"""评测器基类与上下文"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models.conversation import ConversationRecord
from ..models.evaluation import EvalDetail, EvaluationResult
from ..models.scenario import Scenario


@dataclass
class EvalContext:
    """评测上下文 — 传递给每个评测器"""

    conversation: ConversationRecord
    scenario: Scenario
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseEvaluator(abc.ABC):
    """评测器基类 — 每个维度实现一个子类"""

    dimension: str = "base"

    @abc.abstractmethod
    async def evaluate(self, ctx: EvalContext) -> EvaluationResult:
        """执行评测，返回该维度的评分结果"""
        ...
