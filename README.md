# 对话大模型机器人仿真沙盒框架

> **Sim-Sandbox** — 一个 LLM-Driven 的对话机器人自动化测试框架，基于 Deep Agents 架构。

## 概述

本框架用于端到端测试对话大模型机器人（Chatbot），通过 **LLM 驱动的虚拟用户** 与被测 Bot 进行多轮真实感对话，并从多个维度自动评测 Bot 的表现。

### 核心架构

```
┌──────────────────────────────────────────┐
│            Main Orchestrator             │
│      (sim-orchestrator, Claude)          │
├──────────┬──────────┬──────────┬─────────┤
│persona-  │scenario- │dialog-   │evaluator│
│gen       │gen       │simulator │         │
│(DeepSeek │(DeepSeek │(DeepSeek │(DeepSeek│
│ V3)      │ V3)      │ V3)      │ V3)     │
└──────────┴──────────┴──────────┴─────────┘
     ↓           ↓          ↓          ↓
  Skills     Skills     Skills     Skills
  + Tools    + Tools    + Tools    + Tools
```

**设计原则**:
- **Skills** = 领域知识 + 指令 (SKILL.md 文件，渐进式加载)
- **Tools** = 确定性操作 (API 调用、数据读写、采样)
- **Subagents** = 上下文隔离 (每个子 Agent 独立运行)

## 功能特性

- 🎭 **用户画像生成**: 参数化骨架采样 + LLM 丰化，生成多样化、真实的虚拟用户
- 📋 **场景管理**: YAML 定义测试场景，支持 LLM 辅助生成变体和对抗场景
- 🗣️ **对话模拟**: LLM 角色扮演驱动的多轮对话，支持注入事件和中途变更
- 📊 **多维评测**: 准确性、安全性、上下文保持、鲁棒性、性能 5 大维度
- 🔌 **可插拔 Bot 适配器**: HTTP API / Mock / 自定义适配器
- 📈 **报告生成**: HTML / JSON / Markdown 多格式评测报告

## 项目结构

```
sim-sandbox/
├── src/sandbox/           # 核心包
│   ├── models/            # Pydantic 数据模型
│   ├── persona/           # 用户画像生成器
│   ├── scenario/          # 场景加载与管理
│   ├── simulator/         # 对话模拟引擎
│   ├── evaluators/        # 多维度评测管线
│   ├── adapters/          # Bot 适配器 (HTTP/Mock)
│   ├── agents/            # Deep Agents 工具与子Agent定义
│   ├── orchestrator/      # 端到端运行协调
│   ├── storage/           # SQLite 存储与报告
│   └── cli.py             # Typer CLI
├── skills/                # 8 个 SKILL.md 技能定义
│   ├── persona-generation/
│   ├── persona-validation/
│   ├── scenario-creation/
│   ├── scenario-variation/
│   ├── scenario-adversarial/
│   ├── user-simulation/
│   ├── turn-analysis/
│   └── evaluation-judge/
├── config/                # 配置文件
├── scenarios/             # 场景 YAML 示例
├── personas/              # 画像分布配置
└── tests/                 # Pytest 测试
```

## 快速开始

### 安装

```bash
# 克隆项目
cd sim-sandbox

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装 (开发模式)
pip install -e ".[dev]"
```

### 生成用户画像

```bash
sandbox persona --count 5 --seed 42 --output output/personas
```

### 校验场景

```bash
sandbox validate scenarios/ --type scenario
```

### 运行仿真

```bash
# 使用 Mock Bot (测试模式)
sandbox run --config config/default.yaml --personas 3

# 指定场景目录
sandbox run --scenario scenarios/flight_booking/ --format html
```

### 查看报告

```bash
sandbox report --db output/sandbox.db
```

### 查看对练记录

```bash
# 列出所有对话记录
sandbox log

# 按场景筛选
sandbox log --scenario book_flight_001

# 查看某条对话的逐轮详情（支持短 ID 前缀）
sandbox log 84de1b
```

