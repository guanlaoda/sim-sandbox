"""测试: 评测管线"""

import pytest

from sandbox.evaluators.accuracy import AccuracyEvaluator
from sandbox.evaluators.base import EvalContext
from sandbox.evaluators.context import ContextEvaluator
from sandbox.evaluators.performance import PerformanceEvaluator
from sandbox.evaluators.pipeline import EvaluationPipeline
from sandbox.evaluators.robustness import RobustnessEvaluator
from sandbox.evaluators.safety import SafetyEvaluator
from sandbox.models.conversation import ConversationRecord, Turn
from sandbox.models.scenario import (
    EnvironmentState,
    Scenario,
    ScenarioConstraints,
    ScenarioEvalConfig,
    UserGoal,
)


def _make_context() -> EvalContext:
    scenario = Scenario(
        scenario_id="eval-test-001",
        name="评测测试",
        description="评测管线测试",
        category="test",
        difficulty="easy",
        user_goal=UserGoal(
            primary_intent="查询余额",
            slots={"account_id": "12345"},
            success_indicators=["余额为", "查询完成"],
        ),
        environment=EnvironmentState(data={"balance": 1000}),
        constraints=ScenarioConstraints(max_turns=10),
        evaluation_config=ScenarioEvalConfig(accuracy_weight=0.5, safety_weight=0.5),
    )

    record = ConversationRecord(
        record_id="rec-001",
        scenario_id="eval-test-001",
        persona_id="p-001",
        turns=[
            Turn(
                turn_number=1,
                user_message="我要查余额",
                bot_response="请提供账户ID",
                bot_latency_ms=200,
                state_snapshot={"slots_confirmed": {}, "user_mood": 0.6},
            ),
            Turn(
                turn_number=2,
                user_message="12345",
                bot_response="您的余额为1000元，查询完成",
                bot_latency_ms=150,
                state_snapshot={"slots_confirmed": {"account_id": "12345"}, "user_mood": 0.7},
            ),
        ],
        termination_reason="task_completed",
        total_bot_latency_ms=350,
    )

    return EvalContext(conversation=record, scenario=scenario)


class TestAccuracyEvaluator:
    @pytest.mark.asyncio
    async def test_task_completed(self) -> None:
        ctx = _make_context()
        evaluator = AccuracyEvaluator()
        result = await evaluator.evaluate(ctx)

        assert result.dimension == "accuracy"
        assert result.score > 0.5
        assert result.passed

    @pytest.mark.asyncio
    async def test_task_not_completed(self) -> None:
        ctx = _make_context()
        ctx.conversation.termination_reason = "max_turns"
        evaluator = AccuracyEvaluator()
        result = await evaluator.evaluate(ctx)

        # 没有完成任务，分数应该低一些
        assert result.score < 1.0


class TestSafetyEvaluator:
    @pytest.mark.asyncio
    async def test_clean_conversation(self) -> None:
        ctx = _make_context()
        evaluator = SafetyEvaluator()
        result = await evaluator.evaluate(ctx)

        assert result.dimension == "safety"
        assert result.score == 1.0
        assert result.passed


class TestPerformanceEvaluator:
    @pytest.mark.asyncio
    async def test_low_latency(self) -> None:
        ctx = _make_context()
        evaluator = PerformanceEvaluator(max_avg_latency_ms=1000)
        result = await evaluator.evaluate(ctx)

        assert result.dimension == "performance"
        assert result.score > 0.5


class TestEvaluationPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline(self) -> None:
        ctx = _make_context()
        pipeline = EvaluationPipeline()
        report = await pipeline.evaluate(ctx.conversation, ctx.scenario)

        assert report.record_id == "rec-001"
        assert len(report.results) == 5
        assert report.overall_score > 0
