"""Bot 适配器"""

from .base import BaseBotAdapter, BotResponse
from .http_adapter import HttpBotAdapter
from .human_adapter import HumanBotAdapter
from .mock_adapter import MockBotAdapter, ScenarioMockBotAdapter

__all__ = [
    "BaseBotAdapter",
    "BotResponse",
    "HttpBotAdapter",
    "HumanBotAdapter",
    "MockBotAdapter",
    "ScenarioMockBotAdapter",
]
