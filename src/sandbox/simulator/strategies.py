"""用户回复生成策略"""

from __future__ import annotations

import abc
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

from ..models.conversation import ConversationState
from ..models.persona import CommunicationStyle, UserPersona
from ..models.scenario import Injection, Scenario

logger = logging.getLogger(__name__)


class UserAction:
    """用户行为"""

    def __init__(
        self,
        message: str = "",
        internal_thought: str = "",
        mood_delta: float = 0.0,
        wants_to_continue: bool = True,
        terminate: bool = False,
    ) -> None:
        self.message = message
        self.internal_thought = internal_thought
        self.mood_delta = mood_delta
        self.wants_to_continue = wants_to_continue
        self.terminate = terminate


class BaseStrategy(abc.ABC):
    """用户回复生成策略基类"""

    @abc.abstractmethod
    async def generate_opening(
        self,
        persona: UserPersona,
        scenario: Scenario,
    ) -> UserAction:
        """生成开场白"""
        ...

    @abc.abstractmethod
    async def generate_reply(
        self,
        persona: UserPersona,
        scenario: Scenario,
        state: ConversationState,
        bot_response: str,
        triggered_injections: List[Injection] | None = None,
    ) -> UserAction:
        """生成用户回复"""
        ...


# ---- 自然语言表达素材 ----

# slot 值本地化映射
_SLOT_VALUE_LOCALIZE: dict[str, dict[str, str]] = {
    "cabin_class": {
        "economy": "经济舱",
        "business": "商务舱",
        "first": "头等舱",
        "premium_economy": "超级经济舱",
    },
}

# 日期格式自然化: "2026-04-01" → "4月1号"
_DATE_RE = re.compile(r"^\d{4}-(\d{1,2})-(\d{1,2})$")


def _naturalize_date(v: str) -> str:
    m = _DATE_RE.match(str(v))
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return f"{month}月{day}号"
    return str(v)


def _localize_slot(slot_name: str, raw_value: Any) -> str:
    """将 slot 值本地化并自然化"""
    s = str(raw_value)
    mapping = _SLOT_VALUE_LOCALIZE.get(slot_name)
    if mapping:
        s = mapping.get(s, s)
    if slot_name == "date":
        s = _naturalize_date(s)
    return s


# 每个 slot 多种表达模板 — {v} 为占位符
_SLOT_TEMPLATES: dict[str, list[str]] = {
    "departure": [
        "从{v}出发",
        "出发城市是{v}",
        "我在{v}这边",
        "{v}走",
    ],
    "destination": [
        "到{v}",
        "去{v}",
        "飞{v}",
        "目的地是{v}",
    ],
    "date": [
        "{v}的",
        "打算{v}出发",
        "时间就定{v}吧",
        "{v}走",
    ],
    "cabin_class": [
        "坐{v}就行",
        "要{v}",
        "{v}",
        "订{v}的",
    ],
    "passengers": [
        "{v}个人",
        "一共{v}位",
        "我们{v}个人一起",
        "{v}位乘客",
    ],
}

# 按沟通风格的前缀/连接词
_STYLE_PREFIXES: dict[str, list[str]] = {
    "concise": ["", ""],
    "verbose": ["嗯...是这样的，", "让我想想...对了，", "这个嘛..."],
    "emotional": ["哎呀，", "对了对了，", "赶紧帮我看看，"],
    "formal": ["另外，", "还有就是，", "补充一下，"],
}

# 低清晰度下的前缀
_LOW_CLARITY_PREFIXES: list[str] = [
    "嗯...应该是",
    "好像是",
    "我记得是",
    "大概是",
]

# 注入事件的自然化表达模板
_INJECTION_TEMPLATES: list[str] = [
    "等一下，我突然改主意了，{change}",
    "不好意思，刚刚想了下，{change}",
    "哦对了，{change}",
    "抱歉抱歉，临时有变化，{change}",
    "稍等下，{change}",
]

# state_changes 的自然语言描述
_CHANGE_DESC: dict[str, str] = {
    "date": "日期改成{v}",
    "departure": "出发地换成{v}",
    "destination": "目的地改到{v}",
    "cabin_class": "舱位换{v}",
    "passengers": "人数变成{v}位了",
}

