"""测试: 对话模拟器"""

import pytest
import asyncio

from sandbox.adapters.mock_adapter import MockBotAdapter
from sandbox.models.persona import (
    AgeGroup,
    CommunicationStyle,
    PersonaSkeleton,
    UserPersona,
)
from sandbox.models.scenario import (
    Scenario,
    ScenarioConstraints,
    ScenarioEvalConfig,
    UserGoal,
    EnvironmentState,
)
from sandbox.simulator.engine import DialogSimulator
from sandbox.simulator.strategies import RuleBasedStrategy
from sandbox.simulator.termination import TerminationChecker


def _make_persona() -> UserPersona:
    return UserPersona(
        skeleton=PersonaSkeleton(
            persona_id="test-p001",
            age_group=AgeGroup.MIDDLE,
            tech_literacy=0.7,
            patience_level=0.6,
            communication_style=CommunicationStyle.CONCISE,
            intent_clarity=0.8,
        ),
        name="张三",
        age=35,
        occupation="工程师",
        personality_summary="一个务实的中年工程师",
        background_story="普通上班族",
        language_habits=["嗯", "好的"],
        emotional_triggers=["等待太久"],
        typical_expressions={"greeting": "你好"},
    )


def _make_scenario() -> Scenario:
    return Scenario(
        scenario_id="sim-test-001",
        name="测试场景",
        description="简单测试",
        category="test",
        difficulty="easy",
        user_goal=UserGoal(
            primary_intent="查询余额",
            slots={"account_id": "12345"},
            success_indicators=["余额", "完成"],
        ),
        environment=EnvironmentState(data={"balance": 1000}),
        constraints=ScenarioConstraints(max_turns=5, max_duration_seconds=60),
        evaluation_config=ScenarioEvalConfig(accuracy_weight=0.5, safety_weight=0.5),
    )


class TestDialogSimulator:
    @pytest.mark.asyncio
    async def test_basic_simulation(self) -> None:
        persona = _make_persona()
        scenario = _make_scenario()
        adapter = MockBotAdapter(
            responses=[
                "您好，请提供您的账户ID",
                "您的余额为1000元，完成查询",
            ]
        )
        strategy = RuleBasedStrategy()
        termination = TerminationChecker(max_turns=5)

        simulator = DialogSimulator(
            bot_adapter=adapter,
            strategy=strategy,
            termination=termination,
        )

        record = await simulator.run(persona, scenario)

        assert record is not None
        assert record.scenario_id == "sim-test-001"
        assert record.persona_id == "test-p001"
        assert len(record.turns) >= 1

    @pytest.mark.asyncio
    async def test_terminates_at_max_turns(self) -> None:
        persona = _make_persona()
        scenario = _make_scenario()
        # 总是返回同样的回复, 不触发完成
        adapter = MockBotAdapter(responses=["请稍等..."])
        strategy = RuleBasedStrategy()
        termination = TerminationChecker(max_turns=3)

        simulator = DialogSimulator(
            bot_adapter=adapter,
            strategy=strategy,
            termination=termination,
        )

        record = await simulator.run(persona, scenario)

        assert len(record.turns) <= 3
        assert "max_turns" in record.termination_reason


class TestTerminationChecker:
    def test_max_turns(self) -> None:
        from sandbox.models.conversation import ConversationState

        checker = TerminationChecker(max_turns=5)
        state = ConversationState(turn_number=5)
        result = checker.check(state)
        assert result.should_terminate
        assert "max_turns" in result.reasons

    def test_task_completed(self) -> None:
        from sandbox.models.conversation import ConversationState

        checker = TerminationChecker(max_turns=20)
        state = ConversationState(turn_number=3, is_task_complete=True)
        result = checker.check(state)
        assert result.should_terminate
        assert "task_completed" in result.reasons

    def test_not_terminated_early(self) -> None:
        from sandbox.models.conversation import ConversationState

        checker = TerminationChecker(max_turns=20)
        state = ConversationState(turn_number=2, user_mood=0.5)
        result = checker.check(state)
        assert not result.should_terminate
