"""
自適應 ELO 反饋調校引擎 (Feedback-Driven ELO Rating Tuner)
借鏡國際象棋等級分 (ELO Rating System) 與 RouteLLM Preference Router。
依據實際執行成功率、延遲表現與人工審核反饋，動態微調各 Agent 模式與原型的信心偏好權重。
"""

import math
import json
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from ..types import AgentMode


class ModeFeedbackStats(BaseModel):
    mode: AgentMode
    elo_rating: float = Field(default=1200.0, description="目前 ELO 等級分 (基準分 1200)")
    total_calls: int = Field(default=0, description="歷史總呼叫次數")
    success_calls: int = Field(default=0, description="成功次數")
    failed_calls: int = Field(default=0, description="失敗或升級中斷次數")
    avg_latency_ms: float = Field(default=0.0, description="平均耗時 (毫秒)")
    last_updated: float = Field(default_factory=time.time, description="最後更新時間")


class ELORatingTuner:
    """模式等級分與自適應偏好權重調校器"""

    def __init__(self, k_factor: float = 32.0, base_rating: float = 1200.0):
        self.k_factor = k_factor
        self.base_rating = base_rating
        self.stats: Dict[AgentMode, ModeFeedbackStats] = {
            mode: ModeFeedbackStats(mode=mode, elo_rating=base_rating)
            for mode in AgentMode
        }

    def record_feedback(
        self,
        mode: AgentMode,
        success: bool,
        latency_ms: float = 0.0,
        user_rating: Optional[float] = None,
    ) -> float:
        """
        記錄一次執行成果並計算 ELO 增減
        - success: 任務是否順利完成 (True=勝, False=負/中斷)
        - user_rating: 1.0 ~ 5.0 (選填)
        """
        if mode not in self.stats:
            self.stats[mode] = ModeFeedbackStats(mode=mode, elo_rating=self.base_rating)

        stat = self.stats[mode]
        stat.total_calls += 1
        if success:
            stat.success_calls += 1
        else:
            stat.failed_calls += 1

        # 更新指數移動平均延遲
        if stat.total_calls == 1:
            stat.avg_latency_ms = latency_ms
        else:
            stat.avg_latency_ms = 0.85 * stat.avg_latency_ms + 0.15 * latency_ms

        # 計算期望勝率 (Expected Probability) 相對於基準 1200
        rating_diff = stat.elo_rating - self.base_rating
        expected_score = 1.0 / (1.0 + math.pow(10, -rating_diff / 400.0))

        # 計算實際得分 (Actual Score)
        if user_rating is not None:
            # 轉換 1~5 星評分至 0.0 ~ 1.0
            actual_score = max(0.0, min(1.0, (user_rating - 1.0) / 4.0))
        else:
            actual_score = 1.0 if success else 0.0

        # ELO 更新公式: R_new = R_old + K * (Actual - Expected)
        elo_delta = self.k_factor * (actual_score - expected_score)
        stat.elo_rating = round(stat.elo_rating + elo_delta, 2)
        stat.last_updated = time.time()

        return stat.elo_rating

    def get_routing_bias(self, mode: AgentMode) -> float:
        """
        取得該模式對於路由器信心分數的加權補償 (Bias Delta: -0.15 ~ +0.15)
        正分提升優先級，負分抑制作為降級依據
        """
        stat = self.stats.get(mode)
        if not stat:
            return 0.0

        # 將 ELO 偏差 (例如 1000 ~ 1400) 映射至 [-0.15, +0.15]
        diff = stat.elo_rating - self.base_rating
        bias = math.tanh(diff / 300.0) * 0.15
        return round(bias, 4)

    def get_mode_stats(self, mode: AgentMode) -> Dict[str, Any]:
        """取得單一模式的統計指標"""
        if mode in self.stats:
            return self.stats[mode].model_dump()
        return {}

    def export_ratings(self) -> Dict[str, Any]:
        """導出所有模式之 ELO 現狀以利持久化"""
        return {
            mode.value: stat.model_dump()
            for mode, stat in self.stats.items()
        }

    def load_ratings(self, data: Dict[str, Any]):
        """載入歷史 ELO 等級分狀態"""
        for mode_str, stat_dict in data.items():
            try:
                mode = AgentMode(mode_str)
                self.stats[mode] = ModeFeedbackStats(**stat_dict)
            except Exception:
                continue
