---
name: persona-generation
description: >
  为对话仿真测试生成真实用户画像。
  当你需要创建虚拟用户来测试任务型聊天机器人时，使用此技能。
  接收画像骨架（采样属性），丰化为完整画像，包含背景故事、
  语言习惯、情绪触发点和典型表达方式。
license: MIT
metadata:
  author: sim-sandbox
  version: "1.0"
allowed-tools: sample_persona_skeleton validate_persona save_persona
---

# 用户画像生成

## 概述

本技能用于生成对话仿真所需的丰化用户画像，分两阶段执行：

1. **骨架采样** — 调用 `sample_persona_skeleton` 工具，根据配置的分布获取确定性属性值
2. **LLM 丰化** — 将骨架扩展为自洽的完整画像，包含性格、背景故事和行为模式

## 操作步骤

### 第一步：采样骨架

调用 `sample_persona_skeleton`，传入领域和分布配置：

```
sample_persona_skeleton(
    domain="航空出行服务",
    config_path="/config/personas/default_distribution.yaml",
    seed=42
)
```

返回结构化属性：
- age_group（年龄段）、tech_literacy（技术熟练度）、patience_level（耐心程度）、
  communication_style（沟通风格）、intent_clarity（意图清晰度）、domain_knowledge（领域知识）

### 第二步：丰化画像

基于骨架属性，生成以下丰化字段。所有字段必须与骨架属性**自洽**。

**必填字段：**
- `name` — 真实的中文姓名
- `age` — 在 age_group 范围内的具体年龄
- `occupation` — 与年龄和技术熟练度匹配的职业
- `personality_summary` — 2-3 句性格描述
- `background_story` — 简短背景故事，解释其特征来源
- `language_habits` — 3-5 个语言习惯/口头禅
  - tech_literacy < 0.3：使用非技术性、可能不精确的语言
  - communication_style == "verbose"：包含口头禅、重复、啰嗦
  - communication_style == "emotional"：包含感叹词、强调语气
- `emotional_triggers` — 什么会让此人沮丧/开心
- `typical_expressions` — 场景到表达方式的映射

**自洽规则：**
- 老年人 + 低技术水平 → 简单词汇，可能误用技术术语
- 低耐心 + 情绪化 → 容易抱怨，期望快速解决
- 高意图清晰度 → 直接说需求；低 → 绕弯子试探

### 第三步：校验

调用 `validate_persona` 检查自洽性。
如果校验失败，调整不一致的字段后重新校验。

### 第四步：保存

调用 `save_persona` 持久化画像，供仿真使用。

详细字段规格和取值范围见 [references/PERSONA-SCHEMA.md](references/PERSONA-SCHEMA.md)。
