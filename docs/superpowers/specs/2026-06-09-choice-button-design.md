# Choice Button Design — 澄清阶段选择题

## Overview

澄清节点目前只用 `Prompt.ask()` 让用户纯自由输入回答。这次改动将澄清提问改为**选择题模式**：每题给出 A/B/C 选项 + "T. Type something" 自定义输入。默认回车 = 选 A。

## Core Decisions

| 决策 | 选项 |
|------|------|
| 选项由谁生成 | **LLM 自动生成**（改 CLARIFY_PROMPT，每题含 question + options） |
| 选 T 后行为 | **弹出二次输入框**收自定义文字 |
| 澄清记录格式 | **不変**，只记最终答案文字 |
| 自动模式 | **完全不受影响**，选择题仅在人工交互模式生效 |
| 默认回车行为 | **默认选 A**（`Prompt.ask` 默认值 = "A"） |
| 无选项降级 | **降级为纯自由输入**（老行为） |

## LLM Output Format Change

**Before（纯字符串数组）：**

```json
["认证方式应该怎么选？", "数据库用什么？"]
```

**After（对象数组，含选项）：**

```json
[
  {
    "question": "用户认证方式选哪种？",
    "options": ["JWT Token", "Session + Cookie", "OAuth 第三方登录"]
  },
  {
    "question": "数据库选型？",
    "options": ["PostgreSQL", "MySQL", "MongoDB"]
  }
]
```

要点：
- `options` 不带 A/B/C 前缀（字母由代码渲染时自动加）
- 每题 2-3 个 options（`CLARIFY_PROMPT` 明确要求）
- JSON 解析失败 / options 缺失 → **降级为纯自由输入**，永不崩溃
- 兼容老格式：纯字符串项当作「无选项的自由输入题」处理

## State Changes

`AgentState` **无变更**。`clarify_questions` 保持 `list[str]` 类型（只存问题文字），options 仅在渲染时使用，不入 state。自动模式和下游节点不受影响。

## Clarify Node Changes

### 1. 解析阶段

解析 LLM 返回的 JSON：
- 尝试按新格式 `[{question, options}]` 解析
- 若某元素是纯字符串 → 当无选项题处理
- 若整个 JSON 解析失败 → 降级为 `[raw]`

### 2. 交互阶段（仅人工模式，非 auto）

对每个问题循环：

```
┌─────────────────────────────────────┐
│  打印问题                            │
│  渲染选项（自动配 A. B. C. 前缀）       │
│  末尾固定 "T. Type something（自己输入）"│
│                                     │
│  Prompt.ask("请选择", choices=[...], │
│             default="A")            │
│                                     │
│  ├─ A/B/C → answer = 对应选项文字     │
│  └─ T     → Prompt.ask("请输入你的答案")│
│             → answer = 用户输入       │
└─────────────────────────────────────┘
```

如果该题无 options（降级）：直接走老逻辑 `Prompt.ask(问题)` 自由输入，不渲染选项。

choices 列表动态生成：有几个选项就放几个字母 + `"T"`（例如 2 个选项 = `["A","B","T"]`，3 个选项 = `["A","B","C","T"]`）。

`Prompt.ask` 使用 `choices` 参数 + `case_sensitive=False`，非法输入自动高亮提示并重问。

### 3. 自动模式（不受影响）

`auto_mode=True` 时完全不进入交互分支，LLM 自问自答逻辑保持不变。

## 终端渲染效果

```
澄清轮次 1

  用户认证方式选哪种？
    A. JWT Token
    B. Session + Cookie
    C. OAuth 第三方登录
    T. Type something（自己输入）
  请选择 [A/B/C/T] (默认: A): ▍
```

## Clarify Log

格式与现有完全一致，只记问答文字，不记选项结构：

```markdown
## 澄清轮次 1

**Q：** 用户认证方式选哪种？
**A：** JWT Token
```

## 代码结构优化

建议从 `clarify()` 中抽一个纯函数 `render_choices(question: str, options: list[str]) -> str`：

- 输入：问题文字 + 选项列表
- 输出：带 A/B/C 前缀的渲染字符串
- 纯函数、无副作用、可独立单元测试
- 交互循环只负责 `print(rendered)` + `Prompt.ask`

## Files Changed

| 文件 | 变更 |
|------|------|
| `src/agent/prompts.py` | 修改 `CLARIFY_PROMPT`，要求 LLM 输出 `[{question, options}]` 格式 |
| `src/agent/nodes/clarify.py` | 新增 JSON 解析兼容逻辑；新增 `render_choices()` 纯函数；人工交互改为选择题模式；默认回车 = A |
| `tests/nodes/test_clarify.py` | 新增 5 个测试 + 保持 2 个老测试通过 |

## Testing

### 现有测试（保持不变）

- `test_clarify_auto_mode_self_answers` — 自动模式逻辑不动
- `test_clarify_auto_mode_writes_clarify_log` — 日志格式不动

### 新增测试

| # | 测试名 | 覆盖 |
|---|--------|------|
| 1 | `test_parse_new_json_format` | LLM 返回 `[{question, options}]` → 正确解析问题 + 选项 |
| 2 | `test_parse_old_format_fallback` | LLM 返回 `["问题1", "问题2"]` → 降级自由输入、不崩溃 |
| 3 | `test_user_selects_option` | mock 用户按 B → `user_answers` 含对应选项文字 |
| 4 | `test_user_types_custom` | mock 用户按 T 再输入自定义 → `user_answers` 含自定义文字 |
| 5 | `test_clarify_log_unchanged` | 澄清记录只记问答文字，不记选项结构 |
