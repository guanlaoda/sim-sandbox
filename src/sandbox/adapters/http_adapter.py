"""HTTP Bot 适配器 — 通过自定义 HTTP API 调用被测机器人"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from ..config import BotAdapterConfig
from .base import BaseBotAdapter, BotResponse

logger = logging.getLogger(__name__)


def _get_nested(data: dict, dotted_key: str) -> Any:
    """从嵌套 dict 中按点分路径取值, 如 'response.answer'"""
    keys = dotted_key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return None
    return current


def _set_nested(data: dict, dotted_key: str, value: Any) -> None:
    """向嵌套 dict 中按点分路径设值"""
    keys = dotted_key.split(".")
    current = data
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current[keys[-1]] = value


class HttpBotAdapter(BaseBotAdapter):
    """通过 HTTP API 调用被测 Bot"""

    def __init__(self, config: BotAdapterConfig) -> None:
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # 处理 headers 中的环境变量
            import os

            headers = {}
            for k, v in self.config.headers.items():
                if v.startswith("${") and v.endswith("}"):
                    headers[k] = os.environ.get(v[2:-1], "")
                else:
                    headers[k] = v

            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=timeout
            )
        return self._session

    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> BotResponse:
        session = await self._get_session()
        mapping = self.config.request_mapping

        # 构建请求体
        body: Dict[str, Any] = {}
        _set_nested(body, mapping.get("message_field", "query"), message)
        _set_nested(body, mapping.get("session_field", "session_id"), session_id)
        if context is not None:
            _set_nested(body, mapping.get("context_field", "history"), context)

        start = time.monotonic()

        for attempt in range(self.config.max_retries + 1):
            try:
                async with session.request(
                    self.config.method,
                    self.config.endpoint,
                    json=body,
                ) as resp:
                    latency_ms = (time.monotonic() - start) * 1000
                    resp_data = await resp.json()

                    resp_mapping = self.config.response_mapping
                    text = _get_nested(
                        resp_data, resp_mapping.get("text_field", "response")
                    )
                    metadata = (
                        _get_nested(
                            resp_data, resp_mapping.get("metadata_field", "")
                        )
                        or {}
                    )

                    return BotResponse(
                        text=str(text or ""),
                        latency_ms=round(latency_ms, 1),
                        metadata=metadata if isinstance(metadata, dict) else {},
                    )
            except Exception as exc:
                if attempt < self.config.max_retries:
                    logger.warning(
                        "Bot request failed (attempt %d/%d): %s",
                        attempt + 1,
                        self.config.max_retries + 1,
                        exc,
                    )
                    continue
                latency_ms = (time.monotonic() - start) * 1000
                return BotResponse(
                    latency_ms=round(latency_ms, 1),
                    error=str(exc),
                )

        return BotResponse(error="Max retries exceeded")

    async def reset_session(self, session_id: str) -> None:
        """HTTP 方式通常无需显式重置，由服务端管理"""
        pass

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(self.config.endpoint) as resp:
                return resp.status < 500
        except Exception:
            return False

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
