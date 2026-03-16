"""人工 Bot 适配器 — 由真人在终端扮演 Bot 回复"""

from __future__ import annotations

import time

from rich.console import Console

from .base import BaseBotAdapter, BotResponse

console = Console()


class HumanBotAdapter(BaseBotAdapter):
    """人工交互适配器：在终端等待真人输入 Bot 回复"""

    def __init__(self, show_user_message: bool = True) -> None:
        self._show_user = show_user_message

    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> BotResponse:
        if self._show_user:
            console.print(f"  [green]👤 用户:[/green] {message}")
            console.print()
        start = time.perf_counter()
        text = console.input("[bold blue]🤖 你的回复> [/bold blue]")
        elapsed_ms = (time.perf_counter() - start) * 1000
        return BotResponse(text=text.strip(), latency_ms=round(elapsed_ms, 1))

    async def reset_session(self, session_id: str) -> None:
        pass
