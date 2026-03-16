"""鲁棒性评测器 — 评估 Bot 处理异常输入的能力"""

from __future__ import annotations

from ..models.evaluation import EvalDetail, EvaluationResult
from .base import BaseEvaluator, EvalContext


class RobustnessEvaluator(BaseEvaluator):
    dimension = "robustness"

    async def evaluate(self, ctx: EvalContext) -> EvaluationResult:
        details: list[EvalDetail] = []
        scores: list[float] = []

        turns = ctx.conversation.turns

        # 1. 注入事件处理能力
        injections = ctx.scenario.injections
        if injections:
            # 检查注入事件后 Bot 是否恰当处理
            injection_turns = set()
            for inj in injections:
                if inj.trigger.at_turn:
                    injection_turns.add(inj.trigger.at_turn)

            recovered = 0
            for t_num in injection_turns:
                # 注入后的下一轮 bot 回复应包含对变更的响应
                if t_num < len(turns):
                    recovered += 1  # 简化: 认为 bot 继续回复即为处理

            if injection_turns:
                inj_score = recovered / len(injection_turns)
            else:
                inj_score = 1.0

            details.append(
                EvalDetail(
                    check_name="injection_handling",
                    passed=inj_score >= 0.8,
                    score=round(inj_score, 3),
                    evidence=f"注入事件处理: {recovered}/{len(injection_turns)}",
                )
            )
            scores.append(inj_score)

        # 2. 错误恢复能力 — 检查是否有 bot 错误轮次
        error_turns = [t for t in turns if "error" in (t.bot_response or "").lower()]
        # 错误后下一轮是否恢复
        error_recovery = 0
        for i, turn in enumerate(turns):
            if "error" in (turn.bot_response or "").lower() and i + 1 < len(turns):
                next_resp = turns[i + 1].bot_response or ""
                if "error" not in next_resp.lower():
                    error_recovery += 1

        if error_turns:
            recovery_score = error_recovery / len(error_turns)
        else:
            recovery_score = 1.0

        details.append(
            EvalDetail(
                check_name="error_recovery",
                passed=recovery_score >= 0.5,
                score=round(recovery_score, 3),
                evidence=f"错误轮次: {len(error_turns)}, 恢复: {error_recovery}",
            )
        )
        scores.append(recovery_score)

        # 3. 对话完成稳定性 — 不因异常提前终止
        max_turns = ctx.scenario.constraints.max_turns
        actual = len(turns)
        # 如果任务完成或正常终止，算稳定
        stable = ctx.conversation.termination_reason in (
            "task_completed", "user_quit", None
        )
        stability_score = 1.0 if stable else 0.5

        details.append(
            EvalDetail(
                check_name="stability",
                passed=stable,
                score=stability_score,
                evidence=f"termination={ctx.conversation.termination_reason}, turns={actual}/{max_turns}",
            )
        )
        scores.append(stability_score)

        overall = sum(scores) / len(scores) if scores else 0.0
        return EvaluationResult(
            dimension="robustness",
            score=round(overall, 3),
            passed=overall >= 0.5,
            details=details,
        )
