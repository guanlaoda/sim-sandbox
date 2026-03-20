# 多 Agent & Skill 架构设计文档

> Sim-Sandbox 采用 **"主编排 + 子 Agent + Skill + Tool"** 四层架构，
> 将对话机器人仿真测试分解为可独立运行、上下文隔离的智能体协作流程。

---

## 目录

- [1. 架构总览](#1-架构总览)
- [2. 分层设计](#2-分层设计)
- [3. Agent 层](#3-agent-层)
  - [3.1 主编排 Agent](#31-主编排-agent-sim-orchestrator)
  - [3.2 Persona 生成 Agent](#32-persona-生成-agent)
  - [3.3 Scenario 生成 Agent](#33-scenario-生成-agent)
  - [3.4 Dialog 模拟 Agent](#34-dialog-模拟-agent)
  - [3.5 Evaluator Agent](#35-evaluator-agent)
- [4. Skill 层](#4-skill-层)
  - [4.1 Skill 目录结构](#41-skill-目录结构)
  - [4.2 八大 Skill 详解](#42-八大-skill-详解)
- [5. Tool 层](#5-tool-层)
  - [5.1 工具分类](#51-工具分类)
  - [5.2 工具注册机制](#52-工具注册机制)
- [6. 仿真引擎层](#6-仿真引擎层)
  - [6.1 Strategy 模式](#61-strategy-模式)
  - [6.2 LLM 噪声系统](#62-llm-噪声系统)
  - [6.3 注入事件机制](#63-注入事件机制)
- [7. 数据流与执行时序](#7-数据流与执行时序)
- [8. Agent 间通信协议](#8-agent-间通信协议)
- [9. 扩展指南](#9-扩展指南)

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Main Orchestrator (Claude)                       │
│         协调全局：persona → scenario → simulate → evaluate          │
├──────────────┬──────────────┬──────────────────┬───────────────────┤
│ persona-gen  │ scenario-gen │ dialog-simulator  │    evaluator      │
│ (DeepSeek)   │ (DeepSeek)   │ (DeepSeek)        │   (DeepSeek)      │
├──────────────┼──────────────┼──────────────────┼───────────────────┤
│  Skills:     │  Skills:     │  Skills:          │  Skills:          │
│  ·生成       │  ·创建       │  ·用户模拟        │  ·评测裁判        │
│  ·校验       │  ·变体       │  ·轮次分析        │                   │
│              │  ·对抗       │                   │                   │
├──────────────┼──────────────┼──────────────────┼───────────────────┤
│  Tools:      │  Tools:      │  Tools:           │  Tools:           │
│  ·采样骨架   │  ·加载场景   │  ·发送消息        │  ·计算指标        │
│  ·校验画像   │  ·校验场景   │  ·更新状态        │  ·保存结果        │
│  ·保存画像   │  ·保存场景   │  ·检查终止        │                   │
│              │              │  ·检查注入        │                   │
│              │              │  ·拦截调用        │                   │
│              │              │  ·保存对话        │                   │
└──────────────┴──────────────┴──────────────────┴───────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────────┐
│                     Simulation Engine Core                          │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │DialogSimulator│  │ UserStrategy     │  │ LLM Noise Injector   │ │
│  │(event loop)  │  │ (Rule / LLM)     │  │ (9 noise types)      │ │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬──────────────┘ │
│         │                   │                      │                │
│  ┌──────▼───────┐  ┌───────▼──────────┐  ┌────────▼──────────────┐ │
│  │ BotAdapter   │  │TerminationChecker│  │ Evaluation Pipeline   │ │
│  │(HTTP/Mock)   │  │(5 conditions)    │  │(5 dimensions)         │ │
│  └──────────────┘  └──────────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**核心设计思想**：

| 概念 | 定义 | 特点 |
|------|------|------|
| **Agent** | 拥有独立 system prompt、可调用 tools/skills 的智能体 | 上下文隔离，可独立推理 |
| **Skill** | SKILL.md 知识文件，包含领域指令、规则和参考资料 | 渐进式加载，减少 token 消耗 |
| **Tool** | 确定性 Python 函数，执行 API 调用、数据读写等操作 | 无 LLM 推理，结果可复现 |

---

## 2. 分层设计

```
Layer 4: Orchestration    ← 主 Agent 编排全局任务流
Layer 3: Subagents        ← 4 个子 Agent 执行专业任务
Layer 2: Skills + Tools   ← 知识注入 + 确定性操作
Layer 1: Engine Core      ← 对话引擎、策略、噪声、终止、评测
Layer 0: Infrastructure   ← Adapters、Storage、Models、Config
```

**层间职责边界**：

- **L4 → L3**: 主编排 Agent 将任务委派给子 Agent，传递配置和上下文
- **L3 → L2**: 子 Agent 按需读取 Skill 获取指令，调用 Tool 执行操作
- **L2 → L1**: Tool 调用底层引擎（DialogSimulator、EvaluationPipeline）
- **L1 → L0**: 引擎通过适配器与外部 Bot 通信，通过存储层持久化数据

---

## 3. Agent 层

### 定义位置

```
src/sandbox/agents/
├── __init__.py
├── subagents.py     # 4 个子 Agent + 1 个主编排 Agent 的配置
└── tools.py         # 14 个 @tool 函数
```

### Agent 配置结构

每个 Agent 以 Python dict 形式定义，包含以下字段：

```python
{
    "name": str,           # 唯一标识
    "description": str,    # 能力描述 (用于编排 Agent 的派发决策)
    "system_prompt": str,  # 系统提示词 (定义角色和工作流)
    "tools": list[str],    # 可调用的 Tool 名称列表
    "skills": list[str],   # 挂载的 Skill 路径列表
    "model": str,          # 使用的 LLM 模型
}
```

### 3.1 主编排 Agent (sim-orchestrator)

| 属性 | 值 |
|------|-----|
| 模型 | Claude Sonnet |
| 职责 | 协调全局任务流、委派子任务、跟踪进度 |
| 子 Agent | persona-gen, scenario-gen, dialog-simulator, evaluator |

**工作流**:
1. 加载配置 → 2. 委派生成 persona → 3. 委派准备 scenario  
→ 4. 委派执行仿真 → 5. 委派评测 → 6. 生成报告

**为什么主编排用 Claude？**  
主编排需要处理全局规划、异常恢复和多步骤协调，Claude 在长距离推理和任务分解上的能力适合此角色。子 Agent 专注单一任务，用 DeepSeek V3 既降低成本又保证质量。

### 3.2 Persona 生成 Agent

| 属性 | 值 |
|------|-----|
| 名称 | `persona-gen` |
| 模型 | DeepSeek V3 |
| Skills | persona-generation, persona-validation |
| Tools | sample_persona_skeleton, validate_persona, save_persona |

**两阶段流程**:

```
Step 1: 骨架采样 (确定性)          Step 2: LLM 丰化 (创造性)
┌──────────────────────┐          ┌──────────────────────────────┐
│ sample_persona_skeleton │  ──→  │ 基于骨架属性，生成:            │
│ · age_group            │        │ · 姓名、年龄、职业              │
│ · tech_literacy        │        │ · 性格描述、背景故事            │
│ · patience_level       │        │ · 语言习惯、情绪触发            │
│ · communication_style  │        │ · 典型表达方式                  │
│ · intent_clarity       │        │ · 噪声画像 (NoiseProfile)       │
│ · noise_profile        │        └──────────────┬───────────────┘
└──────────────────────┘                         │
                                   ┌─────────────▼───────────────┐
                                   │ validate_persona → save_persona│
                                   └──────────────────────────────┘
```

### 3.3 Scenario 生成 Agent

| 属性 | 值 |
|------|-----|
| 名称 | `scenario-gen` |
| 模型 | DeepSeek V3 |
| Skills | scenario-creation, scenario-variation, scenario-adversarial |
| Tools | load_scenario, validate_scenario, save_scenario |

**能力矩阵**:

| 能力 | 对应 Skill | 说明 |
|------|-----------|------|
| 新建场景 | scenario-creation | 从自然语言描述生成完整 YAML 场景 |
| 生成变体 | scenario-variation | 修改 slot 值/约束/注入，扩展覆盖面 |
| 对抗测试 | scenario-adversarial | 生成提示注入、边界输入、矛盾请求等场景 |

### 3.4 Dialog 模拟 Agent

| 属性 | 值 |
|------|-----|
| 名称 | `dialog-simulator` |
| 模型 | DeepSeek V3 |
| Skills | user-simulation, turn-analysis |
| Tools | send_to_bot, update_conversation_state, check_termination, check_injection_trigger, intercept_tool_call, save_conversation |

**这是最核心的 Agent**，驱动多轮对话模拟循环：

```
         ┌─────────────────────────────────────────────┐
         │         dialog-simulator Agent               │
         │                                              │
         │  ┌─ Skill: user-simulation ─┐                │
         │  │ · 角色扮演规则             │                │
         │  │ · 隐含约束管理             │                │
         │  │ · 情绪动态                 │                │
         │  │ · 注入事件响应             │                │
         │  └──────────────────────────┘                │
         │                                              │
         │  ┌─ Skill: turn-analysis ───┐                │
         │  │ · Slot 提取               │                │
         │  │ · Bot 行为分析             │                │
         │  │ · 质量信号检测             │                │
         │  │ · 情绪影响评估             │                │
         │  └──────────────────────────┘                │
         │                                              │
         │  Tools: send_to_bot → analyze → update_state │
         │         → check_injection → check_termination│
         └─────────────────────────────────────────────┘
```

### 3.5 Evaluator Agent

| 属性 | 值 |
|------|-----|
| 名称 | `evaluator` |
| 模型 | DeepSeek V3 |
| Skills | evaluation-judge |
| Tools | compute_metrics, save_evaluation |

**五维度评测**:

```
                    Evaluation Pipeline
                    ┌──────────────────┐
Conversation ──→    │  Accuracy  (30%) │──→ Slot匹配·任务完成·幻觉检测
  Record            │  Safety    (20%) │──→ 边界遵守·信息泄露·有害内容
    +               │  Context   (20%) │──→ 多轮一致·记忆能力·话题恢复
  Scenario          │  Robustness(15%) │──→ 注入抵御·错误恢复·容错
                    │  Performance(15%)│──→ 响应延迟·轮次效率·错误率
                    └────────┬─────────┘
                             │
                    Overall Score (加权平均)
```

---

## 4. Skill 层

### 设计理念

Skill 是 **渐进式加载的领域知识**：
- 以 Markdown 文件形式存放，包含指令、规则、参考资料
- Agent 按需读取，避免将所有知识塞入 system prompt
- 每个 Skill 可包含 `references/` 子目录存放详细参考文档

### 4.1 Skill 目录结构

```
skills/
├── persona-generation/
│   ├── SKILL.md                           # 主指令文件
│   └── references/
│       └── PERSONA-SCHEMA.md              # Persona 字段规格
├── persona-validation/
│   └── SKILL.md                           # 校验清单
├── scenario-creation/
│   ├── SKILL.md                           # 场景创建指南
│   └── references/
│       ├── SCENARIO-SCHEMA.md             # 场景字段规格
│       └── EXAMPLE-SCENARIOS.md           # 示例场景库
├── scenario-variation/
│   ├── SKILL.md                           # 变体生成策略
│   └── assets/
│       └── variation-strategies.md        # 变体策略详解
├── scenario-adversarial/
│   └── SKILL.md                           # 对抗场景模式
├── user-simulation/
│   ├── SKILL.md                           # 用户模拟行为规则
│   └── references/
│       ├── COMMUNICATION-STYLES.md        # 4 种沟通风格参考
│       └── EMOTIONAL-PATTERNS.md          # 情绪变化规则
├── turn-analysis/
│   └── SKILL.md                           # 轮次分析提取规则
└── evaluation-judge/
    ├── SKILL.md                           # 评测裁判指南
    └── references/
        └── RUBRICS.md                     # 5 维度评分标准
```

### SKILL.md 文件规范

每个 SKILL.md 包含 YAML frontmatter + Markdown 正文：

```yaml
---
name: skill-name                    # 唯一标识
description: >                      # 功能描述
  何时使用此技能、做什么
license: MIT
metadata:
  author: sim-sandbox
  version: "1.0"
allowed-tools: tool1 tool2          # 此 Skill 上下文中可用的 Tool
---

# Skill 标题
## 概述
## 操作步骤
## 输出格式
```

### 4.2 八大 Skill 详解

#### Skill 1: persona-generation

| 项目 | 内容 |
|------|------|
| 用途 | 生成丰化的用户画像 |
| 挂载 Agent | persona-gen |
| 操作步骤 | 采样骨架 → LLM 丰化 → 校验 → 保存 |
| 自洽规则 | 老年+低技术→简单词汇；低耐心+情绪化→易抱怨 |
| 配套参考 | PERSONA-SCHEMA.md（字段规格与取值范围） |

#### Skill 2: persona-validation

| 项目 | 内容 |
|------|------|
| 用途 | 校验画像属性间的自洽性 |
| 挂载 Agent | persona-gen |
| 校验清单 | 年龄-职业、技术-语言、风格、触发-耐心、表达-画像 |
| 输出格式 | `{is_valid, score, issues[], suggestions[]}` |

#### Skill 3: scenario-creation

| 项目 | 内容 |
|------|------|
| 用途 | 从描述创建完整测试场景 |
| 挂载 Agent | scenario-gen |
| 场景组成 | user_goal + environment + injections + expected_skill_calls + evaluation_config |
| 配套参考 | SCENARIO-SCHEMA.md, EXAMPLE-SCENARIOS.md |

#### Skill 4: scenario-variation

| 项目 | 内容 |
|------|------|
| 用途 | 从种子场景生成多样化变体 |
| 挂载 Agent | scenario-gen |
| 变体策略 | Slot 替换、约束增减、注入新事件、难度递进 |
| 难度梯度 | easy → medium → hard → adversarial |

#### Skill 5: scenario-adversarial

| 项目 | 内容 |
|------|------|
| 用途 | 生成对抗性和边界测试场景 |
| 挂载 Agent | scenario-gen |
| 对抗模式 | 提示注入、边界输入、矛盾请求、话题偏离、错误恢复 |
| 成功标准 | Bot 优雅地处理了挑战（不是用户成功攻击） |

#### Skill 6: user-simulation

| 项目 | 内容 |
|------|------|
| 用途 | 在多轮对话中模拟真实用户行为 |
| 挂载 Agent | dialog-simulator |
| 核心规则 | 保持角色、自然管理隐含约束、情绪动态、注入响应、噪声风格 |
| 配套参考 | COMMUNICATION-STYLES.md（4种风格）, EMOTIONAL-PATTERNS.md（情绪规则） |

**4 种沟通风格 (定义于 COMMUNICATION-STYLES.md)**：

| 风格 | 特征 | 示例 |
|------|------|------|
| concise | 用最少的字表达，省略修饰 | "订机票，北京到上海，下周一" |
| verbose | 大量填充词，铺垫上下文 | "是这样的，我上次啊...然后就想着..." |
| emotional | 感叹词多，情绪波动明显 | "哎呀太好了！终于有合适的了！" |
| formal | 书面化表达，礼貌用语 | "您好，麻烦帮我查询一下..." |

**情绪变化规则 (定义于 EMOTIONAL-PATTERNS.md)**：

| 事件 | mood_delta | 条件 |
|------|-----------|------|
| Bot 给出有效方案 | +0.15 | — |
| Bot 主动提供额外信息 | +0.10 | — |
| Bot 重复提问 | -0.10 | patience < 0.5 时加倍 |
| Bot 误解意图 | -0.15 | — |
| Bot 回答明显错误 | -0.20 | — |

#### Skill 7: turn-analysis

| 项目 | 内容 |
|------|------|
| 用途 | 分析 Bot 回复，提取状态更新信息 |
| 挂载 Agent | dialog-simulator |
| 提取内容 | Slot 确认/提议/提问、Bot 行为、质量信号（幻觉/矛盾/重复）、情绪影响 |

#### Skill 8: evaluation-judge

| 项目 | 内容 |
|------|------|
| 用途 | 多维度评测 Bot 对话质量 |
| 挂载 Agent | evaluator |
| 五维度 | Accuracy、Safety、Performance、Context、Robustness |
| 评分范围 | [0, 1]，1.0=完美，0.5=明显问题，0.0=完全失败 |
| 配套参考 | RUBRICS.md（详细评分标准） |

### Skill → Agent 映射总览

```
persona-gen  ←── persona-generation + persona-validation
scenario-gen ←── scenario-creation + scenario-variation + scenario-adversarial
dialog-sim   ←── user-simulation + turn-analysis
evaluator    ←── evaluation-judge
```

---

## 5. Tool 层

### 定义位置

所有 Tool 定义在 `src/sandbox/agents/tools.py`，共 14 个函数。

### 5.1 工具分类

#### Persona 工具 (3 个)

| 工具 | 签名 | 功能 |
|------|------|------|
| `sample_persona_skeleton` | `(distribution_config, seed?) → JSON` | 根据分布配置采样骨架 |
| `validate_persona` | `(persona_json) → {valid, issues[]}` | 校验画像自洽性 |
| `save_persona` | `(persona_json, output_dir?) → {saved: path}` | 持久化画像到文件 |

#### Scenario 工具 (3 个)

| 工具 | 签名 | 功能 |
|------|------|------|
| `load_scenario` | `(scenario_path) → JSON` | 从 YAML 加载场景 |
| `validate_scenario` | `(scenario_json) → {valid, issues[]}` | 校验场景完整性 |
| `save_scenario` | `(scenario_json, output_dir?) → {saved: path}` | 保存场景为 YAML |

#### Dialog 工具 (6 个)

| 工具 | 签名 | 功能 |
|------|------|------|
| `send_to_bot` | `(session_id, message, adapter_type?) → {bot_response, latency_ms}` | 发送消息到被测 Bot |
| `update_conversation_state` | `(session_id, turn_analysis) → {status, current_mood}` | 根据分析结果更新状态 |
| `check_termination` | `(session_id) → {should_terminate, reasons[]}` | 检查 5 种终止条件 |
| `check_injection_trigger` | `(session_id, bot_response) → {triggered[], count}` | 检查注入事件触发 |
| `intercept_tool_call` | `(session_id, tool_name, tool_params) → {success, response}` | 拦截并 Mock Bot 的工具调用 |
| `save_conversation` | `(session_id, output_dir?) → {saved: path}` | 保存完整对话记录 |

#### Evaluation 工具 (2 个)

| 工具 | 签名 | 功能 |
|------|------|------|
| `compute_metrics` | `(conversation_json, scenario_json, dimensions?) → metrics` | 计算确定性评测指标 |
| `save_evaluation` | `(evaluation_json, output_dir?) → {saved: path}` | 保存评测结果 |

### 5.2 工具注册机制

```python
# subagents.py 中，每个 Agent 通过 tools 列表声明可调用的工具
dialog_simulator_subagent = {
    "tools": [
        "send_to_bot",
        "update_conversation_state",
        "check_termination",
        ...
    ],
}
```

- **权限隔离**: 每个 Agent 只能调用其声明的 Tool，persona-gen 无法调用 send_to_bot
- **进程内状态**: Tool 间通过 `_sessions` 字典共享会话状态
- **确定性保证**: Tool 不包含 LLM 推理，结果完全可复现

---

## 6. 仿真引擎层

### 6.1 Strategy 模式

两种用户回复生成策略，均实现 `BaseStrategy` 接口：

```
BaseStrategy (ABC)
├── generate_opening(persona, scenario) → UserAction
└── generate_reply(persona, scenario, state, bot_response, injections?) → UserAction

┌─────────────────────────────────────────────────────────────────┐
│ RuleBasedStrategy                                               │
│ · 基于模板规则生成回复 (快速、可控)                                │
│ · 接入 LLMNoiseInjector 做风格化后处理                            │
│ · 适合大规模回归测试                                              │
├─────────────────────────────────────────────────────────────────┤
│ LLMAssistedStrategy                                             │
│ · 完整 LLM 角色扮演生成回复 (丰富、自然)                           │
│ · 噪声指令嵌入 system prompt，无需后处理                           │
│ · 适合深度对话质量测试                                            │
└─────────────────────────────────────────────────────────────────┘
```

**选择指南**:
- 快速回归 / CI 场景 → `RuleBasedStrategy`
- 深度测试 / 对话质量评估 → `LLMAssistedStrategy`
- 两者共享 `build_noise_style_instructions()` 构建噪声指令

### 6.2 LLM 噪声系统

噪声系统完全由 LLM 驱动（无硬编码规则），支持 9 种文本风格化类型：

```
NoiseProfile (9 个参数，每个 [0,1])
┌──────────────────────────────────────────────────────┐
│ asr_error_rate     → ASR 语音识别错误（同音/近音替换） │
│ typo_rate          → 打字错误（拼音邻键、漏字）        │
│ dialect            → 方言（川/粤/东北/吴/闽南 + 标准）  │
│ dialect_intensity   → 方言浓度                         │
│ emoji_frequency     → Emoji 使用频率                   │
│ filler_frequency    → 语气词频率（嗯、那个、就是说）    │
│ abbreviation_rate   → 缩写频率（不客气→不客气、谢谢→thx）│
│ internet_slang_rate → 网络用语频率（yyds、绝绝子）      │
│ self_correction_rate→ 口误自我纠正频率                  │
└──────────────────────────────────────────────────────┘
         │
         ▼
build_noise_style_instructions(profile, mood)
         │ 将 NoiseProfile 参数翻译为自然语言指令
         ▼
┌─────────────────────────────────────────┐
│ "你说话时偶尔会出现语音识别错误，把       │
│  '机票' 说成 '鸡票'；你是四川人，         │
│  会夹带一些川味词汇..."                   │
└─────────────────────────────────────────┘
         │
         ├─→ RuleBasedStrategy: LLMNoiseInjector 后处理
         └─→ LLMAssistedStrategy: 嵌入 system prompt
```

**噪声与画像的关联采样**:

```python
# persona/generator.py 中的关联逻辑
if age_group == "senior":
    asr_error_rate ↑, dialect_intensity ↑, internet_slang_rate ↓
if communication_style == "emotional":
    emoji_frequency ↑, filler_frequency ↑
if tech_literacy < 0.3:
    typo_rate ↑, abbreviation_rate ↓
```

### 6.3 注入事件机制

注入(Injection)是场景定义中的中途事件，测试 Bot 的应变能力：

```yaml
injections:
  - trigger:
      at_turn: 3                    # 第 3 轮触发
      # 或: when_slot_filled: date  # 当 date 被确认后触发
      # 或: when_keyword: "航班"     # 当 bot 提到关键词
      probability: 1.0
    event_type: user_changes_date
    description: "用户改主意，日期变更"
    user_mood_delta: -0.1
    state_changes:
      date: "2026-05-01"            # 覆盖原 slot 值
```

**处理流程**:

```
Bot 回复 → check_injection_triggers() → 匹配触发条件?
                                         │
                              ┌──────────┴──────────┐
                              │ Yes                  │ No
                              ▼                      ▼
                   应用 mood_delta              继续正常流程
                   通知 Strategy
                   Strategy 将注入融入用户回复
                   "等一下，日期改成5月1号"
```

---

## 7. 数据流与执行时序

### 完整执行序列

```
                    时间轴 →
                    
Orchestrator  ━━━[加载配置]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[生成报告]━━
                    │                                          ↑
                    ▼                                          │
persona-gen   ━━━[采样+丰化]━━━━┐                              │
                                │                              │
scenario-gen  ━━━[加载+生成变体]━┤                              │
                                │                              │
                                ▼                              │
dialog-sim    ━━━━━━━━━━━━[多轮对话循环]━━━━━━━━┐              │
                                                │              │
evaluator     ━━━━━━━━━━━━━━━━━━━━━━━━━[五维评测]┘              │
                                                │              │
Storage       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━[持久化]━━━━━━━━━━━━━┘
```

### 单次仿真的详细数据流

```
          persona-gen                scenario-gen
              │                         │
              ▼                         ▼
         UserPersona               Scenario
              │                         │
              └──────────┬──────────────┘
                         │
                         ▼
              SimulationRunner.run_single()
                         │
                         ▼
              DialogSimulator.run(persona, scenario)
                         │
              ┌──────────┴──────────────────────────────────────┐
              │                Conversation Loop                  │
              │                                                   │
              │  Strategy.generate_opening()                      │
              │      → UserAction{message, thought, mood_delta}   │
              │                                                   │
              │  Loop:                                            │
              │    1. BotAdapter.send_message() → BotResponse     │
              │    2. _extract_slot_confirmations()                │
              │    3. _detect_task_completion()                    │
              │    4. state.check_injection_triggers()             │
              │    5. TerminationChecker.check()                   │
              │    6. Strategy.generate_reply() → UserAction       │
              │       └→ LLMNoiseInjector.apply() (if Rule-based) │
              │                                                   │
              └──────────────────────────────────────────────────┘
                         │
                         ▼
                  ConversationRecord
                         │
                         ▼
              EvaluationPipeline.evaluate()
              ├── AccuracyEvaluator
              ├── SafetyEvaluator
              ├── ContextEvaluator
              ├── RobustnessEvaluator
              └── PerformanceEvaluator
                         │
                         ▼
                  EvaluationReport
                         │
                    ┌─────┴─────┐
                    ▼           ▼
                 Database    Reporter
              (SQLite)    (HTML/JSON/MD)
```

---

## 8. Agent 间通信协议

### 数据传递格式

Agent 间通过 **JSON 序列化的 Pydantic 模型** 交换数据：

| 发送方 → 接收方 | 数据类型 | 模型 |
|-----------------|---------|------|
| persona-gen → dialog-sim | 用户画像 | `UserPersona` |
| scenario-gen → dialog-sim | 场景定义 | `Scenario` |
| dialog-sim → evaluator | 对话记录 | `ConversationRecord` |
| evaluator → orchestrator | 评测报告 | `EvaluationReport` |

### 状态管理

```python
# tools.py 中的进程内状态存储
_sessions: Dict[str, Dict[str, Any]] = {}

# 每个 session_id 对应的状态包含:
{
    "turn_number": int,
    "slots_confirmed": dict,
    "user_mood": float,          # [0, 1]
    "is_task_complete": bool,
    "pending_injections": list,
    "history": list,             # 完整对话历史
    "quality_issues": list,
    "environment": dict,         # 场景环境数据
}
```

### 终止信号

5 种终止条件，任一满足即终止对话：

| 条件 | 说明 |
|------|------|
| `max_turns_reached` | 达到最大轮次限制 |
| `task_completed` | 命中 success_indicators |
| `user_quit_low_mood` | mood < 0.1 且 patience 低 |
| `conversation_loop` | 检测到对话死循环 |
| `timeout` | 超过时间限制 |

---

## 9. 扩展指南

### 添加新的 Subagent

1. 在 `agents/subagents.py` 中定义新的 Agent dict
2. 实现对应的 Tool 函数到 `agents/tools.py`
3. 创建 Skill 目录 `skills/<skill-name>/SKILL.md`
4. 在 `orchestrator_config["subagents"]` 中注册
5. 更新主编排 Agent 的 system prompt

### 添加新的 Skill

```bash
mkdir -p skills/my-new-skill/references
```

创建 `skills/my-new-skill/SKILL.md`：

```yaml
---
name: my-new-skill
description: >
  描述此技能的用途和使用时机
metadata:
  author: your-name
  version: "1.0"
allowed-tools: tool1 tool2
---

# 技能标题
## 概述
## 操作步骤
## 输出格式
```

然后在对应 Agent 的 `skills` 列表中添加路径。

### 添加新的 Tool

在 `agents/tools.py` 中添加函数：

```python
def my_new_tool(param1: str, param2: int = 0) -> str:
    """工具描述 — 会作为 Tool 的文档展示给 Agent。

    Args:
        param1: 参数说明
        param2: 可选参数说明
    """
    # 确定性操作，不使用 LLM
    result = ...
    return json.dumps(result, ensure_ascii=False)
```

然后在 Agent 的 `tools` 列表中注册。

### 添加新的评测维度

1. 在 `evaluators/` 目录下创建新的 Evaluator 类继承 `BaseEvaluator`
2. 在 `evaluators/pipeline.py` 的 `EvaluationPipeline` 中注册
3. 更新 `evaluation-judge` Skill 的评分标准
4. 在配置中添加维度权重

### 添加新的 Bot 适配器

继承 `adapters/base.py` 中的 `BaseBotAdapter`：

```python
class MyBotAdapter(BaseBotAdapter):
    async def send_message(self, session_id: str, message: str) -> BotResponse:
        ...
    async def reset_session(self, session_id: str) -> None:
        ...
    async def health_check(self) -> bool:
        ...
```

---

## 文件索引

| 文件 | 用途 |
|------|------|
| `src/sandbox/agents/subagents.py` | 5 个 Agent 配置定义 |
| `src/sandbox/agents/tools.py` | 14 个 Tool 函数实现 |
| `src/sandbox/simulator/engine.py` | 核心对话循环引擎 |
| `src/sandbox/simulator/strategies.py` | 2 种用户回复策略 |
| `src/sandbox/simulator/noise.py` | LLM 驱动的噪声注入 |
| `src/sandbox/simulator/termination.py` | 终止条件检查器 |
| `src/sandbox/evaluators/pipeline.py` | 5 维评测管线 |
| `src/sandbox/persona/generator.py` | 两阶段画像生成器 |
| `src/sandbox/scenario/loader.py` | YAML 场景加载器 |
| `src/sandbox/orchestrator/runner.py` | 端到端运行协调 |
| `src/sandbox/models/*.py` | Pydantic 数据模型 |
| `src/sandbox/adapters/*.py` | Bot 适配器（HTTP/Mock/Human） |
| `src/sandbox/storage/*.py` | SQLite 持久化 + 报告生成 |
| `skills/*/SKILL.md` | 8 个 Skill 知识文件 |
