"""准确性评测器 — 评估 Bot 是否达成了用户目标"""

from __future__ import annotations

from ..models.evaluation import EvalDetail, EvaluationResult
from .base import BaseEvaluator, EvalContext


class AccuracyEvaluator(BaseEvaluator):
    dimension = "accuracy"

    async def evaluate(self, ctx: EvalContext) -> EvaluationResult:
        details: list[EvalDetail] = []
        score_parts: list[float] = []

        goal = ctx.scenario.user_goal
        conv = ctx.conversation

        # 1. 任务完成度
        task_done = conv.termination_reason == "task_completed"
        details.append(
            EvalDetail(
                check_name="task_completion",
                passed=task_done,
                score=1.0 if task_done else 0.0,
                evidence=f"termination_reason={conv.termination_reason}",
            )
        )
        score_parts.append(1.0 if task_done else 0.0)

        # 2. Slot 确认覆盖率
        goal_slots = set(goal.slots.keys())
        confirmed_slots: set[str] = set()
        for turn in conv.turns:
            if turn.state_snapshot:
                confirmed_slots |= set(
                    turn.state_snapshot.get("slots_confirmed", {}).keys()
                )

        if goal_slots:
            coverage = len(confirmed_slots & goal_slots) / len(goal_slots)
        else:
            coverage = 1.0

        details.append(
            EvalDetail(
                check_name="slot_coverage",
                passed=coverage >= 0.8,
                score=coverage,
                evidence=f"confirmed={confirmed_slots & goal_slots}, total={goal_slots}",
            )
        )
        score_parts.append(coverage)

        # 3. 期望 tool 调用匹配
        expected_calls = ctx.scenario.expected_skill_calls
        actual_tools: set[str] = set()
        for turn in conv.turns:
            for tc in turn.bot_tool_calls:
                actual_tools.add(tc.tool_name)

        if expected_calls:
            required = [ec for ec in expected_calls if ec.required]
            matched = sum(1 for ec in required if ec.tool_name in actual_tools)
            tool_rate = matched / len(required) if required else 1.0
        else:
            tool_rate = 1.0

        details.append(
            EvalDetail(
                check_name="expected_tool_calls",
                passed=tool_rate >= 0.8,
                score=tool_rate,
                evidence=f"actual={actual_tools}",
            )
        )
        score_parts.append(tool_rate)

        overall = sum(score_parts) / len(score_parts) if score_parts else 0.0
        return EvaluationResult(
            dimension="accuracy",
            score=round(overall, 3),
            passed=overall >= 0.6,
            details=details,
        )
