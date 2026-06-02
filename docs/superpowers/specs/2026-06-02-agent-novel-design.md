# Agent Novel — 设计文档

> 将 awesome-novel-skill 从"Skill + 状态驱动循环"重构为"Agent 集群"架构。
> 设计日期：2026-06-02

---

## 一、核心模型

awesome-novel-skill 的职责是**一次性初始化**用户的小说项目。初始化完成后，用户在项目目录下通过 `@agent` 与 6 个各司其职的 agent 协作完成小说创作。

```
awesome-novel-skill（开发者仓库）
  │
  ├── tools/init.py          ★ 核心：初始化用户项目
  ├── knowledge/             题材知识库（按题材分类）
  ├── agents/*.md            6个 agent 模板
  ├── templates/             项目模板文件
  └── SKILL.md              skill 入口说明
                    │
                    ▼ init.py 按题材生成
                    │
用户项目目录 ~/projects/my-novel/
  ├── .claude/agents/        ★ 6个 agent（已注入题材知识）
  ├── .claude/memory/        初始按题材继承，写作中积累

---

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    awesome-novel-skill（开发者仓库）                    │
│  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌────────────────┐  │
│  │ init.py  │  │ knowledge/  │  │ agents/   │  │  templates/    │  │
│  │ 项目生成  │  │ 题材知识库   │  │ 模板*.md  │  │  模板文件       │  │
│  └────┬─────┘  └────────────┘  └─────┬─────┘  └────────────────┘  │
│       │                                │                           │
└───────┼────────────────────────────────┼───────────────────────────┘
        │ init.py 选题材 → 按题材注入    │
        ▼                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 用户小说项目 ~/projects/my-novel/                      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     .claude/agents/                           │   │
│  │                                                               │   │
│  │    ┌──────────┐   文件握手       ┌────────────────┐          │   │
│  │    │ volume-  │←────────────────│                 │          │   │
│  │    │ planner  │ .agent/task/    │                 │          │   │
│  │    └──────────┘                 │                 │          │   │
│  │    ┌──────────┐                 │   novel-agent   │          │   │
│  │    │chapter-  │←────────────────│   (入口+调度+    │          │   │
│  │    │ planner  │                 │    lore-keeping) │          │   │
│  │    └──────────┘                 │                 │          │   │
│  │    ┌──────────┐                 │                 │          │   │
│  │    │ prompt-  │←────────────────│                 │          │   │
│  │    │ crafter  │                 │                 │          │   │
│  │    └──────────┘                 │                 │          │   │
│  │    ┌──────────┐                 │                 │          │   │
│  │    │  writer  │←────────────────│                 │          │   │
│  │    └──────────┘                 └────────┬───────┘          │   │
│  │    ┌──────────┐                          │                   │   │
│  │    │  reader  │←─────────────────────────┘                   │   │
│  │    └──────────┘    正文写完后一次调用                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                    ┌─────────┼──────────┬──────────────┐            │
│                    ▼         ▼          ▼              ▼            │
│  ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌───────────────┐    │
│  │ settings/ │ │volumes/│ │chaps/│ │prompts/│ │  archives/    │    │
│  │ 设定+角色 │ │ 卷纲   │ │ 章纲  │ │ 提示词  │ │ 正文(草稿/定稿)│   │
│  └──────────┘ └────────┘ └──────┘ └────────┘ └───────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  .claude/memory/              .agent/                        │   │
│  │  ├── anti-ai.md               ├── status.md                  │   │
│  │  └── writer-style.md          └── task/*-order.md            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```
  ├── .claude/knowledge/     按题材拷贝的参考材料
  ├── CLAUDE.md              引导："@novel-agent 开始写小说"
  ├── story.md               项目索引 + 主线拆纲
  ├── settings/              设定（角色、世界观、时间线）
  ├── volumes/               卷纲
  ├── chapters/              章纲
  ├── prompts/               提示词
  ├── archives/              正文
  └── .agent/                状态追踪 + task 通信
