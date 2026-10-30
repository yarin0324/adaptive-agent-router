"""
漸進式技能揭露註冊表 (Progressive Skill Disclosure Registry)
設計理念源自 The Agent Harness 與 Anthropic Tool Progressive Disclosure。

核心痛點：
當系統擁有數十個專業技能與工具時，若在 System Prompt 一次性灌入所有詳細規格與參數說明，
將劇烈消耗 5,000 ~ 15,000 Tokens，導致上下文視窗過早耗盡且引發嚴重的注意力迷失（Lost-in-the-Middle）。

本模組透過「兩階段漸進式揭露（Progressive Disclosure）」：
  1. 常態上下文僅注入極簡技能目錄（Compact Index，每項技能約 15 Tokens）。
  2. 當 Agent 決定或 Router 指派特定技能時，才由程式碼隨需注入（On-demand Load）該技能之完整規格。
"""

import json
from typing import Dict, List, Optional

from .types import SkillDescriptor


class ProgressiveSkillRegistry:
    """漸進式技能註冊表"""

    def __init__(self):
        self._skills: Dict[str, SkillDescriptor] = {}

    def register(
        self,
        name: str,
        summary: str,
        category: str = "general",
        full_instructions: str = "",
        parameters_schema: Optional[Dict[str, any]] = None,
    ):
        """註冊新技能"""
        desc = SkillDescriptor(
            name=name,
            summary=summary.strip(),
            category=category,
            full_instructions=full_instructions.strip(),
            parameters_schema=parameters_schema or {},
            is_loaded=False,
        )
        self._skills[name] = desc

    def get_compact_index(self) -> str:
        """
        產出極簡常駐技能目錄 (Compact Skill Index)
        僅提供名稱與單句描述，消耗極少 Token
        """
        lines = ["[AVAILABLE_SKILLS_INDEX] (On-Demand Progressive Disclosure)"]
        for name, desc in sorted(self._skills.items()):
            lines.append(f"- `{name}` ({desc.category}): {desc.summary}")
        return "\n".join(lines)

    def resolve_skills(self, skill_names: List[str]) -> str:
        """
        依需求隨需展開特定技能之完整使用指南與參數規格
        """
        resolved_blocks = []
        for name in skill_names:
            if name in self._skills:
                desc = self._skills[name]
                desc.is_loaded = True
                
                block = [f"### [SKILL: {desc.name}]"]
                block.append(f"**類別**: {desc.category}")
                block.append(f"**核心職責**: {desc.summary}")
                if desc.full_instructions:
                    block.append(f"**詳細操作規範**:\n{desc.full_instructions}")
                if desc.parameters_schema:
                    schema_str = json.dumps(desc.parameters_schema, indent=2, ensure_ascii=False)
                    block.append(f"**參數規範 (JSON Schema)**:\n```json\n{schema_str}\n```")
                resolved_blocks.append("\n".join(block))

        return "\n\n---\n\n".join(resolved_blocks)

    def calculate_token_savings(self) -> Dict[str, any]:
        """計算漸進式揭露所節省的 Token 估計值"""
        compact_text = self.get_compact_index()
        compact_tokens = max(1, int(len(compact_text) / 3.6))

        # 計算若全量展開的 Token 消耗
        full_text = self.resolve_skills(list(self._skills.keys()))
        full_tokens = max(1, int(len(full_text) / 3.6))

        saved_tokens = max(0, full_tokens - compact_tokens)
        saved_ratio = saved_tokens / max(1, full_tokens)

        return {
            "total_skills": len(self._skills),
            "compact_index_tokens": compact_tokens,
            "full_disclosure_tokens": full_tokens,
            "tokens_saved": saved_tokens,
            "saving_ratio": round(saved_ratio, 4),
        }
