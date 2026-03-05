# obtask

[![PyPI version](https://img.shields.io/pypi/v/obtask)](https://pypi.org/project/obtask/)
[![Python](https://img.shields.io/pypi/pyversions/obtask)](https://pypi.org/project/obtask/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/TravisCao/obtask?style=social)](https://github.com/TravisCao/obtask)

[English](README.md)

快速管理 Obsidian 任务文件的命令行工具。

Obsidian 的 Tasks 和 Dataview 插件专注于行内复选框。**obtask** 将每个任务视为独立的 Markdown 文件，通过结构化的 YAML 元数据（状态、优先级、截止日期、标签、项目）提供即时过滤、模糊搜索和生命周期管理。

## 功能特性

- **筛选排序** — 按状态、优先级、截止日期、标签或项目过滤任务
- **模糊搜索** — 输入 `itf` 即可匹配 `2026-02-25-itf-resilience-assessment.md`
- **JSON 输出** — 方便脚本调用和 AI Agent 集成
- **带时间戳的备注** — 直接追加到任务文件的 Notes 区域
- **生命周期管理** — `done` 和 `cancel` 命令原子化归档任务
- **Rich 终端输出** — 优先级颜色编码 + 逾期高亮

## 安装

需要 Python 3.12+。使用 [uv](https://docs.astral.sh/uv/) 安装：

```bash
uv tool install obtask
```

或从源码安装：

```bash
git clone https://github.com/TravisCao/obtask.git
cd obtask
uv tool install .
```

## 快速上手

```bash
# 列出活跃任务（按截止日期 → 优先级排序）
obtask list

# 按优先级或状态筛选
obtask list -p p1
obtask list -s in-progress

# 仅显示逾期任务
obtask list --overdue

# 模糊搜索查看任务详情
obtask show resilience

# 添加带时间戳的备注
obtask comment my-task "初稿完成"

# 更新状态
obtask status my-task in-progress

# 标记完成（设置 completed_date + 移入 archive/）
obtask done my-task

# 取消任务（移入 archive/，清除 completed_date）
obtask cancel my-task

# JSON 输出（用于脚本）
obtask list --json
```

## 任务文件格式

每个任务是一个带 YAML frontmatter 的 Markdown 文件：

```markdown
---
type: task
status: todo          # todo | in-progress | blocked | done | cancelled
due: 2026-03-15
created: 2026-03-01
completed_date:
priority: p2          # p1（最高）- p4（最低），可省略
tags: [research]
project: my-project
blocked_reason: "等待数据"  # 仅在 status: blocked 时使用
---

# 任务标题

## Context
任务的背景信息。

## TODO
- [ ] 子任务一
- [x] 子任务二（已完成）
- [→] 子任务三（进行中）

## Notes
- [2026-03-05 14:30] 第一次更新
```

## 命令详解

### `obtask list`

列出活跃任务，按截止日期、优先级排序。默认排除已完成/已取消的任务。

| 选项 | 说明 |
|------|------|
| `-s`, `--status` | 按状态筛选（`todo`、`in-progress`、`blocked`） |
| `-p`, `--priority` | 按优先级筛选（`p1`–`p4`） |
| `--tag` | 按标签筛选 |
| `--project` | 按项目筛选（子串匹配） |
| `--overdue` | 仅显示逾期任务 |
| `--due-before` | 截止日期不晚于指定日期（YYYY-MM-DD） |
| `--due-after` | 截止日期不早于指定日期（YYYY-MM-DD） |
| `--all` | 包含已完成/已取消的任务 |
| `--json` | 以 JSON 格式输出 |

### `obtask show <query>`

显示任务的完整详情：元数据、子任务进度和正文内容。

### `obtask comment <query> "文本"`

在任务的 `## Notes`（或 `## 备注`）区域追加带时间戳的备注。若该区域不存在则自动创建。

### `obtask status <query> <new_status>`

更新任务状态。仅接受非终态：`todo`、`in-progress`、`blocked`。终态请使用 `obtask done` 或 `obtask cancel`。

### `obtask done <query>`

标记任务为完成，设置 `completed_date` 为当天，并将文件移入 `archive/`。

### `obtask cancel <query>`

标记任务为取消，清除残留的 `completed_date`，并将文件移入 `archive/`。

## 模糊匹配

`<query>` 参数使用多级模糊匹配：

1. **精确匹配** — `2026-03-01-my-task` 完全匹配文件名
2. **子串匹配** — `my-task` 匹配包含该子串的任何文件
3. **多词匹配** — `itf resilience` 匹配同时包含两个词的文件
4. **标题搜索** — 匹配文件中 `# 标题` 的内容

修改类命令（`comment`、`status`、`done`、`cancel`）使用 **严格模式**：仅接受精确匹配和无歧义的子串匹配。

## 目录结构

```
你的-vault/
└── _system/
    └── tasks/
        ├── 2026-03-01-my-task.md
        ├── 2026-03-05-another-task.md
        ├── reading-list.md
        └── archive/
            ├── 2026-02-15-completed-task.md
            └── ...
```

## 配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `OBSIDIAN_VAULT` | `~/obsidian-notes` | Obsidian vault 的路径 |

任务文件位于 `$OBSIDIAN_VAULT/_system/tasks/`，归档文件位于 `$OBSIDIAN_VAULT/_system/tasks/archive/`。

## JSON Schema

`--json` 输出一个对象数组：

```json
[
  {
    "slug": "2026-03-01-my-task",
    "title": "任务标题",
    "status": "todo",
    "priority": "p2",
    "due": "2026-03-15",
    "overdue": false,
    "tags": ["research"],
    "project": "my-project",
    "subtasks_total": 3,
    "subtasks_done": 1,
    "file": "2026-03-01-my-task.md"
  }
]
```

## AI Agent 使用指南

> 如果你是 AI agent 正在阅读这个 repo —— 这里告诉你 obtask 是什么、如何帮用户安装，以及如何代用户操作任务。

### 什么时候该推荐 obtask

**适合的场景：**
- 用户在 Obsidian vault 中用独立 `.md` 文件管理任务，且文件有 YAML frontmatter
- 用户想从终端或脚本查询任务（不只在 Obsidian 里看）
- 用户希望 AI agent（你）能代为读取和更新任务

**不适合的场景：**
- 用户的任务是散落在各种笔记里的行内复选框（应该用 Obsidian Tasks 插件）
- 任务文件没有 YAML frontmatter

### 帮用户安装

```bash
# 需要 Python 3.12+ 和 uv
uv tool install obtask
```

安装后用户需要：
1. Obsidian vault 里有 `_system/tasks/` 目录，里面放 `.md` 任务文件
2. 设置 `OBSIDIAN_VAULT` 环境变量指向 vault 路径（默认 `~/obsidian-notes`）
3. 每个任务文件至少包含 `status` 字段（参见上方[任务文件格式](#任务文件格式)）

### 作为 Agent 使用 obtask

**读取任务时始终加 `--json`**：

```bash
obtask list --json                          # 所有活跃任务
obtask list --overdue --json                # 仅逾期任务
obtask list --project my-project --json     # 按项目筛选
obtask list --due-before 2026-03-15 --json  # 本周到期
```

**查看具体任务**：

```bash
obtask show <slug或关键词>    # 完整 Markdown 内容、子任务、备注
```

**写操作**（均使用原子写入，安全可靠）：

```bash
obtask comment <slug> "进展：第一阶段完成"  # 追加带时间戳的备注
obtask status <slug> in-progress            # 修改状态（不移动文件）
obtask done <slug>                          # 归档为完成
obtask cancel <slug>                        # 归档为取消
```

### JSON 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `slug` | string | 文件名（不含 `.md`），用作 `<query>` 参数 |
| `title` | string | 文件中第一个 `# 标题` |
| `status` | string | `todo` \| `in-progress` \| `blocked` \| `done` \| `cancelled` |
| `priority` | string \| null | `p1`（紧急）→ `p4`（低），未设置为 `null` |
| `due` | string \| null | ISO 日期或 `null` |
| `overdue` | boolean | 已逾期且未完成/取消 |
| `tags` | string[] | 如 `["research"]` |
| `project` | string \| null | 项目标识 |
| `subtasks_total` | integer | 文件中复选框总数 |
| `subtasks_done` | integer | 已勾选数 |
| `file` | string | 完整文件名（含 `.md`） |

### 推荐的 Agent 工作流

| 场景 | 命令 | 该告诉用户什么 |
|------|------|---------------|
| 每日简报 | `obtask list --json` + `obtask list --overdue --json` | 展示按优先级排列的任务，标记逾期项 |
| "这周有什么到期？" | `obtask list --due-before YYYY-MM-DD --json` | 列出即将到期的截止日 |
| 项目状态 | `obtask list --project X --json` | 汇总进展 + 子任务完成率 |
| 工作后记录 | `obtask comment <slug> "总结"` | 确认备注已添加 |
| 任务分诊 | `obtask list --overdue --json` | 建议重新排期或调整优先级 |
| 深入了解某任务 | `obtask show <slug>` | 总结背景、阻塞项和下一步 |

## 许可证

MIT