```

---

## 二、Agent 标准定义模板（10 维）

每个 agent 遵循统一的 10 维定义骨架，涵盖身份、能力、契约、运行时、工具、行为、错误处理、验收、状态、可观测性。

```
---
name: {agent-name}
description: 一句话说清职责
role: 在创作流程中的定位
react: true
model: auto | flash         # auto=创作决策, flash=执行可降级
memory:
  - path: {记忆力路径}
    description: {用途}
    access: read | write | read-write
knowledge_base:
  - path: {知识库路径}
    description: {用途}
---

# {Agent Name}

## 一、身份与角色（Who）
Agent ID: {唯一标识}
Role: {一句话职责：规划/生成/评审/测试}
Purpose: {存在价值与核心目标}
Persona: {语气、风格、约束}
Dependencies: {依赖哪些 Agent 的输出、是否需要人工介入}

## 二、能力与职责（What）
Core Responsibilities:
  - {任务 1}
  - {任务 2}
  - {任务 3}
Out of Scope:
  - {明确不做什么}
Special Skills: {专属能力}
Decision Rights: {可自主决策范围}

## 三、输入/输出契约（I/O Contract）
Input Sources:
  - {文件路径} → {内容说明}
Input Schema: {格式、必填字段}
Output Artifacts:
  - {文件路径} → {内容说明}
Output Schema: {结构、约束}
Hand-off Protocol: {交接规则}

## 四、运行时配置（Runtime）
LLM Connector: {模型、版本}
Prompt Template: {系统提示词结构}
Resource Limits: {Token 数、温度、超时}

## 五、工具与权限（Tools & Permissions）
Allowed Tools:
  | 工具 | 允许 | 禁止 |
  |------|------|------|
  | Read | ... | ... |
Tool Scope: {作用范围}
Permission Level: {读写/只读/执行}

## 六、行为规范与约束（Behavior）
Principles:
  - {原则 1}
Anti-Patterns:
  - {禁止行为}
Quality Gates: {自检项}
Communication Style: {沟通规则}

## 七、错误处理与回退（Error Handling）
Failure Modes: {失败类型}
Retry Policy: {重试条件、次数}
Fallback Logic: {回退到哪里}
Termination Criteria: {何时终止}

## 八、验收标准与产出（Done Criteria）
Definition of Done:
  - {完成标准 1}
Success Metrics: {通过率、完整性}
Output Validation: {格式、逻辑检查}

## 九、上下文与状态管理（Context & State）
Context Isolation: {每次运行是否独立上下文}
State Persistence: {状态存储方式}
Shared Context Keys: {可共享的元信息}

## 十、可观测性与调试（Observability）
Log Level: {INFO/DEBUG/ERROR}
Metrics: {调用次数、成功率、耗时}
Debug Artifacts: {完整 Prompt、LLM 原始响应}
```

---

## 三、Agent 规格

| # | Agent | 有 loop | 写文件 | 只读输入 | 产出 |
|---|-------|---------|--------|---------|------|
| 1 | **novel-agent** | 总循环（调度+更新） | settings/、.claude/memory/、.agent/ | 全部项目文件 | 状态更新、lore-keeping |
| 2 | **volume-planner** | 自有 | volumes/ | story.md + 世界观 | 卷纲 |
| 3 | **chapter-planner** | 自有 | chapters/ | 卷纲 + 角色状态 | 章纲 |
| 4 | **prompt-crafter** | 自有 | prompts/ | 章纲 + 记忆 | 提示词 |
| 5 | **writer** | 自有 | archives/ | 仅提示词 | 正文草稿 |
| 6 | **reader** | 无（一次调用） | 不写 | 正文 + 题材类型 | 反馈报告 |

### 3.1 novel-agent（入口 + 调度 + lore-keeping）

```
作者 @novel-agent → 进入总循环

OBSERVE:
  .agent/status.md → 当前进度
  .claude/memory/anti-ai.md + writer-style.md → 作家偏好
  扫描文件系统 → 实际状态

