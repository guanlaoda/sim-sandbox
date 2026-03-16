---
name: scenario-creation
description: >
  为任务型聊天机器人测试创建完整的对话测试场景。
  当你需要从简短描述生成新测试场景、或构建仿真框架所需的
  场景 YAML 文件时使用此技能。
  涵盖用户目标、环境搭建、工具 Mock 和注入事件。
license: MIT
metadata:
  author: sim-sandbox
  version: "1.0"
allowed-tools: load_scenario validate_scenario save_scenario
---

# 场景创建

## 概述

本技能用于创建对话仿真所需的完整测试场景。
一个场景定义了运行一次模拟对话所需的全部内容：
用户目标、环境状态、Mock 工具响应、以及对话中途注入事件。

## 场景结构

每个场景**必须**包含以下部分：

### 1. 用户目标 (`user_goal`)
- `primary_intent` — 用户想要达成什么
- `slots` — Bot 需要收集/确认的键值对
- `hidden_constraints` — 用户不会主动说、但会拒绝违反条件的选项
- `success_indicators` — 表示任务完成的信号关键词

### 2. 环境 (`environment`)
- `data` — 外部世界状态（航班列表、商品库存等）
- `tools_available` — Bot 可调用的工具/技能，每个包含：
  - `name`、`description`、`parameters`（JSON Schema）
  - `mock_responses` — 条件→响应映射，用于仿真

### 3. 注入事件 (`injections`) — 可选
对话中途的突发事件，测试 Bot 的应变能力：
- `trigger` — 何时触发（at_turn、when_slot_filled、when_keyword）
- `event_type` — 发生了什么（用户改主意、新信息、出错）
- `description` — 自然语言描述，供用户模拟器理解
- `state_changes` — 环境/目标状态如何变化

### 4. 期望工具调用 (`expected_skill_calls`)
Bot 应该调用的工具有序列表，含期望参数。
用于准确性评测。

### 5. 评测配置 (`evaluation_config`)
每个场景各评测维度的权重配置。

## 操作步骤

### 从简短描述创建：
1. 解析描述，识别意图、领域、复杂度
2. 设计 user_goal，包含合适的 slots 和隐含约束
3. 构建真实的环境数据来支撑场景
4. 中等及以上难度添加 1-2 个注入事件
5. 定义期望的工具调用序列
6. 调用 `validate_scenario` 检查完整性
7. 调用 `save_scenario` 持久化

### 从已有场景创建变体：
请使用 scenario-variation 技能。

完整字段规格见 [references/SCENARIO-SCHEMA.md](references/SCENARIO-SCHEMA.md)。

各领域示例场景见 [references/EXAMPLE-SCENARIOS.md](references/EXAMPLE-SCENARIOS.md)。
