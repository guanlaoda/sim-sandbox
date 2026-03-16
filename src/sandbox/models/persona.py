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


class Dialect(str, enum.Enum):
    NONE = "none"
    NORTHERN = "northern"      # 北方口语 (儿化音、咋整)
    SOUTHERN = "southern"      # 南方口语 (蛮好的、晓得)
    CANTONESE = "cantonese"    # 粤语混用 (唔该、有冇)
    SICHUAN = "sichuan"        # 川渝口语 (要得、巴适)
    SHANGHAI = "shanghai"      # 吴语特征 (阿拉、侬)


class NoiseProfile(BaseModel):
    """文本风格化噪声配置 — 模拟真实用户输入的各种失真"""

    asr_error_rate: float = Field(default=0.0, ge=0, le=1, description="ASR 同音字/吞字错误概率")
    typo_rate: float = Field(default=0.0, ge=0, le=1, description="打字/拼音选词错误概率")
    dialect: Dialect = Field(default=Dialect.NONE, description="方言特征")
    emoji_frequency: float = Field(default=0.0, ge=0, le=1, description="表情符号使用频率")
    filler_word_rate: float = Field(default=0.0, ge=0, le=1, description="语气词/犹豫词插入率")
    abbreviation_rate: float = Field(default=0.0, ge=0, le=1, description="缩写倾向 (bj=北京)")
    internet_slang: bool = Field(default=False, description="是否使用网络用语")
    self_correction_rate: float = Field(default=0.0, ge=0, le=1, description="说完自我纠正概率")
    punctuation_chaos: float = Field(default=0.0, ge=0, le=1, description="标点遗漏/滥用概率")


class PersonaSkeleton(BaseModel):
    """阶段1输出 — 可复现的结构化骨架"""

    persona_id: str
    age_group: AgeGroup
    tech_literacy: float = Field(ge=0, le=1)
    patience_level: float = Field(ge=0, le=1)
    communication_style: CommunicationStyle
    intent_clarity: float = Field(ge=0, le=1)
    domain_knowledge: Dict[str, float] = Field(default_factory=dict)
    noise_profile: NoiseProfile = Field(default_factory=NoiseProfile)


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
        prompt = (
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

        # 噪声风格化提示
        np_ = self.skeleton.noise_profile
        style_hints: list[str] = []
        if np_.dialect != Dialect.NONE:
            dialect_desc = {
                Dialect.NORTHERN: "你说话带北方口音，会用儿化音、'咋整'、'中不中'、'得嘞'等北方口语",
                Dialect.SOUTHERN: "你说话带南方口音，会说'蛮好的'、'晓得'、'要得'等南方口语",
                Dialect.CANTONESE: "你普通话夹杂粤语词，偶尔说'唔该'、'有冇'、'靓'",
                Dialect.SICHUAN: "你说话带川渝口音，会说'要得'、'巴适'、'莫得'、'啥子'",
                Dialect.SHANGHAI: "你说话带上海口音，偶尔冒出'阿拉'、'侬'、'老好的'",
            }
            style_hints.append(dialect_desc.get(np_.dialect, ""))
        if np_.internet_slang:
            style_hints.append("你喜欢用网络用语，如 yyds、绝绝子、6、蚌埠住了等")
        if np_.emoji_frequency > 0.3:
            style_hints.append("你喜欢在消息里加表情符号如 😄👌🔥😭")
        if np_.filler_word_rate > 0.3:
            style_hints.append("你说话时经常带语气词，如'嗯'、'那个'、'就是说'、'额'")
        if np_.self_correction_rate > 0.3:
            style_hints.append("你说话偶尔会说错再纠正，如'去北京，不对，去上海'")
        if np_.punctuation_chaos > 0.3:
            style_hints.append("你打字不太注意标点，经常省略或多打感叹号")

        if style_hints:
            prompt += "\n## 你的说话风格\n"
            for hint in style_hints:
                prompt += f"- {hint}\n"

        return prompt
