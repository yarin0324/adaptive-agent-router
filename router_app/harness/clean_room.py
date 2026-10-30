"""
無菌室子代理隔離執行器 (Clean-Room Subagent Runner)
設計理念源自 The Agent Harness 與無菌室架構原則。

核心痛點：
多代理協同中，若讓子代理在主會話同一個上下文視窗內進行繁重的爬蟲探勘、錯誤重試或數據清洗，
成百上千行的中間除錯過程會直接污染主上下文，使主代理注意力渙散。

本模組提供「無菌室隔離機制」：
  1. 為子任務開闢獨立且乾淨的 Scratchpad 上下文。
  2. 子代理在無菌室內完成多輪執行、重試與資料聚合。
  3. 執行結束後，僅將高密度摘要（Summary Output）與結構化成果（Artifacts）交還給主上下文。
"""

import time
from typing import Any, Callable, Dict, Optional

from .types import CleanRoomResult


class CleanRoomSubagentRunner:
    """無菌室子代理隔離執行器"""

    @classmethod
    def execute_in_clean_room(
        cls,
        subagent_id: str,
        task_description: str,
        task_fn: Callable[..., Dict[str, Any]],
        **task_kwargs,
    ) -> CleanRoomResult:
        """
        在隔離無菌室中執行特定子任務
        """
        start_time = time.perf_counter()

        try:
            # 於獨立無菌室閉包內執行任務
            raw_result = task_fn(**task_kwargs)
            success = True

            # 抽取精煉摘要與結構化產物
            summary = str(raw_result.get("summary", raw_result.get("output", "任務執行完成")))
            artifacts = raw_result.get("artifacts", {})
            tokens = int(raw_result.get("tokens_consumed", max(1, int(len(str(raw_result)) / 3.6))))

        except Exception as e:
            success = False
            summary = f"無菌室子代理執行異常: {str(e)}"
            artifacts = {"error": str(e)}
            tokens = 0

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return CleanRoomResult(
            subagent_id=subagent_id,
            task_description=task_description,
            success=success,
            summary_output=summary,
            structured_artifacts=artifacts,
            tokens_consumed=tokens,
            execution_time_ms=round(latency_ms, 3),
        )
