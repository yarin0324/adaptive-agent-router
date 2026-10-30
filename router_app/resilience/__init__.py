"""
系統韌性與前沿測試套件 (Resilience & Advanced Testing Engineering)
================================================================
包含：
1. Agent Chaos Monkey (Netflix 風格混沌工程故障注入)
2. Deterministic Simulation Testing - DST (Antithesis 風格確定性模擬重現)
3. Test-as-Oracle Runner (SWE-bench 風格實體代碼測試即真理)
4. Production Shadow Dual-Run (Stripe/Uber 風格生產環境陰影雙跑比對)
"""

from .chaos_monkey import (
    ChaosFaultType,
    ChaosInjectionConfig,
    ChaosEventRecord,
    ChaosInjectionException,
    AgentChaosMonkey,
)
from .simulation import (
    SimulationEvent,
    VirtualClock,
    DeterministicSimulationRunner,
)
from .test_oracle import (
    OracleExecutionResult,
    TestAsOracle,
)
from .shadow_runner import (
    ShadowComparisonReport,
    ShadowDualRunner,
)

__all__ = [
    # Chaos Monkey
    "ChaosFaultType",
    "ChaosInjectionConfig",
    "ChaosEventRecord",
    "ChaosInjectionException",
    "AgentChaosMonkey",
    # Simulation
    "SimulationEvent",
    "VirtualClock",
    "DeterministicSimulationRunner",
    # Test as Oracle
    "OracleExecutionResult",
    "TestAsOracle",
    # Shadow Runner
    "ShadowComparisonReport",
    "ShadowDualRunner",
]
