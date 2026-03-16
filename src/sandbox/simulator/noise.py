"""LLM 驱动的文本风格化噪声引擎

通过大模型对用户消息施加各类真实感失真：
ASR 噪声、打字错误、方言特征、表情符号、语气词、自我纠正等。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..models.persona import Dialect, NoiseProfile

logger = logging.getLogger(__name__)

# 方言描述映射
_DIALECT_DESC: dict[Dialect, str] = {
    Dialect.NORTHERN: (
        "北方口语: 使用儿化音、'咋整''得嘞''中不中''能成''搁哪儿''玩意儿'等北方口语，"
        "语气后缀如'呗''嘛''呢吧'"
    ),
    Dialect.SOUTHERN: (
        "南方口语: 使用'蛮好的''晓得''要得''么子''好得很'等南方口语，"
        "语气后缀如'嘞''喏''啵''咯'"
    ),
    Dialect.CANTONESE: (
        "粤语混用: 偶尔夹杂'唔该''有冇''靓''咩''乜嘢'等粤语词，"
        "语气后缀如'嘅''喇''咩''啦'"
    ),
    Dialect.SICHUAN: (
        "川渝口语: 使用'要得''巴适''莫得''啥子''啷个''晓得'等川渝方言词，"
        "语气后缀如'嘛''撒''噻'"
    ),
    Dialect.SHANGHAI: (
        "吴语特征: 偶尔用'阿拉'(我)、'侬'(你)、'老好的''啥个'等上海话词汇，"
        "语气后缀如'伐''嗯哪'"
    ),
}


def build_noise_style_instructions(profile: NoiseProfile, mood: float = 0.5) -> str:
    """根据 NoiseProfile 构建风格化噪声指令文本。

    可嵌入 system prompt 或用于独立噪声转换。
    """
    if not is_noise_active(profile):
        return ""

    sections: list[str] = []
    p = profile

    if p.asr_error_rate > 0:
        level = "少量" if p.asr_error_rate < 0.1 else ("中等" if p.asr_error_rate < 0.25 else "较多")
        sections.append(
            f"- ASR 语音识别错误 (程度: {level}): "
            "将部分字词替换为同音字或近音字，模拟语音转文字的错误。"
            "例: 北京→背景、机票→鸡票、帮我→办我、预订→鱼定、出发→初发。"
            "声母混淆: zh/z, ch/c, sh/s, n/l, r/l"
        )

    if p.typo_rate > 0:
        level = "偶尔" if p.typo_rate < 0.1 else ("时常" if p.typo_rate < 0.25 else "频繁")
        sections.append(
            f"- 打字/拼音选词错误 ({level}): "
            "模拟拼音输入法选错候选词。"
            "例: 航班→杭班、经济舱→精济仓、查询→茶询"
        )

    if p.dialect != Dialect.NONE:
        desc = _DIALECT_DESC.get(p.dialect, "")
        if desc:
            sections.append(f"- 方言特征 — {desc}")

    if p.emoji_frequency > 0:
        level = "偶尔" if p.emoji_frequency < 0.2 else ("较多" if p.emoji_frequency < 0.5 else "频繁")
        mood_hint = "正面emoji如😄👌🙏👍" if mood > 0.6 else (
            "负面emoji如😭😡😤😞" if mood < 0.3 else "中性emoji如🤔😅😏👀"
        )
        sections.append(
            f"- 表情符号 ({level}): 在句末添加{mood_hint}"
        )

    if p.filler_word_rate > 0:
        level = "偶尔" if p.filler_word_rate < 0.2 else "经常"
        sections.append(
            f"- 语气词/犹豫词 ({level}): "
            "在句首或中间插入'嗯''那个''就是说''额''怎么说呢''然后'等口头禅"
        )

    if p.abbreviation_rate > 0:
        level = "偶尔" if p.abbreviation_rate < 0.1 else "较常"
        sections.append(
            f"- 缩写 ({level}): "
            "将地名或术语缩写为拼音首字母，如 北京→bj、上海→sh、经济舱→jjc"
        )

    if p.internet_slang:
        sections.append(
            "- 网络用语: 使用年轻人网络梗，如 yyds、绝绝子、6/666、蚌埠住了、"
            "芭比Q了、寄了、感谢老铁、蟹蟹"
        )

    if p.self_correction_rate > 0:
        level = "偶尔" if p.self_correction_rate < 0.1 else "时常"
        sections.append(
            f"- 自我纠正 ({level}): "
            "说错后自行纠正，如'去南京，不对，去北京''去杭州...等等，上海才对'"
        )

    if p.punctuation_chaos > 0:
        level = "轻微" if p.punctuation_chaos < 0.1 else "明显"
        sections.append(
            f"- 标点混乱 ({level}): "
            "省略标点或叠加感叹号/问号，如省掉逗号句号、连用'！！！'或'？？？'"
        )

    header = "你的消息需要体现以下真实用户输入特征（模拟语音输入或手机打字的各种失真）：\n"
    footer = (
        "\n重要：保持原始语义完全不变，噪声要自然像真人说话/打字，"
        "不要过度叠加导致不可读。"
    )
    return header + "\n".join(sections) + footer


def is_noise_active(profile: NoiseProfile) -> bool:
    """检查是否有任何噪声被启用"""
    p = profile
    return (
        p.asr_error_rate > 0
        or p.typo_rate > 0
        or p.dialect != Dialect.NONE
        or p.emoji_frequency > 0
        or p.filler_word_rate > 0
        or p.abbreviation_rate > 0
        or p.internet_slang
        or p.self_correction_rate > 0
        or p.punctuation_chaos > 0
    )


class LLMNoiseInjector:
    """通过 LLM 对已生成的文本施加风格化噪声（用于 RuleBasedStrategy 后处理）"""

    def __init__(self, llm_client: Any, model: str = "deepseek-chat") -> None:
        self._client = llm_client
        self._model = model

    async def apply(
        self, text: str, profile: NoiseProfile, mood: float = 0.5
    ) -> str:
        """调用 LLM 对文本施加噪声，返回风格化后的文本"""
        if not text or not is_noise_active(profile):
            return text

        style_instructions = build_noise_style_instructions(profile, mood)

        system_prompt = (
            "你是一个文本风格化引擎。将给定的中文文本改写为带有指定噪声特征的版本。\n\n"
            f"{style_instructions}\n\n"
            "规则：\n"
            "1. 保持原始语义和意图完全不变\n"
            "2. 只输出改写后的文本，不要 JSON、引号或任何解释\n"
            "3. 如果原文很短（<5字），可以只做微调或不改\n"
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.9,
                max_tokens=200,
            )
            result = (response.choices[0].message.content or "").strip()
            # 防御：如果 LLM 返回为空或异常长，回退到原文
            if not result or len(result) > len(text) * 3:
                return text
            return result
        except Exception as exc:
            logger.warning("LLM noise injection failed, returning original: %s", exc)
            return text
