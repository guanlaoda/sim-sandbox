# Scenario Schema 参考

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scenario_id | string | ✅ | 唯一标识 |
| name | string | ✅ | 场景名称 |
| description | string | | 场景描述 |
| category | string | | 分类 (如 flight_booking) |
| tags | list[string] | | 标签 |
| difficulty | enum | | easy/medium/hard/adversarial |
| user_goal | UserGoal | ✅ | 用户目标 |
| environment | Environment | ✅ | 模拟环境 |
| injections | list[Injection] | | 注入事件 |
| constraints | Constraints | | 约束条件 |
| expected_skill_calls | list | | 期望的 tool 调用序列 |
| evaluation_config | EvalConfig | | 评测权重配置 |

## UserGoal 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| primary_intent | string | 主意图 |
| slots | dict | 需要确认的槽位 |
| secondary_intents | list[string] | 附加意图 |
| hidden_constraints | list[string] | 隐含约束 |
| success_indicators | list[string] | 成功标志 |

## Environment 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| data | dict | 环境数据 |
| tools_available | list[ToolDef] | Bot 可用工具 |

## Injection 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| trigger.at_turn | int? | 在第 N 轮触发 |
| trigger.when_slot_filled | string? | 某槽位填充时触发 |
| trigger.when_keyword | string? | Bot 回复含关键词时触发 |
| trigger.probability | float | 触发概率 [0,1] |
| event_type | string | 事件类型 |
| description | string | 事件描述 |
| state_changes | dict | 状态变更 |
| user_mood_delta | float | 情绪变化量 |