# 催促语
_URGE_MESSAGES: list[str] = [
    "信息都给你了，能帮我查查吗？",
    "麻烦帮我看看有什么合适的",
    "这些够了吧？帮我找找",
    "差不多了吧，帮我搜一下呗",
    "信息应该齐了，辛苦帮我看看",
]

# 等待/通用应答
_WAIT_MESSAGES: list[str] = [
    "好的",
    "嗯嗯",
    "行",
    "好，你说",
    "嗯，继续",
    "我听着呢",
]

# 完成感谢语
_THANKS_MESSAGES: list[str] = [
    "好的，谢谢！",
    "行，那就这样，谢谢",
    "没问题，多谢了！",
    "好嘞，感谢！",
]

# 不耐烦/被冒犯时的反应
_OFFENDED_REACTIONS: list[str] = [
    "你这是什么态度？",
    "说话注意点行吗",
    "你这样说话很不礼貌",
    "请你专业一点好吗",
]

# 用于检测 bot 不礼貌/冒犯的关键词
_RUDE_KEYWORDS: list[str] = [
    "有病", "脑子", "白痴", "傻", "蠢", "滚", "闭嘴", "废物", "智障",
]


class RuleBasedStrategy(BaseStrategy):
    """基于规则的用户回复生成策略 (无需 LLM, 用于测试)"""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._opening_slots: set[str] = set()  # 开场白中已提及的 slot

    # ---- 辅助方法 ----

    def _pick(self, choices: list[str]) -> str:
        return self._rng.choice(choices) if choices else ""

    def _format_slot(self, slot_name: str, raw_value: Any) -> str:
        """自然化地表达一个 slot"""
        v = _localize_slot(slot_name, raw_value)
        templates = _SLOT_TEMPLATES.get(slot_name, ["{v}"])
        return self._pick(templates).format(v=v)

    def _is_bot_rude(self, bot_response: str) -> bool:
        return any(kw in bot_response for kw in _RUDE_KEYWORDS)

    def _build_injection_message(self, injection: Injection) -> str:
        """把注入事件转化为自然口语"""
        # 尝试从 state_changes 生成具体描述
        parts: list[str] = []
        for key, val in injection.state_changes.items():
            v = _localize_slot(key, val)
            tmpl = _CHANGE_DESC.get(key)
            if tmpl:
                parts.append(tmpl.format(v=v))
            else:
                parts.append(f"{key}改成{v}")
        change_text = "，".join(parts) if parts else injection.description
        return self._pick(_INJECTION_TEMPLATES).format(change=change_text)

    # ---- 开场白 ----

    async def generate_opening(
        self,
        persona: UserPersona,
        scenario: Scenario,
    ) -> UserAction:
        goal = scenario.user_goal
        style = persona.skeleton.communication_style
        clarity = persona.skeleton.intent_clarity

        if clarity > 0.7:
            # 直接给出部分信息
            slot_items = list(goal.slots.items())
            # 开场时提供前 1~2 个 slot
            n = min(2, len(slot_items))
            opening_slots = slot_items[:n]
            slot_parts = [self._format_slot(k, v) for k, v in opening_slots]
            slot_info = "，".join(slot_parts)
            self._opening_slots = {k for k, _ in opening_slots}

            if style == CommunicationStyle.FORMAL:
                msg = f"您好，我想{goal.primary_intent}，{slot_info}"
            elif style == CommunicationStyle.EMOTIONAL:
                msg = f"你好！我急着要{goal.primary_intent}！{slot_info}，赶紧帮我处理！"
            else:
                msg = f"你好，我想{goal.primary_intent}，{slot_info}"
        else:
            if style == CommunicationStyle.VERBOSE:
                msg = f"嗯...是这样的，我有个事情想问问...就是关于{goal.primary_intent}的事情..."
            else:
                msg = f"你好，我想问下{goal.primary_intent}的事"

        return UserAction(
            message=msg,
            internal_thought=f"我要{goal.primary_intent}，期望达成目标",
        )

    # ---- 回复 ----

    async def generate_reply(
        self,
        persona: UserPersona,
        scenario: Scenario,
        state: ConversationState,
        bot_response: str,
        triggered_injections: List[Injection] | None = None,
    ) -> UserAction:
        goal = scenario.user_goal
        mood_delta = 0.0

        # 0. 检测 bot 是否不礼貌 — 影响情绪并可能回击
        if self._is_bot_rude(bot_response):
            mood_delta -= 0.2
            if state.user_mood + mood_delta < 0.3:
                return UserAction(
                    message=self._pick(_OFFENDED_REACTIONS),
                    internal_thought="bot 态度恶劣，很生气",
                    mood_delta=mood_delta,
                    wants_to_continue=False,
                )
            return UserAction(
                message=self._pick(_OFFENDED_REACTIONS) + "，算了，我继续说正事。",
                internal_thought="bot 态度不好但忍着继续",
                mood_delta=mood_delta,
            )

        # 1. 处理注入事件 — 自然口语化
        if triggered_injections:
            injection = triggered_injections[0]
            mood_delta += injection.user_mood_delta
            msg = self._build_injection_message(injection)
            return UserAction(
                message=msg,
                internal_thought=f"计划变更: {injection.event_type}",
                mood_delta=mood_delta,
            )

        # 2. 提供未提供过的 slot
        remaining_slots = {
            k: v
            for k, v in goal.slots.items()
            if k not in state.slots_confirmed
            and k not in state.slots_offered
            and k not in self._opening_slots
        }

        if remaining_slots:
            slot_name, slot_value = next(iter(remaining_slots.items()))
            clarity = persona.skeleton.intent_clarity
            style_key = persona.skeleton.communication_style.value
            slot_expr = self._format_slot(slot_name, slot_value)

            # 根据风格/清晰度组装
            if clarity <= 0.5:
                prefix = self._pick(_LOW_CLARITY_PREFIXES)
                msg = f"{prefix}{slot_expr}"
            else:
                prefixes = _STYLE_PREFIXES.get(style_key, [""])
                prefix = self._pick(prefixes)
                msg = f"{prefix}{slot_expr}"

            state.slots_offered[slot_name] = slot_value

            return UserAction(
                message=msg,
                internal_thought=f"告诉对方 {slot_name}",
                mood_delta=0.0,
            )

        # 3. 所有 slot 已提供，检查 bot 表示完成
        if "确认" in bot_response or "完成" in bot_response or "成功" in bot_response or "预订" in bot_response:
            return UserAction(
                message=self._pick(_THANKS_MESSAGES),
                internal_thought="任务完成",
                mood_delta=0.1,
                wants_to_continue=False,
            )

        # 4. bot 还在问/处理中 — 多样化催促或应答
        pending_keys = [k for k in state.slots_offered if k not in state.slots_confirmed]
        if pending_keys:
            # 第一次催促用催促语，后面交替催促和等待
            urge_count = sum(
                1 for t in state.history
                if any(u in t.user_message for u in ("帮我", "查查", "搜一下", "看看", "够了"))
            )
            if urge_count < 2:
                msg = self._pick(_URGE_MESSAGES)
            else:
                msg = self._pick(_WAIT_MESSAGES)
            return UserAction(
                message=msg,
                internal_thought="等待处理，信息已全",
                mood_delta=-0.03,
            )

        # 5. 默认通用应答
        return UserAction(
            message=self._pick(_WAIT_MESSAGES),
            internal_thought="等待 bot 继续",
        )


