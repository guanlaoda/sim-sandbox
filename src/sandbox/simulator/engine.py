"""对话模拟引擎 — 核心对话循环"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..adapters.base import BaseBotAdapter
from ..models.conversation import ConversationRecord, ConversationState, ToolCallRecord, Turn
from ..models.persona import UserPersona
from ..models.scenario import Injection, Scenario
from .strategies import BaseStrategy, UserAction
from .termination import TerminationChecker

logger = logging.getLogger(__name__)


class DialogSimulator:
    """对话模拟器

    负责驱动一次完整的多轮对话模拟:
    1. 生成用户开场白
    2. 发送到 bot, 获取回复
    3. 分析回复, 更新 state
    4. 检查注入事件
    5. 检查终止条件
    6. 生成下一轮用户消息
    7. 重复直到终止
    """

    def __init__(
        self,
        bot_adapter: BaseBotAdapter,
        strategy: BaseStrategy,
        termination: TerminationChecker,
    ) -> None:
        self._bot = bot_adapter
        self._strategy = strategy
        self._termination = termination

    async def run(
        self,
        persona: UserPersona,
        scenario: Scenario,
        session_id: str | None = None,
    ) -> ConversationRecord:
        """执行一次完整的对话模拟"""
        session_id = session_id or uuid.uuid4().hex[:12]
        started_at = datetime.now()

        state = ConversationState(
            turn_number=0,
            history=[],
            slots_confirmed={},
            slots_pending=dict(scenario.user_goal.slots),
            user_mood=0.6,
            pending_injections=list(scenario.injections),
            bot_tool_calls=[],
            is_task_complete=False,
        )

        logger.info(
            "Simulation started — session=%s scenario=%s persona=%s",
            session_id,
            scenario.scenario_id,
            persona.skeleton.persona_id,
        )

        # 1. 用户开场白
        opening = await self._strategy.generate_opening(persona, scenario)
        if opening.terminate:
            return self._build_record(session_id, persona, scenario, state, started_at, "user_abort")

        # 对话循环
        user_message = opening.message
        internal_thought = opening.internal_thought
        state.user_mood = max(0.0, min(1.0, state.user_mood + opening.mood_delta))

        while True:
            state.turn_number += 1

            # 2. 发送到 bot
            bot_resp = await self._bot.send_message(session_id, user_message)
            if bot_resp.error:
                logger.warning("Bot error at turn %d: %s", state.turn_number, bot_resp.error)
                if bot_resp.error == "user_quit":
                    state.termination_reason = "user_quit"
                    return self._build_record(
                        session_id, persona, scenario, state, started_at, "user_quit"
                    )

            # 3. 简易的回复分析 — 提取 slot 确认信号
            newly_confirmed = self._extract_slot_confirmations(
                bot_resp.text, user_message, state.slots_pending, state.slots_offered,
                has_error=bool(bot_resp.error),
            )
            for slot in newly_confirmed:
                val = state.slots_pending.pop(slot, None) or state.slots_offered.pop(slot, None)
                state.slots_confirmed[slot] = val

            # 记录 bot tool calls
            tool_calls: list[ToolCallRecord] = []
            if bot_resp.tool_calls:
                for tc in bot_resp.tool_calls:
                    tool_calls.append(
                        ToolCallRecord(
                            tool_name=tc.get("name", "unknown"),
                            params=tc.get("parameters", {}),
                            response=tc.get("result"),
                        )
                    )
                    state.bot_tool_calls.append(tc.get("name", "unknown"))

            # 检测任务完成
            if self._detect_task_completion(bot_resp.text, scenario):
                state.is_task_complete = True

            # 记录本轮 Turn
            turn = Turn(
                turn_number=state.turn_number,
                user_message=user_message,
                user_internal_thought=internal_thought,
                bot_response=bot_resp.text,
                bot_latency_ms=bot_resp.latency_ms,
                bot_tool_calls=tool_calls,
                state_snapshot={
                    "slots_confirmed": dict(state.slots_confirmed),
                    "user_mood": state.user_mood,
                    "is_task_complete": state.is_task_complete,
                },
            )
            state.history.append(turn)

            # 4. 检查注入事件
            triggered_injections = state.check_injection_triggers(
                bot_resp.text, state.pending_injections
            )
            applied: list[Injection] = []
            for inj in triggered_injections:
                state.user_mood = max(0.0, min(1.0, state.user_mood + inj.user_mood_delta))
                applied.append(inj)
                state.pending_injections.remove(inj)

            # 5. 检查终止条件
            term_result = self._termination.check(state)
            if term_result.should_terminate:
                reason = ", ".join(term_result.reasons)
                logger.info("Termination at turn %d: %s", state.turn_number, reason)
                state.termination_reason = reason
                return self._build_record(session_id, persona, scenario, state, started_at, reason)

            # 6. 生成下一轮用户消息
            action = await self._strategy.generate_reply(
                persona=persona,
                scenario=scenario,
                state=state,
                bot_response=bot_resp.text,
                triggered_injections=applied if applied else None,
            )

            state.user_mood = max(0.0, min(1.0, state.user_mood + action.mood_delta))
            user_message = action.message
            internal_thought = action.internal_thought

            if action.terminate or not action.wants_to_continue:
                state.termination_reason = "user_quit"
                return self._build_record(
                    session_id, persona, scenario, state, started_at, "user_quit"
                )

    # ---- helpers ----

    _ACKNOWLEDGE_KEYWORDS = (
        "好的", "了解", "收到", "明白", "已", "没问题", "帮您",
        "知道了", "记录", "确认",
    )

    @classmethod
    def _extract_slot_confirmations(
        cls,
        bot_text: str,
        user_text: str,
        pending_slots: Dict[str, Any],
        offered_slots: Dict[str, Any],
        *,
        has_error: bool = False,
    ) -> list[str]:
        """检测 slot 确认: bot 回复含 slot 值，或 bot 确认了用户提供的 slot"""
        confirmed = []
        # 方式1: bot 回复直接包含 slot value
        for slot_name, slot_value in pending_slots.items():
            value_str = str(slot_value)
            if value_str and value_str in bot_text:
                confirmed.append(slot_name)
        # 方式2: 用户提供了 slot 值且 bot 给了非错误回应
        if not has_error:
            bot_ack = any(kw in bot_text for kw in cls._ACKNOWLEDGE_KEYWORDS)
            for slot_name, slot_value in list(offered_slots.items()):
                if slot_name not in confirmed:
                    if bot_ack or str(slot_value) in bot_text:
                        confirmed.append(slot_name)
        return confirmed

    @staticmethod
    def _detect_task_completion(bot_text: str, scenario: Scenario) -> bool:
        """检查是否命中任何 success_indicators"""
        for indicator in scenario.user_goal.success_indicators:
            if indicator in bot_text:
                return True
        return False

    @staticmethod
    def _build_record(
        session_id: str,
        persona: UserPersona,
        scenario: Scenario,
        state: ConversationState,
        started_at: datetime,
        termination_reason: str,
    ) -> ConversationRecord:
        total_latency = sum(
            t.bot_latency_ms for t in state.history if t.bot_latency_ms
        )
        return ConversationRecord(
            record_id=session_id,
            scenario_id=scenario.scenario_id,
            persona_id=persona.skeleton.persona_id,
            turns=state.history,
            termination_reason=termination_reason,
            total_bot_latency_ms=total_latency,
            started_at=started_at,
            finished_at=datetime.now(),
        )
