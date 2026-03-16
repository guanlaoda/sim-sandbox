"""性能评测器 — 评估 Bot 响应延迟和对话效率"""

from __future__ import annotations

from ..models.evaluation import EvalDetail, EvaluationResult
from .base import BaseEvaluator, EvalContext


class PerformanceEvaluator(BaseEvaluator):
    dimension = "performance"

    def __init__(
        self,
        max_avg_latency_ms: float = 3000.0,
        max_single_latency_ms: float = 10000.0,
        ideal_turns_ratio: float = 1.5,
    ) -> None:
        self._max_avg = max_avg_latency_ms
        self._max_single = max_single_latency_ms
        self._ideal_ratio = ideal_turns_ratio

    async def evaluate(self, ctx: EvalContext) -> EvaluationResult:
        details: list[EvalDetail] = []
        scores: list[float] = []

        turns = ctx.conversation.turns
        if not turns:
            return EvaluationResult(
                dimension="performance", score=0.0, passed=False, details=[]
            )

        # 1. 平均响应延迟
        latencies = [t.bot_latency_ms for t in turns if t.bot_latency_ms]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        lat_score = max(0.0, 1.0 - avg_lat / self._max_avg)
        details.append(
            EvalDetail(
                check_name="avg_latency",
                passed=avg_lat <= self._max_avg,
                score=round(lat_score, 3),
                evidence=f"avg={avg_lat:.0f}ms, threshold={self._max_avg}ms",
            )
        )
        scores.append(lat_score)

        # 2. 最大单次延迟
        max_lat = max(latencies) if latencies else 0
        max_score = max(0.0, 1.0 - max_lat / self._max_single)
        details.append(
            EvalDetail(
                check_name="max_latency",
                passed=max_lat <= self._max_single,
                score=round(max_score, 3),
                evidence=f"max={max_lat:.0f}ms, threshold={self._max_single}ms",
            )
        )
        scores.append(max_score)

        # 3. 对话效率 — 实际轮次 vs 最少所需轮次 (slot 数量)
        min_turns = max(len(ctx.scenario.user_goal.slots), 2)
        ideal_max = min_turns * self._ideal_ratio
        actual_turns = len(turns)
        if actual_turns <= ideal_max:
            eff_score = 1.0
        else:
            eff_score = max(0.0, 1.0 - (actual_turns - ideal_max) / ideal_max)

        details.append(
            EvalDetail(
                check_name="turn_efficiency",
                passed=actual_turns <= ideal_max,
                score=round(eff_score, 3),
                evidence=f"actual={actual_turns}, ideal_max={ideal_max:.0f}",
            )
        )
        scores.append(eff_score)

        overall = sum(scores) / len(scores)
        return EvaluationResult(
            dimension="performance",
            score=round(overall, 3),
            passed=overall >= 0.5,
            details=details,
        )
