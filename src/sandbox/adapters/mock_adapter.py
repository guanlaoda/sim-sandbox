"""Mock Bot 适配器 — 用于框架自身测试"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List, Optional

from .base import BaseBotAdapter, BotResponse


class MockBotAdapter(BaseBotAdapter):
    """返回预设回复的 Mock Bot，用于测试仿真框架"""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        latency_range: tuple[float, float] = (50, 200),
        error_rate: float = 0.0,
    ) -> None:
        self._responses = responses or [
            "好的，我来帮您查一下。请问您的出发城市是哪里？",
            "已为您找到以下航班，请问选择哪一个？",
            "好的，已为您预订成功，订单号是 ORD20260401001。",
        ]
        self._latency_range = latency_range
        self._error_rate = error_rate
        self._sessions: Dict[str, int] = {}  # session_id → response index

    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> BotResponse:
        # 模拟延迟
        latency = random.uniform(*self._latency_range)
        await asyncio.sleep(latency / 1000)

        # 模拟随机错误
        if random.random() < self._error_rate:
            return BotResponse(latency_ms=latency, error="Simulated error")

        # 按顺序返回预设回复
        idx = self._sessions.get(session_id, 0)
        text = self._responses[min(idx, len(self._responses) - 1)]
        self._sessions[session_id] = idx + 1

        return BotResponse(text=text, latency_ms=round(latency, 1))

    async def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class ScenarioMockBotAdapter(BaseBotAdapter):
    """基于场景环境数据的 Mock Bot, 模拟 tool-calling 行为"""

    def __init__(self, environment_data: Dict[str, Any]) -> None:
        self._env = environment_data
        self._turn = 0

    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> BotResponse:
        self._turn += 1
        # 简单模拟: 根据 turn 返回不同阶段的回复
        if self._turn == 1:
            text = "好的，我来帮您处理。请您提供一些详细信息。"
        elif self._turn <= 3:
            text = "已收到您的信息，正在为您查询中..."
        else:
            text = "已为您处理完毕，请问还有其他需要帮助的吗？"

        return BotResponse(text=text, latency_ms=round(random.uniform(50, 150), 1))

    async def reset_session(self, session_id: str) -> None:
        self._turn = 0
