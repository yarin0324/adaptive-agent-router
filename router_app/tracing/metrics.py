"""
原生 Prometheus 遙測指標收集器 (Prometheus Metrics Exporter)
純 Python 零外部重型依賴實作，符合 OpenMetrics / Prometheus 文字格式規範。
開箱即用，可直接掛載至 HTTP GET /metrics 端點供 Grafana 與 Prometheus 抓取。
"""

import time
from collections import defaultdict
from typing import Dict, Tuple


class MetricsCollector:
    """Prometheus 指標收集器單例"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._init_metrics()
        return cls._instance

    def _init_metrics(self):
        # 計數器: (mode, tier, status) -> 次數
        self.requests_total: Dict[Tuple[str, str, str], int] = defaultdict(int)
        self.cache_hits_total: int = 0
        self.circuit_breaker_trips_total: int = 0
        self.suspended_tasks_total: int = 0
        self.tokens_consumed_total: int = 0
        self.tokens_saved_total: int = 0
        # 耗時總合與次數: mode -> (total_seconds, count)
        self.duration_seconds_sum: Dict[str, float] = defaultdict(float)
        self.duration_seconds_count: Dict[str, int] = defaultdict(int)

    def record_request(self, mode: str, tier: str, status: str = "success", duration_seconds: float = 0.0):
        self.requests_total[(mode, tier, status)] += 1
        self.duration_seconds_sum[mode] += duration_seconds
        self.duration_seconds_count[mode] += 1

    def record_cache_hit(self):
        self.cache_hits_total += 1

    def record_circuit_breaker_trip(self):
        self.circuit_breaker_trips_total += 1

    def record_suspended_task(self):
        self.suspended_tasks_total += 1

    def record_tokens(self, consumed: int, saved: int = 0):
        self.tokens_consumed_total += consumed
        self.tokens_saved_total += saved

    def export_prometheus_text(self) -> str:
        """導出符合 Prometheus 標準文字格式的指標資料"""
        lines = []

        # 1. 請求總數計數器
        lines.append("# HELP router_requests_total Total number of routed agent requests.")
        lines.append("# TYPE router_requests_total counter")
        for (mode, tier, status), count in sorted(self.requests_total.items()):
            lines.append(f'router_requests_total{{mode="{mode}",tier="{tier}",status="{status}"}} {count}')
        if not self.requests_total:
            lines.append('router_requests_total{mode="none",tier="none",status="none"} 0')

        # 2. 快取命中計數器
        lines.append("# HELP router_cache_hits_total Total number of zero-delay route cache hits.")
        lines.append("# TYPE router_cache_hits_total counter")
        lines.append(f"router_cache_hits_total {self.cache_hits_total}")

        # 3. 熔斷攔截計數器
        lines.append("# HELP router_circuit_breaker_trips_total Total circuit breaker emergency trips.")
        lines.append("# TYPE router_circuit_breaker_trips_total counter")
        lines.append(f"router_circuit_breaker_trips_total {self.circuit_breaker_trips_total}")

        # 4. 人機審批掛起計數器
        lines.append("# HELP router_suspended_tasks_total Total tasks suspended for human approval.")
        lines.append("# TYPE router_suspended_tasks_total counter")
        lines.append(f"router_suspended_tasks_total {self.suspended_tasks_total}")

        # 5. Token 消耗與壓縮節省計數器
        lines.append("# HELP router_tokens_consumed_total Total LLM tokens consumed.")
        lines.append("# TYPE router_tokens_consumed_total counter")
        lines.append(f"router_tokens_consumed_total {self.tokens_consumed_total}")

        lines.append("# HELP router_tokens_saved_total Total tokens saved by context compression.")
        lines.append("# TYPE router_tokens_saved_total counter")
        lines.append(f"router_tokens_saved_total {self.tokens_saved_total}")

        # 6. 耗時彙總
        lines.append("# HELP router_request_duration_seconds Latency summary of mode execution.")
        lines.append("# TYPE router_request_duration_seconds summary")
        for mode, total_sec in sorted(self.duration_seconds_sum.items()):
            count = self.duration_seconds_count[mode]
            lines.append(f'router_request_duration_seconds_sum{{mode="{mode}"}} {total_sec:.4f}')
            lines.append(f'router_request_duration_seconds_count{{mode="{mode}"}} {count}')

        return "\n".join(lines) + "\n"


# 全域單例
metrics = MetricsCollector()
