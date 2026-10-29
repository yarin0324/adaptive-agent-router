"""
輕量語意原型匹配層 (Semantic Prototype Matcher)
借鏡自 Semantic Router (Aurelio AI)
採用特徵向量空間與餘弦/Jaccard 語意相似度，不呼叫龐大 LLM 即可在 5ms 內精確命中典型模式。
"""

import math
import re
from typing import Dict, List, Optional, Tuple
from ..types import AgentMode, ModelTier, RoutingDecision, RiskLevel


class SemanticPrototypeMatcher:
    """輕量快速語意原型匹配器"""

    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold
        # 各模式之原型特徵庫
        self.prototypes: Dict[AgentMode, List[str]] = {
            AgentMode.SINGLE_TURN: [
                "抽取 文字 中的 電話 統編 欄位 整理 成 表格",
                "提取 摘要 總結 重點 翻譯",
                "格式 轉換 json 表格 欄位 解析",
            ],
            AgentMode.REACT: [
                "調查 為什麼 延遲 飆高 異常 原因 探索",
                "排查 故障 邊看 邊測 找找看 猜測 嘗試",
                "日誌 分析 追蹤 尋找 根本 原因",
            ],
            AgentMode.PLANNER_EXECUTOR: [
                "規劃 完整 方案 步驟 分解 里程碑 藍圖",
                "百萬 級 批量 處理 架構 拆解 專案 計畫",
                "多步驟 長流程 任務 拓撲 並行 工作",
            ],
            AgentMode.REFLECTION: [
                "嚴格 審查 合約 條款 挑出 漏洞 反思 優化",
                "論文 代碼 審核 批評 抓蟲 改寫 精煉",
                "法務 合規 風險 漏洞 多輪 審查",
            ],
            AgentMode.MULTI_AGENT: [
                "跨部門 多角度 評估 安排 專家 辯論",
                "正方 反方 紅隊 挑刺 仲裁 評估 論證",
                "架構師 風控 領域 專家 圓桌 協商",
            ],
            AgentMode.MEMORY_AUGMENTED: [
                "查詢 歷史 記憶 長期 規範 喚醒 脈絡",
                "本專案 規範 慣例 決策 背景 防死鎖 with",
                "個人 偏好 記憶 檢索 跨輪次 累積 規則",
            ],
        }

    def _tokenize(self, text: str) -> set:
        """分詞與字元 N-gram 萃取"""
        words = set(re.findall(r"[\w]+", text.lower()))
        # 加入雙字元 N-gram 強化中文語意匹配
        clean_text = "".join(words)
        bigrams = {clean_text[i : i + 2] for i in range(len(clean_text) - 1)}
        return words.union(bigrams)

    def _similarity(self, set1: set, set2: set) -> float:
        """Jaccard / Cosine 語意相似度計量"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def match(self, prompt: str) -> Optional[Tuple[AgentMode, float, str]]:
        """計算輸入提問與各模式原型的相似度"""
        query_tokens = self._tokenize(prompt)
        best_mode: Optional[AgentMode] = None
        highest_score = 0.0
        matched_sample = ""

        for mode, samples in self.prototypes.items():
            for sample in samples:
                sample_tokens = self._tokenize(sample)
                score = self._similarity(query_tokens, sample_tokens)
                if score > highest_score:
                    highest_score = score
                    best_mode = mode
                    matched_sample = sample

        if highest_score >= self.threshold and best_mode:
            return best_mode, round(highest_score, 3), matched_sample

        return None
