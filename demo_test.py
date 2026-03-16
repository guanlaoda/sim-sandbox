"""端到端演示测试脚本"""

import asyncio
from pathlib import Path

from sandbox.config import PersonaGenerationConfig
from sandbox.persona.generator import PersonaGenerator
from sandbox.scenario.loader import ScenarioLoader
from sandbox.adapters.mock_adapter import MockBotAdapter
from sandbox.simulator.engine import DialogSimulator
from sandbox.simulator.strategies import RuleBasedStrategy
from sandbox.simulator.termination import TerminationChecker
from sandbox.evaluators.pipeline import EvaluationPipeline


def main():
    # ===== 1. 生成用户画像 =====
    print("=" * 60)
    print("步骤1: 生成用户画像")
    print("=" * 60)
    gen = PersonaGenerator(
        config=PersonaGenerationConfig(seed=42),
        project_root=Path.cwd(),
    )
    personas = gen.generate(count=1)
    persona = personas[0]
    print(f"  名字: {persona.name}")
    print(f"  年龄: {persona.age} ({persona.skeleton.age_group.value})")
    print(f"  职业: {persona.occupation}")
    print(f"  沟通风格: {persona.skeleton.communication_style.value}")
    print(f"  技术水平: {persona.skeleton.tech_literacy}")
    print(f"  耐心水平: {persona.skeleton.patience_level}")
    print(f"  意图清晰度: {persona.skeleton.intent_clarity}")
    print(f"  语言习惯: {persona.language_habits}")
    print(f"  情绪触发: {persona.emotional_triggers}")
    print()
    prompt = persona.to_system_prompt()
    print("  系统提示词 (前8行):")
    for line in prompt.split("\n")[:8]:
        print(f"    {line}")
    print()

    # ===== 2. 加载场景 =====
    print("=" * 60)
    print("步骤2: 加载测试场景")
    print("=" * 60)
    loader = ScenarioLoader(scenarios_dir="scenarios")
    scenario = loader.load_file("flight_booking/basic_booking.yaml")
    print(f"  场景ID: {scenario.scenario_id}")
    print(f"  场景名: {scenario.name}")
    print(f"  难度: {scenario.difficulty.value}")
    print(f"  用户目标: {scenario.user_goal.primary_intent}")
    print(f"  需确认slots: {list(scenario.user_goal.slots.keys())}")
    print(f"  成功标志: {scenario.user_goal.success_indicators}")
    print(f"  隐含约束: {scenario.user_goal.hidden_constraints}")
    print(f"  注入事件数: {len(scenario.injections)}")
    print(f"  最大轮次: {scenario.constraints.max_turns}")
    print()

    # ===== 3. 创建 Mock Bot 适配器 =====
    print("=" * 60)
    print("步骤3: 创建 Mock Bot 适配器")
    print("=" * 60)
    bot = MockBotAdapter(
        responses=[
            "您好！请问有什么可以帮您？",
            "好的，帮您查一下北京到上海的航班。找到4个航班：CA1234 国航 800元 08:00, MU5678 东航 650元 14:00, 9C8899 春秋 350元 22:30, CA5566 国航 2500元 10:00。您想选哪个？",
            "好的，您选择CA1234国航航班，2位乘客，总价1600元。请确认出发日期是2026-04-01对吗？",
            "已为您预订成功！订单号 ORD20260401001，CA1234 北京到上海 2026-04-01 08:00出发，2位乘客，总价1600元。祝您旅途愉快！",
        ],
        latency_range=(80, 200),
    )
    print(f"  预设回复数: {len(bot._responses)}")
    print(f"  模拟延迟: {bot._latency_range} ms")
    print()

    # ===== 4. 运行对话模拟 =====
    print("=" * 60)
    print("步骤4: 运行对话模拟")
    print("=" * 60)
    strategy = RuleBasedStrategy()
    termination = TerminationChecker(
        max_turns=scenario.constraints.max_turns,
        timeout_seconds=scenario.constraints.max_duration_seconds,
    )
    simulator = DialogSimulator(
        bot_adapter=bot,
        strategy=strategy,
        termination=termination,
    )

    record = asyncio.run(simulator.run(persona, scenario))

    print(f"  对话轮次: {len(record.turns)}")
    print(f"  终止原因: {record.termination_reason}")
    print(f"  总延迟: {record.total_bot_latency_ms:.0f} ms")
    print()
    print("  --- 对话记录 ---")
    for turn in record.turns:
        print(f"  [轮 {turn.turn_number}]")
        print(f"    用户: {turn.user_message}")
        if turn.user_internal_thought:
            print(f"    (内心: {turn.user_internal_thought})")
        bot_text = turn.bot_response
        if len(bot_text) > 100:
            bot_text = bot_text[:100] + "..."
        print(f"    Bot:  {bot_text}")
        confirmed = turn.state_snapshot.get("slots_confirmed", {})
        print(f"    延迟: {turn.bot_latency_ms:.0f}ms | 确认slots: {confirmed}")
        print()

    # ===== 5. 运行评测管线 =====
    print("=" * 60)
    print("步骤5: 运行评测管线")
    print("=" * 60)
    pipeline = EvaluationPipeline()
    report = asyncio.run(pipeline.evaluate(record, scenario))

    passed_str = "PASS" if report.overall_passed else "FAIL"
    print(f"  综合评分: {report.overall_score:.3f}")
    print(f"  是否通过: {passed_str}")
    print()
    print("  各维度评分:")
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"    [{status}] {result.dimension:12s} {result.score:.3f}")
        for d in result.details:
            ds = "+" if d.passed else "-"
            evidence = d.evidence[:65] if len(d.evidence) > 65 else d.evidence
            print(f"       {ds} {d.check_name}: {d.score:.2f} | {evidence}")
    print()
    print("=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
