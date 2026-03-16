"""Bot 适配器基类"""

from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BotResponse(BaseModel):
    """Bot 回复"""

    text: str = ""
    latency_ms: float = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: list = Field(default_factory=list)
    error: Optional[str] = None


class BaseBotAdapter(abc.ABC):
    """被测机器人适配器基类"""

    @abc.abstractmethod
    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> BotResponse:
        """发送消息并获取回复"""
        ...

    @abc.abstractmethod
    async def reset_session(self, session_id: str) -> None:
        """重置会话状态"""
        ...

    async def health_check(self) -> bool:
        """健康检查"""
        return True

    async def close(self) -> None:
        """释放资源"""
        pass
