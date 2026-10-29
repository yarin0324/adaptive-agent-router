"""
設定檔 (Configuration)
管理 API 金鑰、預設模型與模式開關。
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 自動尋找並載入 .env
load_dotenv()


class RouterConfig:
    # 預設路由器模型：建議用便宜快速的模型（支援 OpenAI, Gemini, Claude, Ollama, DeepSeek 等格式）
    ROUTER_MODEL: str = os.getenv("ROUTER_MODEL", "gpt-4o-mini")

    # 預設深度專家模型：用於 Planner, Multi-Agent, Reflection
    EXPERT_MODEL: str = os.getenv("EXPERT_MODEL", "gpt-4o")

    # 溫度設定
    ROUTER_TEMPERATURE: float = float(os.getenv("ROUTER_TEMPERATURE", "0.0"))
    EXPERT_TEMPERATURE: float = float(os.getenv("EXPERT_TEMPERATURE", "0.3"))

    # 安全與護欄門檻
    STRICT_VERIFIER_MODE: bool = os.getenv("ENABLE_VERIFIER_GATED", "true").lower() == "true"
    MAX_REFLECTION_ROUNDS: int = int(os.getenv("MAX_REFLECTION_ROUNDS", "3"))
    MAX_REACT_LOOPS: int = int(os.getenv("MAX_REACT_LOOPS", "5"))


config = RouterConfig()
