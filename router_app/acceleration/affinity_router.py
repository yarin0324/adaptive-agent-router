"""
快取感知親和性路由器 (Cache-Aware Affinity Router)
設計理念源自 SGLang Router 與 Mooncake (月之暗面 Kimi) 的 KV-Cache Centric 負載調度。

核心目標：
當下游部署多台 GPU 推論節點（vLLM / SGLang 叢集）時，若使用傳統 Round-Robin 負載平衡，
相同的前綴（如相同的大型 System Prompt 或相同 RAG 文件）會被隨機打散，
導致每台 GPU 都必須重新進行 Prefill 計算，KV Cache 命中率接近 0%。

本模組透過一致性雜湊（Consistent Hashing with Bounded Loads）與前綴親和性快取表，
確保相同 prefix_hash 優先路由至同一台已具備快取的節點，將跨節點快取命中率最大化。
"""

import bisect
import hashlib
import threading
import time
from typing import Dict, List, Optional, Tuple

from .types import WorkerNode, WorkloadType


class CacheAwareAffinityRouter:
    """快取感知親和性路由器"""

    def __init__(
        self,
        nodes: Optional[List[WorkerNode]] = None,
        virtual_nodes: int = 64,
        spillover_threshold: float = 0.90,  # 當節點負載達 90% 時溢流至次選節點
    ):
        self.virtual_nodes = virtual_nodes
        self.spillover_threshold = spillover_threshold
        self._lock = threading.Lock()
        
        # 節點註冊表
        self.nodes: Dict[str, WorkerNode] = {}
        # 一致性雜湊環: (hash_int, node_id)
        self.ring: List[int] = []
        self.ring_map: Dict[int, str] = {}
        
        # 統計數據
        self.total_routed = 0
        self.cache_hits = 0

        # 初始化預設節點 (若無外部傳入)
        if nodes:
            for node in nodes:
                self.register_node(node)
        else:
            self.register_node(WorkerNode(node_id="worker_gpu_0", endpoint="http://localhost:8001/v1", gpu_type="H100-80GB", capacity=32))
            self.register_node(WorkerNode(node_id="worker_gpu_1", endpoint="http://localhost:8002/v1", gpu_type="H100-80GB", capacity=32))
            self.register_node(WorkerNode(node_id="worker_gpu_2", endpoint="http://localhost:8003/v1", gpu_type="H100-80GB", capacity=32))

    def _hash_key(self, key: str) -> int:
        """計算 32-bit 整數雜湊值"""
        return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)

    def register_node(self, node: WorkerNode):
        """向雜湊環註冊新推論節點"""
        with self._lock:
            self.nodes[node.node_id] = node
            for i in range(self.virtual_nodes):
                v_key = f"{node.node_id}#vnode_{i}"
                h = self._hash_key(v_key)
                self.ring.append(h)
                self.ring_map[h] = node.node_id
            self.ring.sort()

    def unregister_node(self, node_id: str):
        """註銷故障或下線節點"""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
            new_ring = []
            new_map = {}
            for h in self.ring:
                if self.ring_map[h] != node_id:
                    new_ring.append(h)
                    new_map[h] = self.ring_map[h]
            self.ring = new_ring
            self.ring_map = new_map

    def dispatch(
        self,
        prefix_hash: str,
        workload_type: WorkloadType = WorkloadType.BALANCED,
    ) -> Tuple[WorkerNode, bool]:
        """
        為請求指派最適 WorkerNode
        回傳: (WorkerNode, is_cache_hit: bool)
        """
        with self._lock:
            if not self.nodes:
                raise RuntimeError("無可用的後端推論節點 (WorkerNode list is empty)")

            self.total_routed += 1

            # 1. 優先檢查是否已有健康節點已經快取該前綴
            cached_candidates = []
            for nid, node in self.nodes.items():
                if prefix_hash in node.cached_prefixes:
                    # 檢查節點負載是否在安全閥值內
                    if node.active_requests < (node.capacity * self.spillover_threshold):
                        # 若有 Workload 傾向 (例如 Prefill 節點)，給予優先權
                        preference_bonus = 1 if node.workload_preference == workload_type else 0
                        cached_candidates.append((preference_bonus, -node.active_requests, node))

            if cached_candidates:
                # 選擇最適已快取節點
                cached_candidates.sort(reverse=True)
                selected = cached_candidates[0][2]
                selected.active_requests += 1
                selected.total_served += 1
                selected.cache_hits += 1
                self.cache_hits += 1
                return selected, True

            # 2. 若尚未快取，透過一致性雜湊環計算目標節點
            h = self._hash_key(prefix_hash)
            idx = bisect.bisect_right(self.ring, h)
            if idx >= len(self.ring):
                idx = 0

            target_node_id = self.ring_map[self.ring[idx]]
            selected_node = self.nodes[target_node_id]

            # 3. 負載邊界檢查 (Bounded Load Overflow)
            # 若選中節點已飽和，沿環找尋次近之節點
            step = 0
            while selected_node.active_requests >= selected_node.capacity and step < len(self.ring):
                idx = (idx + 1) % len(self.ring)
                selected_node = self.nodes[self.ring_map[self.ring[idx]]]
                step += 1

            # 記錄前綴快取至該節點
            selected_node.cached_prefixes.add(prefix_hash)
            selected_node.active_requests += 1
            selected_node.total_served += 1

            return selected_node, False

    def release(self, node_id: str):
        """請求結束，釋放節點併發 Slot"""
        with self._lock:
            if node_id in self.nodes:
                if self.nodes[node_id].active_requests > 0:
                    self.nodes[node_id].active_requests -= 1

    def get_stats(self) -> Dict[str, any]:
        """匯出叢集快取與負載統計指標"""
        with self._lock:
            hit_ratio = (self.cache_hits / self.total_routed) if self.total_routed > 0 else 0.0
            nodes_stats = {}
            for nid, node in self.nodes.items():
                nodes_stats[nid] = {
                    "endpoint": node.endpoint,
                    "active_requests": node.active_requests,
                    "capacity": node.capacity,
                    "cached_prefixes_count": len(node.cached_prefixes),
                    "total_served": node.total_served,
                    "cache_hits": node.cache_hits,
                }
            return {
                "total_routed": self.total_routed,
                "cluster_cache_hits": self.cache_hits,
                "cluster_cache_hit_ratio": round(hit_ratio, 4),
                "nodes": nodes_stats,
            }
