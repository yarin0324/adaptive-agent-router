"""
系統熔斷器與 Token 計量防護 (Circuit Breaker & Token Budget Guard)
實作微服務斷路器模式 (Michael Nygard, Release It!)，專為 LLM Agent 長迴圈設計。
防止 ReAct 思考迴圈或多代理協作陷入死循環、暴走或耗盡 Token 預算。
"""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class CircuitBreakerConfig(BaseModel):
    max_steps_per_task: int = Field(default=8, description="單一任務允許的最大執行步數")
    max_tokens_budget: int = Field(default=8000, description="單一任務最高容許消耗之 Token 預算")
    timeout_seconds: float = Field(default=30.0, description="單一任務最大超時限制 (秒)")


class CircuitBreakerException(Exception):
    """觸發熔斷時拋出的例外"""
    pass


class TaskCircuitBreaker:
    """任務級生命週期熔斷守護者"""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.step_count = 0
        self.tokens_used = 0
        self.start_time = time.time()
        self.is_tripped = False
        self.trip_reason = ""

    def record_step(self, tokens: int = 0, step_detail: Optional[str] = None):
        """每執行一個步驟進行即時監控與計量"""
        self.step_count += 1
        self.tokens_used += tokens
        elapsed = time.time() - self.start_time

        # 1. 步數熔斷檢驗
        if self.step_count > self.config.max_steps_per_task:
            self.trip(f"超出單一任務步數上限 ({self.step_count} > {self.config.max_steps_per_task})，疑似陷入死循環。")

        # 2. Token 預算熔斷檢驗
        if self.tokens_used > self.config.max_tokens_budget:
            self.trip(f"超出 Token 預算額度 ({self.tokens_used} > {self.config.max_tokens_budget})，啟動自我截斷防護。")

        # 3. 逾時熔斷檢驗
        if elapsed > self.config.timeout_seconds:
            self.trip(f"執行時間超過容許閾值 ({elapsed:.1f}s > {self.config.timeout_seconds}s)。")

    def trip(self, reason: str):
        """觸發熔斷"""
        self.is_tripped = True
        self.trip_reason = reason
        raise CircuitBreakerException(f"[熔斷保護機制生效] 系統強制終止執行：{reason}")

    def get_telemetry(self) -> Dict[str, Any]:
        """產出監控數據"""
        return {
            "elapsed_seconds": round(time.time() - self.start_time, 3),
            "total_steps": self.step_count,
            "tokens_used": self.tokens_used,
            "is_tripped": self.is_tripped,
            "trip_reason": self.trip_reason,
        }
