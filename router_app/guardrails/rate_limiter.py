"""
滑動窗口速率限制與 Token 炸彈防護 (Sliding Window Rate Limiter & Token Bomb Guard - OWASP LLM10)
防止惡意呼叫者透過高頻請求或巨型 Token 炸彈發動「錢包拒絕服務攻擊 (Denial-of-Wallet)」，
即時監控每分鐘請求數 (RPM) 與每分鐘 Token 消耗量 (TPM)。
"""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    max_requests_per_minute: int = Field(default=60, description="每分鐘最大允許請求數 (RPM)")
    max_tokens_per_minute: int = Field(default=60000, description="每分鐘最大允許 Token 額度 (TPM)")
    max_prompt_length_chars: int = Field(default=25000, description="單次 Prompt 長度上限 (防止巨型 Token 炸彈)")

    def __init__(self, **data):
        if "rpm" in data:
            data["max_requests_per_minute"] = data.pop("rpm")
        if "tpm" in data:
            data["max_tokens_per_minute"] = data.pop("tpm")
        if "max_prompt_chars" in data:
            data["max_prompt_length_chars"] = data.pop("max_prompt_chars")
        super().__init__(**data)

    @property
    def rpm(self) -> int:
        return self.max_requests_per_minute

    @rpm.setter
    def rpm(self, val: int):
        self.max_requests_per_minute = val


class SlidingWindowRateLimiter:
    """滑動時間窗口速率限制器"""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        # client_id -> 請求時間戳清單
        self._request_timestamps: Dict[str, List[float]] = defaultdict(list)
        # client_id -> (時間戳, token數) 清單
        self._token_records: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self._lock = threading.Lock()

    def _cleanup_expired(self, client_id: str, now: float):
        """清除超過 60 秒的時間戳"""
        cutoff = now - 60.0
        self._request_timestamps[client_id] = [
            ts for ts in self._request_timestamps[client_id] if ts > cutoff
        ]
        self._token_records[client_id] = [
            (ts, tok) for ts, tok in self._token_records[client_id] if ts > cutoff
        ]

    def check_limit(
        self,
        client_id: str,
        prompt_str: str = "",
        estimated_tokens: int = 0,
    ) -> Tuple[bool, str, int]:
        """
        校驗是否超出頻率與額度 (執行緒安全)
        回傳: (是否允許, 原因說明, 需等待秒數 Retry-After)
        """
        with self._lock:
            now = time.time()

            # 1. 檢驗單次 Prompt 炸彈 (字元長度防護)
            if len(prompt_str) > self.config.max_prompt_length_chars:
                return (
                    False,
                    f"阻斷 Token 炸彈攻擊：Prompt 長度 ({len(prompt_str)} 字元) 超出單次上限 ({self.config.max_prompt_length_chars} 字元)。",
                    60,
                )

            self._cleanup_expired(client_id, now)

            # 2. 檢驗每分鐘請求次數 (RPM)
            current_rpm = len(self._request_timestamps[client_id])
            if current_rpm >= self.config.max_requests_per_minute:
                oldest_ts = self._request_timestamps[client_id][0]
                retry_after = max(1, int(60.0 - (now - oldest_ts)))
                return (
                    False,
                    f"超出請求頻率上限 (RPM: {current_rpm} >= {self.config.max_requests_per_minute})，啟動頻率限制閥門。",
                    retry_after,
                )

            # 3. 檢驗每分鐘 Token 額度 (TPM)
            current_tpm = sum(tok for _, tok in self._token_records[client_id])
            if current_tpm + estimated_tokens > self.config.max_tokens_per_minute:
                retry_after = 30
                return (
                    False,
                    f"超出每分鐘 Token 預算額度 (TPM: {current_tpm} + {estimated_tokens} > {self.config.max_tokens_per_minute})，啟動帳單保護。",
                    retry_after,
                )

            # 記錄本次請求
            self._request_timestamps[client_id].append(now)
            if estimated_tokens > 0:
                self._token_records[client_id].append((now, estimated_tokens))

            return True, "Rate limit check passed.", 0
