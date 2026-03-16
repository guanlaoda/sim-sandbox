"""对话记录数据模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """Bot 工具调用记录"""

    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    response: Any = None
    latency_ms: float = 0
    success: bool = True


class Turn(BaseModel):
    """单轮对话"""

    turn_number: int
    user_message: str
    user_internal_thought: str = ""
    bot_response: str = ""
    bot_latency_ms: float = 0
    bot_tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    skill_used: str = ""
    state_snapshot: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationState(BaseModel):
    """对话运行时状态 — 实时追踪"""

    turn_number: int = 0
    history: List[Turn] = Field(default_factory=list)
    slots_confirmed: Dict[str, Any] = Field(default_factory=dict)
    slots_pending: Dict[str, Any] = Field(default_factory=dict)
    slots_offered: Dict[str, Any] = Field(default_factory=dict)
    user_mood: float = Field(default=0.5, ge=0, le=1)
    pending_injections: List[Any] = Field(default_factory=list)
    bot_tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    is_task_complete: bool = False
    termination_reason: Optional[str] = None

    def get_recent_context(self, max_turns: int = 10) -> List[Turn]:
        """获取最近 N 轮用于 LLM 上下文"""
        return self.history[-max_turns:]

    def check_injection_triggers(
        self,
        bot_response: str,
        injections: list,
    ) -> list:
        """检查是否有注入事件被触发"""
        import random as _random

        triggered = []
        for injection in injections:
            trigger = injection.trigger
            if trigger.at_turn is not None and trigger.at_turn == self.turn_number:
                triggered.append(injection)
            elif (
                trigger.when_slot_filled
                and trigger.when_slot_filled in self.slots_confirmed
            ):
                triggered.append(injection)
            elif trigger.when_keyword and trigger.when_keyword in bot_response:
                triggered.append(injection)

        return [
            inj
            for inj in triggered
            if _random.random() < inj.trigger.probability
        ]


class ConversationRecord(BaseModel):
    """完整对话记录"""

    record_id: str
    run_id: str = ""
    scenario_id: str = ""
    persona_id: str = ""
    turns: List[Turn] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    termination_reason: str = ""
    total_bot_latency_ms: float = 0
    total_llm_skill_cost: float = 0
    final_state: Optional[ConversationState] = None
