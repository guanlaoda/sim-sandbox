"""评测管线 — 串联多个维度评测器"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..models.conversation import ConversationRecord
from ..models.evaluation import EvaluationReport, EvaluationResult
from ..models.scenario import Scenario
from .base import BaseEvaluator, EvalContext

logger = logging.getLogger(__name__)

# 默认维度权重
DEFAULT_WEIGHTS: Dict[str, float] = {
    "accuracy": 0.30,
    "safety": 0.20,
    "context": 0.20,
    "robustness": 0.15,
    "performance": 0.15,
}


class EvaluationPipeline:
    """评测管线 — 对一次对话记录执行多维度评测"""

    def __init__(
        self,
        evaluators: List[BaseEvaluator] | None = None,
        weights: Dict[str, float] | None = None,
    ) -> None:
        self._evaluators = evaluators or self._default_evaluators()
        self._weights = weights or DEFAULT_WEIGHTS

    @staticmethod
    def _default_evaluators() -> List[BaseEvaluator]:
        from .accuracy import AccuracyEvaluator
        from .context import ContextEvaluator
        from .performance import PerformanceEvaluator
        from .robustness import RobustnessEvaluator
        from .safety import SafetyEvaluator

        return [
            AccuracyEvaluator(),
            SafetyEvaluator(),
            PerformanceEvaluator(),
            ContextEvaluator(),
            RobustnessEvaluator(),
        ]

    async def evaluate(
        self,
        conversation: ConversationRecord,
        scenario: Scenario,
    ) -> EvaluationReport:
        """执行全部维度评测并生成报告"""
        ctx = EvalContext(conversation=conversation, scenario=scenario)
        results: List[EvaluationResult] = []

        for evaluator in self._evaluators:
            try:
                result = await evaluator.evaluate(ctx)
                results.append(result)
                logger.info(
                    "Evaluated %s: score=%.3f passed=%s",
                    result.dimension,
                    result.score,
                    result.passed,
                )
            except Exception as exc:
                logger.error("Evaluator %s failed: %s", evaluator.dimension, exc)
                results.append(
                    EvaluationResult(
                        dimension=evaluator.dimension,
                        score=0.0,
                        passed=False,
                        details=[],
                    )
                )

        report = EvaluationReport(
            record_id=conversation.record_id,
            scenario_id=conversation.scenario_id,
            results=results,
            dimension_weights=self._weights,
        )
        report.compute_overall()
        return report
