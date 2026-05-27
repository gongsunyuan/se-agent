# Auto-Mode Design

## Overview

为 se-agent 加入全自动模式（`--auto`），运行时除初始 prompt 外不需要任何用户输入，完全自动化生成 outputs。同时为所有模式加入 LLM 调用 trace log 和节点级执行摘要，便于 debug。

## State Changes

`AgentState` 新增一个字段：

```python
auto_mode: bool  # 默认 False
```

## Graph Changes

`build_graph()` 接受 `auto_mode: bool = False` 参数。

Auto 模式下，graph 边结构发生变化——checkpoint 节点被完全绕过：

```
gen_req_doc → (条件边) → high_level       [auto]
                        → checkpoint_a     [normal]

high_level  → (条件边) → detail           [auto]
                        → checkpoint_b     [normal]
```

实现方式：
- 新增 `_route_after_gen_req(state)` 和 `_route_after_high_level(state)` 两个路由函数
- 将 `gen_req_doc` 的出边从 `add_edge("gen_req_doc", "checkpoint_a")` 改为 `add_conditional_edges`
- 将 `high_level` 的出边从 `add_edge("high_level", "checkpoint_b")` 改为 `add_conditional_edges`
- `checkpoint_a` → `high_level` / `checkpoint_b` → `detail` 的边在 auto 模式下永远不被触发，但不影响正确性

Judge → clarify → process 的澄清 loop 保持不变。auto 模式下 clarify 通过自问自答处理。

## Clarify Self-Answering

`clarify` 节点内，当 `state["auto_mode"]` 为 `True` 时：

1. LLM 生成澄清问题（与交互模式一致）
2. 将问题列表再次送 LLM，prompt 要求站在用户角度合理推测答案
3. 问题+答案写入 `澄清记录.md`，格式与交互模式一致
4. `user_answers` 填入 LLM 生成的答案，`clarification_round` +1

自答 LLM 调用：max_tokens=512，prompt 要求简洁回答，基于需求上下文推断，不编造。

## CLI Changes

`run` 命令新增 `--auto` / `--auto-mode` flag：

```
--auto / --auto-mode: bool = False
```

Auto 模式下 CLI 行为：

1. 初始 state 设 `auto_mode=True`
2. `build_graph(auto_mode=True)` 构建时生成跳过 checkpoint 的图结构
3. 首次 stream 后不进入 `while True` interrupt resume loop——图中无 interrupt 节点，`state.next` 直接为空
4. 输出目录结构与交互模式完全一致

## Log System (All Modes)

两个 log 文件写入 `output_dir`：

### trace.log

每行一条 JSON 记录，由 `LLMClient.create_message()` 统一写入：

```json
{
  "timestamp": "2026-05-27T10:30:00",
  "node": "clarify",
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "system_prompts": "...",
  "user_content": "...",
  "response": "...",
  "max_tokens": 512
}
```

对所有 LLM 调用透明，无需各节点改动。

### execution.log

Markdown 格式，每个节点一条摘要记录：

```markdown
## [2026-05-27 10:30:00] clarify (round 1)
**输入**: open_questions=3, requirements.functional=5
**决策**: 生成 3 个澄清问题，auto 模式自答
**输出**: user_answers=3, clarification_round=2
```

由新增的 `logger.py` 提供 `log_execution()` 函数，各节点调用写入。

## Files Changed

| 文件 | 变更 |
|---|---|
| `src/agent/state.py` | 新增 `auto_mode: bool` |
| `src/agent/graph.py` | `build_graph(auto_mode)` 参数，条件边绕过 checkpoint |
| `src/agent/cli.py` | 新增 `--auto` flag，auto 模式跳过 interrupt resume loop |
| `src/agent/nodes/clarify.py` | auto 模式 LLM 自问自答 |
| `src/agent/config.py` | `LLMClient.create_message()` 新增 trace log 写入 |
| 新增 `src/agent/logger.py` | 统一 log 模块：`log_trace()` + `log_execution()` |

## Testing

- `tests/test_auto_mode.py`：mock LLMClient，验证 auto 模式下各节点行为
- 验证 clarify 自问自答：LLM 返回问题后第二次调用 LLM 自答
- 验证 graph 在 auto 模式下 gen_req_doc → high_level → detail 直达路径
- 验证 CLI `--auto` flag 正确传递到 state
- 验证 trace.log 和 execution.log 文件正确生成
