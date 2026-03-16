"""Agent Tools — 可被 Deep Agents 框架调用的 @tool 函数集合

这些函数是确定性操作 (API 调用、数据读写、计算)，与 SKILL.md 知识互补。
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------- 内部状态存储 (进程内, 用于 tool 间通信) ----------
_sessions: Dict[str, Dict[str, Any]] = {}


def _load_state(session_id: str) -> Dict[str, Any]:
    return _sessions.setdefault(session_id, {})


def _save_state(session_id: str, state: Dict[str, Any]) -> None:
    _sessions[session_id] = state


# ================================================================
# 1. Persona 相关 Tools
# ================================================================


def sample_persona_skeleton(
    distribution_config: str,
    seed: int | None = None,
) -> str:
    """从给定的分布配置中采样一个 PersonaSkeleton。
    返回结构化的 JSON 骨架数据。

    Args:
        distribution_config: 分布配置的 YAML 内容或文件路径
        seed: 随机种子（可选）
    """
    from ..persona.generator import DistributionSampler

    sampler = DistributionSampler(distribution_config, seed=seed)
    skeleton = sampler.sample()
    return skeleton.model_dump_json(indent=2)


def validate_persona(persona_json: str) -> str:
    """校验一个 UserPersona 的完整性和自洽性。

    Args:
        persona_json: UserPersona 的 JSON 字符串
    """
    from ..models.persona import UserPersona

    issues: list[str] = []
    try:
        persona = UserPersona.model_validate_json(persona_json)
    except Exception as exc:
        return json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False)

    sk = persona.skeleton
    # 一致性检查
    if sk.tech_literacy < 0.3 and sk.communication_style.value == "formal":
        issues.append("低技术素养用户通常不会使用正式风格")
    if sk.patience_level < 0.3 and len(persona.language_habits) == 0:
        issues.append("低耐心用户应具有特征性口头禅")
    if not persona.name.strip():
        issues.append("姓名不能为空")
    if persona.age < 10 or persona.age > 100:
        issues.append(f"年龄异常: {persona.age}")

    return json.dumps(
        {"valid": len(issues) == 0, "issues": issues}, ensure_ascii=False
    )


def save_persona(persona_json: str, output_dir: str = "output/personas") -> str:
    """将 UserPersona 保存到文件。

    Args:
        persona_json: UserPersona 的 JSON 字符串
        output_dir: 输出目录
    """
    from ..models.persona import UserPersona

    persona = UserPersona.model_validate_json(persona_json)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{persona.skeleton.persona_id}.json"
    file_path.write_text(persona_json, encoding="utf-8")
    return json.dumps({"saved": str(file_path)}, ensure_ascii=False)


# ================================================================
# 2. Scenario 相关 Tools
# ================================================================


def load_scenario(scenario_path: str) -> str:
    """从 YAML 文件加载场景定义。

    Args:
        scenario_path: 场景 YAML 文件路径
    """
    from ..scenario.loader import ScenarioLoader

    loader = ScenarioLoader()
    scenario = loader.load_file(scenario_path)
    return scenario.model_dump_json(indent=2)


def validate_scenario(scenario_json: str) -> str:
    """校验场景定义的完整性。

    Args:
        scenario_json: Scenario 的 JSON 字符串
    """
    from ..models.scenario import Scenario

    issues: list[str] = []
    try:
        scenario = Scenario.model_validate_json(scenario_json)
    except Exception as exc:
        return json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False)

    if not scenario.user_goal.slots:
        issues.append("用户目标未定义任何 slot")
    if not scenario.user_goal.success_indicators:
        issues.append("缺少成功判定标志 success_indicators")
    if scenario.constraints.max_turns < 3:
        issues.append("最大轮次过少 (< 3)")

    return json.dumps(
        {"valid": len(issues) == 0, "issues": issues}, ensure_ascii=False
    )


def save_scenario(scenario_json: str, output_dir: str = "output/scenarios") -> str:
    """将 Scenario 保存到 YAML 文件。

    Args:
        scenario_json: Scenario 的 JSON 字符串
        output_dir: 输出目录
    """
    import yaml

    from ..models.scenario import Scenario

    scenario = Scenario.model_validate_json(scenario_json)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{scenario.scenario_id}.yaml"
    file_path.write_text(
        yaml.dump(
            scenario.model_dump(mode="json"),
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return json.dumps({"saved": str(file_path)}, ensure_ascii=False)


# ================================================================
# 3. Dialog Simulation 相关 Tools
# ================================================================


def send_to_bot(
    session_id: str,
    message: str,
    adapter_type: str = "mock",
) -> str:
    """发送用户消息到被测 Bot 并获取回复。
    测量响应延迟。

    Args:
        session_id: 会话唯一标识
        message: 用户消息
        adapter_type: 适配器类型 (mock/http)
    """
    import asyncio

    from ..adapters.mock_adapter import ScenarioMockBotAdapter

    state = _load_state(session_id)
    turn = state.get("turn_number", 0)

    start = time.monotonic()

    # 默认使用 mock adapter
    adapter = ScenarioMockBotAdapter(total_turns=20)

    async def _send() -> dict:
        resp = await adapter.send_message(session_id, message)
        return {
            "bot_response": resp.text,
            "latency_ms": resp.latency_ms,
            "metadata": resp.metadata,
            "tool_calls": resp.tool_calls,
            "error": resp.error,
        }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_send())
    finally:
        loop.close()

    latency = (time.monotonic() - start) * 1000
    result["latency_ms"] = round(latency, 1)

    return json.dumps(result, ensure_ascii=False)


def update_conversation_state(
    session_id: str,
    turn_analysis: str,
) -> str:
    """根据轮次分析结果更新会话状态。

    Args:
        session_id: 会话标识
        turn_analysis: JSON 字符串，包含 slot 更新、情绪变化、质量信号等
    """
    analysis = json.loads(turn_analysis)
    state = _load_state(session_id)

    # 更新 slots
    newly_confirmed = analysis.get("newly_confirmed_slots", {})
    confirmed = state.get("slots_confirmed", {})
    confirmed.update(newly_confirmed)
    state["slots_confirmed"] = confirmed

    # 更新 mood
    mood_delta = analysis.get("mood_delta", 0.0)
    current_mood = state.get("user_mood", 0.5)
    state["user_mood"] = max(0.0, min(1.0, current_mood + mood_delta))

    # 记录 quality issues
    issues = analysis.get("quality_issues", [])
    all_issues = state.get("quality_issues", [])
    all_issues.extend(issues)
    state["quality_issues"] = all_issues

    # 任务完成标志
    if analysis.get("task_completed"):
        state["is_task_complete"] = True

    _save_state(session_id, state)
    return json.dumps(
        {"status": "updated", "current_mood": state["user_mood"]},
        ensure_ascii=False,
    )


def check_termination(session_id: str) -> str:
    """检查对话是否应该终止。

    Args:
        session_id: 会话标识
    """
    state = _load_state(session_id)

    reasons = []
    max_turns = state.get("max_turns", 20)
    if state.get("turn_number", 0) >= max_turns:
        reasons.append("max_turns_reached")
    if state.get("is_task_complete"):
        reasons.append("task_completed")
    if state.get("user_mood", 0.5) < 0.1:
        reasons.append("user_quit_low_mood")

    # 简易循环检测
    history = state.get("history", [])
    if len(history) >= 4:
        recent = [h.get("user_message", "") for h in history[-4:]]
        if len(set(recent)) <= 1:
            reasons.append("conversation_loop")

    return json.dumps(
        {"should_terminate": len(reasons) > 0, "reasons": reasons},
        ensure_ascii=False,
    )


def check_injection_trigger(
    session_id: str,
    bot_response: str,
) -> str:
    """检查是否有注入事件应该触发。

    Args:
        session_id: 会话标识
        bot_response: Bot 的最新回复文本
    """
    state = _load_state(session_id)
    triggered = []

    for injection in state.get("pending_injections", []):
        trigger = injection.get("trigger", {})
        hit = False
        if trigger.get("at_turn") == state.get("turn_number"):
            hit = True
        elif trigger.get("when_slot_filled") in state.get("slots_confirmed", {}):
            hit = True
        elif trigger.get("when_keyword") and trigger["when_keyword"] in bot_response:
            hit = True

        if hit and random.random() < trigger.get("probability", 1.0):
            triggered.append(injection)

    # 移除已触发的注入
    for inj in triggered:
        if inj in state.get("pending_injections", []):
            state["pending_injections"].remove(inj)
    _save_state(session_id, state)

    return json.dumps(
        {"triggered": triggered, "count": len(triggered)},
        ensure_ascii=False,
    )


def intercept_tool_call(
    session_id: str,
    tool_name: str,
    tool_params: str,
) -> str:
    """拦截并模拟 Bot 的 tool 调用。
    在场景环境定义中查找匹配的 mock 响应。

    Args:
        session_id: 会话标识
        tool_name: Bot 尝试调用的 tool 名称
        tool_params: JSON 字符串的 tool 参数
    """
    state = _load_state(session_id)
    params = json.loads(tool_params)

    env = state.get("environment", {})
    for tool_def in env.get("tools_available", []):
        if tool_def.get("name") == tool_name:
            for mock in tool_def.get("mock_responses", []):
                condition = mock.get("condition", {})
                if all(
                    params.get(k) == v for k, v in condition.items()
                ):
                    return json.dumps(
                        {
                            "success": True,
                            "response": mock.get("response"),
                            "latency_ms": mock.get("latency_ms", 100),
                        },
                        ensure_ascii=False,
                    )

    return json.dumps(
        {"success": False, "error": f"No mock found for {tool_name}"},
        ensure_ascii=False,
    )


def save_conversation(
    session_id: str,
    output_dir: str = "output/conversations",
) -> str:
    """保存完整对话记录到文件。

    Args:
        session_id: 会话标识
        output_dir: 输出目录
    """
    state = _load_state(session_id)
    record = {
        "record_id": session_id,
        "scenario_id": state.get("scenario_id", "unknown"),
        "persona_id": state.get("persona_id", "unknown"),
        "turns": state.get("history", []),
        "termination_reason": state.get("termination_reason"),
        "total_bot_latency_ms": sum(
            t.get("bot_latency_ms", 0) for t in state.get("history", [])
        ),
    }

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{session_id}.json"
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps({"saved": str(file_path)}, ensure_ascii=False)


# ================================================================
# 4. Evaluation 相关 Tools
# ================================================================


def compute_metrics(
    conversation_json: str,
    scenario_json: str,
    dimensions: str = "accuracy,safety,performance,context,robustness",
) -> str:
    """计算对话评测指标（确定性部分）。

    Args:
        conversation_json: ConversationRecord JSON
        scenario_json: Scenario JSON
        dimensions: 逗号分隔的评测维度
    """
    conv = json.loads(conversation_json)
    scenario = json.loads(scenario_json)
    dims = [d.strip() for d in dimensions.split(",")]
    results: Dict[str, Any] = {}

    turns = conv.get("turns", [])

    if "performance" in dims:
        latencies = [t.get("bot_latency_ms", 0) for t in turns]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        results["performance"] = {
            "avg_latency_ms": round(avg_latency, 1),
            "max_latency_ms": max(latencies) if latencies else 0,
            "total_turns": len(turns),
        }

    if "accuracy" in dims:
        expected_calls = scenario.get("expected_skill_calls", [])
        actual_tools = set()
        for t in turns:
            for tc in t.get("bot_tool_calls", []):
                actual_tools.add(tc.get("tool_name", ""))
        expected_tools = {ec.get("tool_name", "") for ec in expected_calls}
        matched = expected_tools & actual_tools
        results["accuracy"] = {
            "expected_tools": list(expected_tools),
            "actual_tools": list(actual_tools),
            "tool_match_rate": len(matched) / len(expected_tools) if expected_tools else 1.0,
            "task_completed": conv.get("termination_reason") == "task_completed",
        }

    if "context" in dims:
        # 简单指标：检查 slot 确认率
        goal_slots = set(scenario.get("user_goal", {}).get("slots", {}).keys())
        confirmed = set()
        for t in turns:
            snap = t.get("state_snapshot", {})
            confirmed |= set(snap.get("slots_confirmed", {}).keys())
        results["context"] = {
            "slot_coverage": len(confirmed & goal_slots) / len(goal_slots) if goal_slots else 1.0,
            "total_goal_slots": len(goal_slots),
            "confirmed_slots": len(confirmed & goal_slots),
        }

    return json.dumps(results, ensure_ascii=False, indent=2)


def save_evaluation(
    evaluation_json: str,
    output_dir: str = "output/evaluations",
) -> str:
    """保存评测结果到文件。

    Args:
        evaluation_json: EvaluationResult / EvaluationReport JSON
        output_dir: 输出目录
    """
    data = json.loads(evaluation_json)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    eval_id = data.get("record_id", uuid.uuid4().hex[:12])
    file_path = out_path / f"{eval_id}.json"
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return json.dumps({"saved": str(file_path)}, ensure_ascii=False)