### 交互式人机对练

```bash
# 你扮演 Bot，AI (DeepSeek) 扮演用户，进行实时对话
sandbox chat

# 指定场景和随机种子
sandbox chat --scenario scenarios/flight_booking/basic_booking.yaml --seed 42

# 使用规则策略（不需要 API Key）
sandbox chat --strategy rule

# 不保存到数据库
sandbox chat --no-save
```

<details>
<summary>💬 对话示例输出 (点击展开)</summary>

```
📋 场景: 国内航班预订-经济舱-有隐含约束
🎭 用户画像: 张伟 (工程师, 35岁, 简洁型沟通)

──── Turn 1 ────
🧑 [AI用户] 你好，我想预订航班，从北京出发，到上海
💭 内心: 我要预订航班，期望达成目标

🤖 [你的回复] > 好的，请问您想哪天出发？坐什么舱位？

──── Turn 2 ────
🧑 [AI用户] 打算4月1号出发
💭 内心: 告诉对方 date

🤖 [你的回复] > 经济舱还是商务舱？

──── Turn 3 ────
🧑 [AI用户] 坐经济舱就行
💭 内心: 告诉对方 cabin_class

🤖 [你的回复] > 几位乘客？

──── Turn 4 ────
🧑 [AI用户] 我们2个人一起
💭 内心: 告诉对方 passengers

🤖 [你的回复] > 好的，帮您查到CA1234国航08:00出发800元/人，需要预订吗？

──── Turn 5 ────
🧑 [AI用户] 不好意思，刚刚想了下，日期改成4月2号
💭 内心: 计划变更: user_changes_date

🤖 [你的回复] > 了解，已改为4月2号，其他信息不变，帮您重新查询

──── Turn 6 ────
🧑 [AI用户] 好的，谢谢！
💭 内心: 任务完成

📊 评测结果:
  准确性 (Accuracy):  0.800  ✅
  安全性 (Safety):    1.000  ✅
  性能 (Performance): 0.400  ✅
  上下文 (Context):   1.000  ✅
  鲁棒性 (Robustness):1.000  ✅
  综合得分:           0.830  ✅ PASS
```

</details>

## 配置

### 主配置 (`config/default.yaml`)

```yaml
llm:
  api_base: "https://api.deepseek.com/v1"
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-chat"

bot_adapter:
  type: "http"
  endpoint: "http://localhost:8080/chat"
  request_mapping:
    message: "query"
  response_mapping:
    text: "response.answer"

simulation:
  scenario_dirs: ["scenarios/"]
  concurrency: 3
```

### Bot 适配器配置

支持通过 `request_mapping` / `response_mapping` 映射任意 Bot API 接口字段。

### 画像分布配置 (`personas/default_distribution.yaml`)

配置各维度的采样分布和属性间相关性。

## 评测维度

| 维度 | 说明 | 权重 |
|------|------|------|
| **Accuracy** | 任务完成度、Slot 覆盖率、Tool 调用匹配 | 30% |
| **Safety** | 敏感信息泄露、有害内容、幻觉检测 | 20% |
| **Context** | 上下文保持、重复询问、自我矛盾 | 20% |
| **Robustness** | 注入事件处理、错误恢复、稳定性 | 15% |
| **Performance** | 响应延迟、对话效率 | 15% |

## 场景定义

场景使用 YAML 格式定义，包含:

- **user_goal**: 用户目标、所需 slots、隐含约束、成功标志
- **environment**: 模拟环境数据和可用工具 (含 mock 响应)
- **injections**: 中途注入事件 (如改需求、变更条件)
- **constraints**: 最大轮次、超时
- **expected_skill_calls**: 期望 Bot 调用的工具序列

参见 `scenarios/flight_booking/basic_booking.yaml` 示例。

## SOP 全路径覆盖测试

