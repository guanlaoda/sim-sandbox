"""场景定义数据模型"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ADVERSARIAL = "adversarial"


class UserGoal(BaseModel):
    """用户目标 — 用户想达成什么"""

    primary_intent: str
    slots: Dict[str, Any] = Field(default_factory=dict)
    secondary_intents: List[str] = Field(default_factory=list)
    hidden_constraints: List[str] = Field(default_factory=list)
    success_indicators: List[str] = Field(default_factory=list)


class MockToolResponse(BaseModel):
    """Tool 模拟响应 — 根据输入条件返回预设结果"""

    condition: Dict[str, Any] = Field(default_factory=dict)
    response: Any = None
    latency_ms: int = 100
    error: Optional[str] = None


class ToolDefinition(BaseModel):
    """Bot 的 Tool/Skill 定义 — 用于模拟 Bot 可调用的能力"""

    name: str
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    mock_responses: List[MockToolResponse] = Field(default_factory=list)


class EnvironmentState(BaseModel):
    """模拟环境 — Bot 可查询到的外部世界状态"""

    data: Dict[str, Any] = Field(default_factory=dict)
    tools_available: List[ToolDefinition] = Field(default_factory=list)


class InjectionTrigger(BaseModel):
    """注入触发条件"""

    at_turn: Optional[int] = None
    when_slot_filled: Optional[str] = None
    when_keyword: Optional[str] = None
    probability: float = Field(default=1.0, ge=0, le=1)


class Injection(BaseModel):
    """对话注入事件 — 模拟中途变化"""

    trigger: InjectionTrigger
    event_type: str
    description: str
    state_changes: Dict[str, Any] = Field(default_factory=dict)
    user_mood_delta: float = 0.0


class ExpectedSkillCall(BaseModel):
    """期望 Bot 触发的 Skill/Tool 调用"""

    tool_name: str
    expected_params: Dict[str, Any] = Field(default_factory=dict)
    order: Optional[int] = None
    required: bool = True


class ScenarioConstraints(BaseModel):
    max_turns: int = 20
    max_duration_seconds: int = 300
    required_persona_traits: Dict[str, Any] = Field(default_factory=dict)


class ScenarioEvalConfig(BaseModel):
    accuracy_weight: float = 0.25
    safety_weight: float = 0.20
    context_weight: float = 0.20
    robustness_weight: float = 0.15
    performance_weight: float = 0.20
    custom_checks: List[Dict[str, Any]] = Field(default_factory=list)


class Scenario(BaseModel):
    """完整场景定义"""

    scenario_id: str
    name: str
    description: str = ""
    category: str = ""
    tags: List[str] = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    user_goal: UserGoal
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    injections: List[Injection] = Field(default_factory=list)
    constraints: ScenarioConstraints = Field(default_factory=ScenarioConstraints)
    expected_skill_calls: List[ExpectedSkillCall] = Field(default_factory=list)
    evaluation_config: ScenarioEvalConfig = Field(default_factory=ScenarioEvalConfig)
