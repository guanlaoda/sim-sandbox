"""用户画像数据模型"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgeGroup(str, enum.Enum):
    YOUNG = "young"
    MIDDLE = "middle"
    SENIOR = "senior"


class CommunicationStyle(str, enum.Enum):
    CONCISE = "concise"
    VERBOSE = "verbose"
    EMOTIONAL = "emotional"
    FORMAL = "formal"


class PersonaSkeleton(BaseModel):
    """阶段1输出 — 可复现的结构化骨架"""

    persona_id: str
    age_group: AgeGroup
    tech_literacy: float = Field(ge=0, le=1)
    patience_level: float = Field(ge=0, le=1)
    communication_style: CommunicationStyle
    intent_clarity: float = Field(ge=0, le=1)
    domain_knowledge: Dict[str, float] = Field(default_factory=dict)


class UserPersona(BaseModel):
    """阶段2输出 — LLM 丰化后的完整画像"""

    skeleton: PersonaSkeleton
    name: str
    age: int
    occupation: str
    personality_summary: str
    background_story: str
    language_habits: List[str] = Field(default_factory=list)
    emotional_triggers: List[str] = Field(default_factory=list)
    typical_expressions: Dict[str, str] = Field(default_factory=dict)
    current_mood: float = Field(default=0.5, ge=0, le=1)

    def to_system_prompt(self) -> str:
        """将画像转为 LLM system prompt 片段，用于对话模拟"""
        habits = ", ".join(self.language_habits) if self.language_habits else "无特殊习惯"
        return (
            f"你正在扮演一个真实用户。\n\n"
            f"## 你的身份\n"
            f"{self.personality_summary}\n\n"
            f"姓名: {self.name}\n"
            f"年龄: {self.age}\n"
            f"职业: {self.occupation}\n"
            f"性格: {self.skeleton.communication_style.value}\n"
            f"技术熟练度: {self.skeleton.tech_literacy} (0=完全不懂, 1=非常精通)\n"
            f"耐心程度: {self.skeleton.patience_level} (0=非常急躁, 1=非常有耐心)\n"
            f"语言习惯: {habits}\n"
            f"当前心情: {self.current_mood} (0=很差, 1=很好)\n"
        )