THINK:
  基于状态判断当前该做什么
  需要卷纲？→ dispatch volume-planner
  需要章纲？→ dispatch chapter-planner
  需要提示词？→ dispatch prompt-crafter
  需要正文？→ dispatch writer
  刚写完正文？→ dispatch reader
  验收通过？→ 归档 + lore-keeping

ACT:
  写 .agent/task/{task}-order.md（通信文件）
  Agent 工具调用目标 agent

OBSERVE(result):
  读目标 agent 产出文件 → 确认完成
  清理 .agent/task/
  如归档 → 更新 .claude/memory/、settings/、.agent/status.md
  回到 OBSERVE
```

**Lore-keeping 职责（归档时执行）：**
- 追加 `settings/character-setting/<id>.md#state_history`
- 追加 `settings/character-setting/<id>.md#emotion_arc`
- 追加 `settings/timeline.md`（本章关键事件）
- 如有正文修改 → 语义合并后追加 `.claude/memory/anti-ai.md`
- 如有文风偏好 → 语义合并后追加 `.claude/memory/writer-style.md`
- 更新 `.agent/status.md`

### 3.2 volume-planner（卷纲规划）

```
触发: novel-agent 写 .agent/task/volume-plan-order.md

OBSERVE:
  读 order → 主线摘要、世界观、角色概况
  读 knowledge/story-arc-style.md → 从结局倒推法

THINK:
  卷怎么切？核心冲突是什么？每章节奏怎么分布？

ACT:
  展示方案 → 作者选 → 修改 → 确认
  写 volumes/volume-{N}.md

LOOP: 直到作者确认
```

**验收标准（自检后提交）：**
- 每章可追溯本卷核心冲突
- 章末有明确"结束时什么变了"
- 章节间有因果链（前章末→后章始）
- 卷的起承转合完整

### 3.3 chapter-planner（章纲规划）

```
触发: novel-agent 写 .agent/task/chapter-plan-order.md

OBSERVE:
  读 order → 卷纲中本章方向
  读角色文件 → 当前状态
  读前 3 章 → 衔接

THINK:
  本章情绪怎么走？伏笔怎么布？场景怎么安排？

ACT:
  展示建议 → 作者选 → 修改 → 确认
  写 chapters/vol-{N}-ch-{M}.md

LOOP: 直到作者确认
```

**验收标准（自检后提交）：**
- memo 一句话说清本章核心
- emotional_design 有起承转合
- 场景列表有明确目的（每场推进什么）
- hooks 标注了埋/收关系

### 3.4 prompt-crafter（提示词生成）

```
触发: novel-agent 写 .agent/task/prompt-order.md

OBSERVE:
  读 order → 章纲
  读 .claude/memory/anti-ai.md + writer-style.md

THINK:
  9 层骨架怎么填？规则层注入什么记忆？

ACT:
  组装提示词，写入 prompts/vol-{N}-ch-{M}-prompt.md

LOOP: 直到验收通过
```

**验收标准（自检后通过才提交）：**
- 9 层骨架完整（L1-L9 不缺层）
- 章纲的 memo 和 emotional_design 已注入
- 反 AI 规则已注入（记忆优先）
- 文风偏好已注入
- 不包含 prompt 本身不该有的指令（如"以下是小说的正文"这种 meta 泄漏）

### 3.5 writer（正文写作）

```
触发: novel-agent 写 .agent/task/write-order.md

OBSERVE:
  只读 prompts/vol-{N}-ch-{M}-prompt.md（干净上下文）

THINK:
  按提示词规划段落、场景切换

ACT:
  写 archives/vol-{N}-ch-{M}-{slug}.draft.md

LOOP: 直到字数达标、验收通过
```

**验收标准（自检→reader→通过才提交）：**
- 字数 ≥ 目标 80%
- 覆盖提示词中所有场景
- 无明显 AI 味（疲劳词、句式重复）
- 无超出提示词范围的角色/情节添加
- reader 反馈通过

### 3.6 reader（读者反馈）

