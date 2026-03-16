"""终止条件判定"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..models.conversation import ConversationState, Turn


@dataclass
class TerminationResult:
    """终止判定结果"""

    should_terminate: bool = False
    reasons: List[str] = field(default_factory=list)


class TerminationChecker:
    """多条件终止判定"""

    def __init__(
        self,
        max_turns: int = 20,
        timeout_seconds: int = 300,
        start_time: float | None = None,
    ) -> None:
        self._max_turns = max_turns
        self._timeout_seconds = timeout_seconds
        self._start_time = start_time or time.monotonic()

    def check(self, state: ConversationState) -> TerminationResult:
        """检查是否应该终止"""
        reasons: list[str] = []

        if state.turn_number >= self._max_turns:
            reasons.append("max_turns")

        elapsed = time.monotonic() - self._start_time
        if elapsed > self._timeout_seconds:
            reasons.append("timeout")

        if state.is_task_complete:
            reasons.append("task_completed")

        if state.user_mood < 0.1:
            reasons.append("user_quit_low_mood")

        if self._detect_loop(state.history):
            reasons.append("conversation_loop")

        return TerminationResult(
            should_terminate=bool(reasons),
            reasons=reasons,
        )

    @staticmethod
    def _detect_loop(
        history: list[Turn],
        window: int = 4,
        threshold: float = 0.8,
    ) -> bool:
        """检测对话是否陷入循环 (最近 N 轮重复度过高)"""
        if len(history) < window * 2:
            return False

        recent = [t.bot_response for t in history[-window:]]
        earlier = [t.bot_response for t in history[-window * 2 : -window]]

        if not recent or not earlier:
            return False

        # 简单相似度: 完全匹配的比例
        matches = sum(1 for r, e in zip(recent, earlier) if r == e)
        return (matches / window) >= threshold
