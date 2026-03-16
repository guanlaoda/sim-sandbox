"""上下文保持评测器 — 评估 Bot 在多轮中是否保持上下文一致"""

from __future__ import annotations

from ..models.evaluation import EvalDetail, EvaluationResult
from .base import BaseEvaluator, EvalContext


class ContextEvaluator(BaseEvaluator):
    dimension = "context"

    async def evaluate(self, ctx: EvalContext) -> EvaluationResult:
        details: list[EvalDetail] = []
        scores: list[float] = []

        turns = ctx.conversation.turns

        # 1. Slot 重复询问检测
        asked_slots: dict[str, int] = {}
        for turn in turns:
            bot_text = turn.bot_response.lower()
            for slot_name in ctx.scenario.user_goal.slots:
                if slot_name.lower() in bot_text:
                    asked_slots[slot_name] = asked_slots.get(slot_name, 0) + 1

        repeat_count = sum(1 for v in asked_slots.values() if v > 2)
        repeat_score = max(0.0, 1.0 - repeat_count * 0.2)
        details.append(
            EvalDetail(
                check_name="slot_repeat_question",
                passed=repeat_count == 0,
                score=round(repeat_score, 3),
                evidence=f"重复询问slots: {repeat_count}个, 详情: {asked_slots}",
            )
        )
        scores.append(repeat_score)

        # 2. Bot 自我矛盾检测 (简化版 — 检查确认后又变更)
        contradiction_flag = False
        last_confirmed: dict[str, str] = {}
        for turn in turns:
            snap = turn.state_snapshot or {}
            current_confirmed = snap.get("slots_confirmed", {})
            for k, v in current_confirmed.items():
                if k in last_confirmed and str(last_confirmed[k]) != str(v):
                    contradiction_flag = True
                    details.append(
                        EvalDetail(
                            check_name="contradiction",
                            passed=False,
                            score=0.0,
                            evidence=f"Slot '{k}' 从 {last_confirmed[k]} 变为 {v}",
                        )
                    )
            last_confirmed.update({k: str(v) for k, v in current_confirmed.items()})

        if not contradiction_flag:
            details.append(
                EvalDetail(
                    check_name="contradiction",
                    passed=True,
                    score=1.0,
                    evidence="未发现自我矛盾",
                )
            )
        scores.append(0.0 if contradiction_flag else 1.0)

        # 3. 整体 slot 最终确认率
        goal_slots = set(ctx.scenario.user_goal.slots.keys())
        final_confirmed = set(last_confirmed.keys())
        if goal_slots:
            final_rate = len(final_confirmed & goal_slots) / len(goal_slots)
        else:
            final_rate = 1.0

        details.append(
            EvalDetail(
                check_name="final_slot_confirmation",
                passed=final_rate >= 0.8,
                score=round(final_rate, 3),
                evidence=f"最终确认: {final_confirmed & goal_slots} / {goal_slots}",
            )
        )
        scores.append(final_rate)

        overall = sum(scores) / len(scores) if scores else 0.0
        return EvaluationResult(
            dimension="context",
            score=round(overall, 3),
            passed=overall >= 0.6,
            details=details,
        )