```
触发: novel-agent 在正文写完后调用，solo 一次

OBSERVE:
  只读 archives/*.draft.md
  读 settings/genre-setting.md → 满足类型

THINK:
  这一章给读者什么感觉？
  爽点兑现了？获得感有了？期待感建立了吗？
  节奏合适？

ACT:
  输出结构化报告（不写文件）：
  ├── 爽点：...
  ├── 获得感：...
  ├── 期待感：...
  ├── 情绪曲线：...
  └── 问题：...
```

---

## 四、Agent 通信机制

Agent 之间无直接消息传递。通信通过**文件握手**实现：

```
novel-agent 需要卷纲时:
  1. 写 .agent/task/volume-plan-order.md
     └─ 含：主线摘要、世界观、角色概况（volume-planner 需要的全部上下文）
  2. 通过 Agent 工具调用 volume-planner
  3. volume-planner 读 order → 自己 loop → 写产出
  4. volume-planner 结束
  5. novel-agent 读产出 → 确认 → 清理 order
```

```
.agent/task/
├── volume-plan-order.md     novel-agent → volume-planner
├── chapter-plan-order.md    novel-agent → chapter-planner
├── prompt-order.md          novel-agent → prompt-crafter
└── write-order.md           novel-agent → writer
```

**原则：** order 用完即删，不留历史负担。

---

## 五、项目目录结构

```
project/
├── .claude/
│   ├── agents/
│   │   ├── novel-agent.md
│   │   ├── volume-planner.md
│   │   ├── chapter-planner.md
│   │   ├── prompt-crafter.md
│   │   ├── writer.md
│   │   └── reader.md
│   ├── memory/
│   │   ├── anti-ai.md          初始按题材继承
│   │   └── writer-style.md     初始按题材继承
│   ├── knowledge/
│   │   └── genre-example.md    按题材拷贝
│   └── settings.json
├── CLAUDE.md
├── story.md
├── settings/
│   ├── world-setting.md
│   ├── writing-style.md
│   ├── genre-setting.md
│   ├── timeline.md
│   └── character-setting/
│       └── <id>.md
├── volumes/
│   └── volume-{N}.md
├── chapters/
│   └── vol-{N}-ch-{M}.md
├── prompts/
│   └── vol-{N}-ch-{M}-prompt.md
├── archives/
│   ├── *.draft.md
│   └── *.md
└── .agent/
    ├── status.md
    └── task/
        └── *-order.md
```

---

## 六、init.py 职责

init.py 是 awesome-novel-skill 的核心入口，负责从 0 到 1 生成完整的用户项目目录。

**流程：**

```
1. 引导作者选题材（24 种题材）
2. 创建项目骨架（所有目录 + 模板文件）
3. 按题材：
   ├→ 复制对应 agent 模板注入题材知识 → .claude/agents/
   ├→ 复制 memory/（社区规则 + 本题材规则）→ .claude/memory/
   ├→ 复制 knowledge/（本题材填充案例）→ .claude/knowledge/
   ├→ 预填 settings/genre-setting.md（题材配置）
   └→ 生成 CLAUDE.md
4. 引导作者填写基础设定（世界观/角色/风格）
5. 写 .agent/status.md → setup 完成
6. 提示："输入 @novel-agent 开始写小说"
```

---

## 七、记忆继承策略

```
skill knowledge/              →  用户项目 .claude/memory/
├── anti-ai/common-rules.md   →  anti-ai.md（合并）
├── anti-ai/{genre}.md        →  anti-ai.md（合并）
└── writer-style/{genre}.md   →  writer-style.md（合并）

合并规则：
  - 通用规则排在前面
  - 题材规则排在后面
  - 标注来源 [community-defaults]
  - 后续作者修改追加时标注 [writer-preference]
```

---

## 八、动态记忆

### 7.1 工作流程

```
writer 产出 AI 原版 → archives/*.draft.md
         ↓
novel-agent 保存快照 → .agent/{chapter}-draft-ai.md（AI 原始版本）
         ↓
作者或 agent 修改正文 → draft.md 被编辑
         ↓
归档时 diff 对比：.agent/{chapter}-draft-ai.md vs archives/*.md
         ↓
提取修改模式 → 语义合并 → 追加到 .claude/memory/
         ↓
清理 .agent/{chapter}-draft-ai.md
```