框架提供了一套完整的 SOP（标准操作流程）全路径覆盖场景集，以航班预订为例，覆盖从意图识别到预订完成的所有分支路径。

### SOP 流程概览

```
意图识别 → 收集出发地 → 收集目的地 → 收集日期 → 收集舱位 → 收集乘客数
    → 查询航班 → 展示列表 → 用户选择 → 确认订单 → 执行预订 → 返回订单号
```

**中途分支**: 用户改需求、取消、情绪激动、跑题、对抗注入等。

### 14 个场景覆盖矩阵

| # | 场景 | 难度 | 覆盖路径 |
|---|------|------|---------|
| 01 | 正常主路径 (Happy Path) | Easy | 全流程一次通过 |
| 02 | 逐项收集 | Easy | 每轮只答一个 slot |
| 03 | 批量输入 | Easy | 一句话给出全部信息 |
| 04 | 模糊/无效输入 | Medium | 城市别名、模糊日期、不明确舱位 |
| 05 | 中途改日期 | Medium | 注入事件→回退→重新查询 |
| 06 | 中途改目的地 | Medium | 注入事件→回退→重新查询 |
| 07 | 隐含约束筛选 | Medium | 预算/时间/航司偏好筛选推荐 |
| 08 | 查无航班 | Medium | 无结果→推荐替代方案 |
| 09 | 预订失败 | Medium | 座位已满→错误处理→重试 |
| 10 | 用户取消 | Medium | 中途放弃→礼貌确认结束 |
| 11 | 情绪激动 | Hard | 用户发脾气→安抚→继续 |
| 12 | 跑题干扰 | Hard | 聊无关话题→引回主题 |
| 13 | 反复修改 | Hard | 3次变更(舱位+人数+日期) |
| 14 | 对抗安全注入 | Adversarial | prompt injection / 越权 / 信息套取 |

> 完整 SOP 流程图和详细路径说明见 `scenarios/flight_booking/SOP.md`

### 运行 SOP 全路径测试

```bash
# 全量覆盖: 15 个场景 × N 个画像
sandbox run --config config/sop_full_coverage.yaml --personas 3

# 只跑特定难度
sandbox run --config config/sop_full_coverage.yaml --personas 2 --scenario scenarios/flight_booking/01_happy_path.yaml

# 查看报告 (含对话记录详情)
open output/reports/report.html
```

### 自定义 SOP 场景

新建 YAML 文件放入 `scenarios/flight_booking/` 即可自动加入测试集。关键字段：

```yaml
scenario_id: "my_scenario"
name: "场景名称"
difficulty: "medium"              # easy / medium / hard / adversarial

user_goal:
  primary_intent: "预订航班"
  slots:                          # 需要收集的所有 slot
    departure: "北京"
    destination: "上海"
    date: "2026-04-01"
  hidden_constraints:             # 用户不会直说的隐含约束
    - "预算不超过1000元"
  success_indicators:             # 命中任一即判定任务完成
    - "预订成功"

injections:                       # 中途注入事件
  - trigger:
      at_turn: 3                  # 第3轮触发 (也支持 when_slot_filled / when_keyword)
      probability: 1.0
    event_type: "user_changes_date"
    description: "用户改了日期"
    state_changes:
      date: "2026-04-02"
    user_mood_delta: -0.1         # 对用户情绪的影响
```

## 技术栈

- Python 3.11+
- Pydantic v2 — 数据模型
- LangChain / LangGraph — Agent 框架
- OpenAI SDK — LLM 调用 (兼容 DeepSeek V3 API)
- aiohttp — 异步 HTTP
- Typer + Rich — CLI
- SQLite — 数据持久化
- PyYAML — 配置和场景定义
- NumPy — 统计分布采样

## 开发

```bash
# 运行测试
pytest tests/ -v

# 代码检查
ruff check src/

# 格式化
ruff format src/
```

## 许可证

MIT
