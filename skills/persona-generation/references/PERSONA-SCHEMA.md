# Persona Schema 参考

## PersonaSkeleton 字段

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| persona_id | string | UUID hex[:8] | 唯一标识 |
| age_group | enum | young/middle/senior | 年龄段 |
| tech_literacy | float | [0, 1] | 技术素养 |
| patience_level | float | [0, 1] | 耐心程度 |
| communication_style | enum | concise/verbose/emotional/formal | 沟通风格 |
| intent_clarity | float | [0, 1] | 表达意图的清晰度 |
| domain_knowledge | dict | {domain: float} | 领域知识水平 |

## UserPersona 丰化字段

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 中文姓名 |
| age | int | 具体年龄 (与 age_group 匹配) |
| occupation | string | 职业 |
| personality_summary | string | 2-3 句话性格描述 |
| background_story | string | 背景故事 |
| language_habits | list[string] | 3-5 个口头禅/语言习惯 |
| emotional_triggers | list[string] | 情绪触发条件 |
| typical_expressions | dict[string, string] | 场景→典型表达方式 |

## Age Group 映射

- **young**: 18-35 岁
- **middle**: 36-55 岁
- **senior**: 56-75 岁

## 一致性约束矩阵

| 条件 | 影响 |
|------|------|
| senior + tech_literacy < 0.3 | language_habits 必须包含非技术性表达 |
| young + tech_literacy > 0.7 | 可使用网络用语 |
| patience_level < 0.3 | emotional_triggers 应包含等待相关 |
| communication_style=formal | language_habits 不可包含口语化表达 |
