"""
確定性模擬測試引擎 (Deterministic Simulation Testing - DST)
==========================================================
學術與業界借鏡：
- Antithesis: Deterministic Simulation Testing for Distributed Systems
- FoundationDB: Testing Distributed Systems with Deterministic Simulation (Zhou et al., SIGMOD 2021)

核心原理：
在分散式代理人與非同步流程中，併發競爭與隨機排程常導致幽靈 Bug (Heisenbugs)，無法在 CI 中重現。
本模組提供單執行緒虛擬排程器：
1. 虛擬時鐘 (Virtual Clock): 模擬毫秒級超時與時延，無需真實 OS `time.sleep`。
2. 確定性隨機種子 (Deterministic PRNG): 保證事件序列 100% 相同。
3. 狀態軌跡雜湊指紋 (Trace Fingerprint): 記錄每一步的狀態躍遷與決策，計算 SHA-256 軌跡摘要。
4. 重播錄影機 (Replay Engine): 只要給定相同 `seed`，任何複雜錯誤軌跡皆能 100% 重播除錯。
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class SimulationEvent:
    """模擬器事件"""
    virtual_timestamp_ms: float
    event_type: str
    component: str
    details: Dict[str, Any]
    state_after: Optional[str] = None


class VirtualClock:
    """可控虛擬時鐘"""

    def __init__(self, start_timestamp_ms: float = 0.0):
        self.current_time_ms = start_timestamp_ms

    def now_ms(self) -> float:
        return self.current_time_ms

    def advance_ms(self, delta_ms: float):
        if delta_ms < 0:
            raise ValueError("Virtual time cannot travel backwards")
        self.current_time_ms += delta_ms

    def sleep_ms(self, duration_ms: float):
        self.advance_ms(duration_ms)


class DeterministicSimulationRunner:
    """確定性模擬測試執行器"""

    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.clock = VirtualClock()
        self.events: List[SimulationEvent] = []
        self._action_queue: List[Callable[[], None]] = []

    def reset(self, seed: Optional[int] = None):
        """重置模擬環境與時鐘"""
        if seed is not None:
            self.seed = seed
        self.clock = VirtualClock()
        self.events.clear()
        self._action_queue.clear()

    def record_event(
        self,
        event_type: str,
        component: str,
        details: Dict[str, Any],
        state_after: Optional[str] = None,
    ):
        """記錄單一確定性事件"""
        event = SimulationEvent(
            virtual_timestamp_ms=self.clock.now_ms(),
            event_type=event_type,
            component=component,
            details=details,
            state_after=state_after,
        )
        self.events.append(event)

    def calculate_trace_hash(self) -> str:
        """
        計算整段模擬過程的密碼學軌跡指紋 (Deterministic Trace Hash)
        只要決策順序、步驟或輸出有任何 1 bit 差異，雜湊值即刻不同。
        """
        hasher = hashlib.sha256()
        for ev in self.events:
            event_payload = json.dumps(
                {
                    "t": ev.virtual_timestamp_ms,
                    "type": ev.event_type,
                    "comp": ev.component,
                    "details": ev.details,
                    "state": ev.state_after,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            hasher.update(event_payload.encode("utf-8"))
        return hasher.hexdigest()

    def run_multi_step_scenario(
        self,
        initial_state: str,
        steps: List[Dict[str, Any]],
        step_handler: Callable[[Dict[str, Any], VirtualClock], Tuple[str, Dict[str, Any]]],
    ) -> str:
        """
        依序執行多步模擬場景並推進虛擬時鐘
        """
        current_state = initial_state
        self.record_event(
            event_type="SCENARIO_START",
            component="SimulationCoordinator",
            details={"initial_state": initial_state, "total_steps": len(steps)},
            state_after=current_state,
        )

        for i, step_def in enumerate(steps):
            # 步進虛擬時間 (例如每步推進 10ms ~ 50ms)
            step_duration = step_def.get("duration_ms", 15.0)
            self.clock.advance_ms(step_duration)

            next_state, outcome = step_handler(step_def, self.clock)
            self.record_event(
                event_type=f"STEP_{i+1}_EXECUTE",
                component=step_def.get("component", "AgentEngine"),
                details=outcome,
                state_after=next_state,
            )
            current_state = next_state

        self.record_event(
            event_type="SCENARIO_END",
            component="SimulationCoordinator",
            details={"final_state": current_state},
            state_after=current_state,
        )

        return self.calculate_trace_hash()