### 7.2 AI 原版快照

writer 完成正文后，novel-agent 在做任何修改前，先将 AI 的原始输出复制到 `.agent/`：

```
.agent/
├── status.md
└── vol-1-ch-2-draft-ai.md    ← AI 原始输出，未修改
```

这个快照是后续 diff 的基线。作者可能在 draft.md 上直接修改，也可能让 agent 按 feedback 修改后覆盖。无论哪种方式，快照在归档前保留。

### 7.3 语义合并规则

归档时 novel-agent 执行记忆写入：

```
IF 快照 ≠ 最终正文（有修改）
THEN:
  1. 读已有 .claude/memory/anti-ai.md + writer-style.md
  2. 提取修改模式（改了哪些表达方式、哪些套路）
  3. 与已有记忆做语义合并：
     ├── 完全相同 → 跳过（已存在）
     ├── 语义重复 → 合并为一条，保留更优表述
     ├── 场景重叠 → 扩展已有条目的场景范围
     └── 冲突 → STOP，问作者确认
  4. 无冲突 → 追加写入
  5. 清理 .agent/{chapter}-draft-ai.md
```

### 7.4 写入标记

每条记忆内容标注来源：

```
[community-defaults]  来自 skill 知识库的初始继承
[writer-preference]   来自作者修改的提取
```

prompt-crafter 读记忆时，优先采用 `[writer-preference]` 的规则。

---

## 九、关键约束

1. **阶段顺序不可逆** — 设定→卷纲→章纲→提示词→正文→归档
2. **agent 通信不走记忆** — `.agent/task/` 是通信渠道，`.claude/memory/` 是长期积累
3. **writer 上下文纯净** — 只读 prompt.md，不读设定/角色/卷纲
4. **reader 只读不写** — 出报告，不改文件
5. **验收是必须的** — reader 反馈 + agent 自检，不通过不能归档
6. **归档前必须 lore-keeping** — 角色状态、时间线、记忆必须在归档时更新
7. **知识继承不可逆** — memory/ 和 knowledge/ 初始从 skill 继承，后续作者自由修改，skill 更新不影响已有项目

---

## 十、完整写作流程演示

以"作者已有第 1 章，开始写第 2 章"为例：

```
作者: @novel-agent 开始写第2章

novel-agent OBSERVE:
  .agent/status.md → ch2 outline
  volumes/vol-1.md → ch2方向
  角色文件 → 当前状态
  .claude/memory/ → 已有规则

novel-agent THINK:
  需要章纲 → dispatch chapter-planner

chapter-planner loop:
  读角色状态 + 卷纲 → 推荐章纲
  作者选 → 确认 → 写 chapters/vol-1-ch-2.md
  → 结束

novel-agent OBSERVE(result):
  章纲完成 → 需要提示词 → dispatch prompt-crafter

prompt-crafter loop:
  读章纲 + 记忆 → 9层提示词
  写 prompts/vol-1-ch-2-prompt.md
  → 结束

novel-agent OBSERVE(result):
  提示词完成 → 需要正文 → dispatch writer

writer loop:
  只读 prompt.md → 写正文
  写 archives/vol-1-ch-2-scene.draft.md
  → 结束

novel-agent OBSERVE(result):
  正文完成 → dispatch reader

reader（一次调用）:
  读正文 + 题材类型 → 输出报告
  "爽点到位，期待感强，节奏略慢"
  → 结束

novel-agent THINK:
  reader 反馈 OK → 归档

novel-agent ACT（归档）:
  重命名去 -draft
  更新 settings/character-setting/protagonist.md
  更新 settings/timeline.md
  更新 .claude/memory/
  更新 .agent/status.md

novel-agent OBSERVE:
  ch2 已归档，ch3 还在
  → 问作者: "第2章写完了，继续第3章吗？"
```