class LLMAssistedStrategy(BaseStrategy):
    """LLM 辅助的用户回复生成策略 — 通过 DeepSeek API 驱动角色扮演"""

    def __init__(self, llm_client: Any, model: str = "deepseek-chat") -> None:
        self._client = llm_client
        self._model = model

    async def generate_opening(
        self,
        persona: UserPersona,
        scenario: Scenario,
    ) -> UserAction:
        system_prompt = self._build_system_prompt(persona, scenario)
        user_prompt = (
            "现在开始对话。你刚联系上这个客服，请说第一句话。\n"
            "要求：\n"
            "- 根据你的性格自然开口，不要一次把所有信息全说完\n"
            "- 意图清晰度较高就直接说需求，较低就先模糊问问\n"
            "- 像真人打字一样，口语化、有停顿\n\n"
            "请只输出 JSON:\n"
            '{"message": "你说的话", "internal_thought": "你心里在想什么"}'
        )
        return await self._call_llm(system_prompt, [
            {"role": "user", "content": user_prompt},
        ])

    async def generate_reply(
        self,
        persona: UserPersona,
        scenario: Scenario,
        state: ConversationState,
        bot_response: str,
        triggered_injections: List[Injection] | None = None,
    ) -> UserAction:
        system_prompt = self._build_system_prompt(persona, scenario, state)

        # 构建完整对话历史作为 messages
        messages: list[dict[str, str]] = []
        for turn in state.history:
            messages.append({"role": "assistant", "content": turn.user_message})
            messages.append({"role": "user", "content": f"[客服回复] {turn.bot_response}"})

        # 当前轮的 user prompt
        parts: list[str] = []
        parts.append(f"客服刚刚说：\n「{bot_response}」\n")

        if triggered_injections:
            for inj in triggered_injections:
                change_parts = []
                for k, v in inj.state_changes.items():
                    localized = _localize_slot(k, v)
                    desc = _CHANGE_DESC.get(k, f"{k}改成{{v}}")
                    change_parts.append(desc.format(v=localized))
                if change_parts:
                    parts.append(f"⚠️ 你突然改主意了：{'，'.join(change_parts)}")
                else:
                    parts.append(f"⚠️ 发生了变化：{inj.description}")
                parts.append("请把这个变化自然地告诉客服。\n")

        # 提醒还没给的信息
        remaining = {
            k: v for k, v in scenario.user_goal.slots.items()
            if k not in state.slots_confirmed and k not in state.slots_offered
        }
        if remaining:
            slot_hints = ", ".join(f"{k}={_localize_slot(k, v)}" for k, v in remaining.items())
            parts.append(f"[提示：你还没告诉客服的信息：{slot_hints}，不需要一次全说，自然地透露]")

        parts.append(
            "\n请以角色身份回复客服。自然口语，不要像填表。\n"
            "只输出 JSON:\n"
            '{"message": "你说的话", "internal_thought": "你心里在想什么", '
            '"mood_delta": 0.0, "wants_to_continue": true}'
        )

        messages.append({"role": "user", "content": "\n".join(parts)})
        return await self._call_llm(system_prompt, messages)

    def _build_system_prompt(
        self,
        persona: UserPersona,
        scenario: Scenario,
        state: ConversationState | None = None,
    ) -> str:
        prompt = persona.to_system_prompt()
        prompt += f"\n## 你的目标\n你想要{scenario.user_goal.primary_intent}。\n"

        prompt += "\n## 你心里知道的信息（按需透露给客服，不要一次全说）\n"
        for slot, value in scenario.user_goal.slots.items():
            prompt += f"- {slot}: {_localize_slot(slot, value)}\n"

        if scenario.user_goal.hidden_constraints:
            prompt += "\n## 你不会主动说但心里在意的条件\n"
            for c in scenario.user_goal.hidden_constraints:
                prompt += f"- {c}\n"
            prompt += "（如果客服推荐的选项违反了这些条件，你要自然地拒绝，但不要直接说出条件本身）\n"

        if state:
            if state.slots_confirmed:
                confirmed = ", ".join(
                    f"{k}={_localize_slot(k, v)}" for k, v in state.slots_confirmed.items()
                )
                prompt += f"\n## 当前状态\n已确认的信息: {confirmed}\n"
            prompt += f"当前心情: {state.user_mood:.2f} (0=很差, 1=很好)\n"

        prompt += (
            "\n## 核心规则\n"
            "1. 你是一个普通用户，不是 AI，不是测试员\n"
            "2. 像真人在微信/电话上说话一样：口语化、有情绪、会跑题\n"
            "3. 不要用 \"好的\" \"嗯\" 之类敷衍，结合上下文自然回应\n"
            "4. 如果客服态度差或说脏话，你会生气/投诉\n"
            "5. 不要主动总结信息或列清单，像普通人那样聊\n"
            "6. 每次只输出 JSON，不要输出其他内容\n"
        )
        return prompt

    async def _call_llm(
        self, system_prompt: str, messages: list[dict[str, str]],
    ) -> UserAction:
        try:
            all_messages = [{"role": "system", "content": system_prompt}] + messages
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=all_messages,
                temperature=0.8,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            return UserAction(
                message=data.get("message", ""),
                internal_thought=data.get("internal_thought", ""),
                mood_delta=data.get("mood_delta", 0.0),
                wants_to_continue=data.get("wants_to_continue", True),
            )
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return UserAction(
                message="你好，请继续",
                internal_thought=f"LLM 调用失败: {exc}",
            )
