"""
路由快取層 (Routing Cache Layer)
提供精確比對 (Exact Hash) 與基於字串正規化的快取，避免高頻重複查詢重複呼叫分類器，實現 0ms 路由判定。
"""

import hashlib
from typing import Dict, Optional
from ..types import RoutingDecision


class RouteCache:
    """記憶體 LRU 路由快取"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, RoutingDecision] = {}

    def _normalize_key(self, prompt: str) -> str:
        cleaned = "".join(prompt.strip().lower().split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> Optional[RoutingDecision]:
        key = self._normalize_key(prompt)
        return self._cache.get(key)

    def set(self, prompt: str, decision: RoutingDecision):
        key = self._normalize_key(prompt)
        if len(self._cache) >= self.max_size:
            # 淘汰第一個插入的 key
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[key] = decision

    def clear(self):
        self._cache.clear()
