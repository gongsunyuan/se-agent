# Choice Button Implementation Plan — 澄清阶段选择题

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 澄清节点从纯自由输入升级为选择题（A/B/C + T.Type something），回车默认选 A。

**Architecture:** 修改 CLARIFY_PROMPT 使 LLM 输出 `{question, options}` 格式；在 clarify 节点内新增 `render_choices()` 纯函数渲染选项，用 `Prompt.ask(choices=[...], default="A")` 做受限选择；JSON 解析失败时降级为老行为。

**Tech Stack:** Python, rich.prompt.Prompt, LangGraph

---

### Task 1: 修改 CLARIFY_PROMPT → LLM 输出新格式

**Files:**
- Modify: `src/agent/prompts.py`

- [ ] **Step 1: 修改 CLARIFY_PROMPT**

将 `CLARIFY_PROMPT` 从：

```python
CLARIFY_PROMPT = """基于以下未解决的问题，生成 2-3 个精准的澄清问题（数组格式）。
问题应该具体、可回答，避免模糊。"""
```

改为：

```python
CLARIFY_PROMPT = """基于以下未解决的问题，生成 2-3 个精准的澄清问题。

每道题除了问题本身，还需给出 2-3 个候选选项（即选择题），让用户从中选择。

请严格输出以下 JSON 数组格式：
[
  {
    "question": "问题文字",
    "options": ["选项A", "选项B", "选项C"]
  }
]

要求：
- 每道题必须有 2-3 个选项
- 选项文字简洁（每个 1-10 个字），能覆盖最合理的几种可能性
- 问题具体、可回答，避免模糊
- 如果某个问题确实不适合做选择题（比如开放式长文本输入），可以设 options 为空数组 []"""
```

- [ ] **Step 2: 运行现有测试确保 prompt 修改不影响自动模式**

```bash
python -m pytest tests/nodes/test_clarify.py -v
```
Expected: 2 tests PASS（自动模式测试不受影响，因为它们 mock 了 LLM 返回值）

- [ ] **Step 3: Commit**

```bash
git add src/agent/prompts.py
git commit -m "feat: update CLARIFY_PROMPT to output {question, options} format"
```

---

### Task 2: 新增 render_choices() 纯函数

**Files:**
- Modify: `src/agent/nodes/clarify.py`
- Create test in: `tests/nodes/test_clarify.py`

- [ ] **Step 1: 写测试 — render_choices 正常渲染**

在 `tests/nodes/test_clarify.py` 末尾新增：

```python
from agent.nodes.clarify import render_choices


def test_render_choices_normal():
    """render_choices 生成带 A/B/C 编号的选项字符串。"""
    result = render_choices("数据库选型？", ["PostgreSQL", "MySQL", "MongoDB"])
    assert "数据库选型？" in result
    assert "A. PostgreSQL" in result
    assert "B. MySQL" in result
    assert "C. MongoDB" in result
    assert "T. Type something" in result


def test_render_choices_two_options():
    """2 个选项时只渲染 A、B。"""
    result = render_choices("认证方式？", ["JWT", "Session"])
    assert "A. JWT" in result
    assert "B. Session" in result
    assert "C." not in result
    assert "T. Type something" in result


def test_render_choices_no_options():
    """空选项列表返回空字符串。"""
    result = render_choices("随便问个问题", [])
    assert result == ""
```

- [ ] **Step 2: 运行测试 → 应 FAIL（函数不存在）**

```bash
python -m pytest tests/nodes/test_clarify.py::test_render_choices_normal tests/nodes/test_clarify.py::test_render_choices_two_options tests/nodes/test_clarify.py::test_render_choices_no_options -v
```
Expected: 3 FAIL, `NameError: name 'render_choices' is not defined`

- [ ] **Step 3: 实现 render_choices()**

在 `src/agent/nodes/clarify.py` 文件末尾（classify 函数定义之后）添加：

```python
def render_choices(question: str, options: list[str]) -> str:
    """将问题和选项渲染为终端显示字符串。不带选项时返回空字符串。"""
    if not options or len(options) == 0:
        return ""
    letters = []
    for i in range(len(options)):
        letters.append(chr(65 + i))  # 65 = 'A'
    lines = [f"  {question}"]
    for letter, opt in zip(letters, options):
        lines.append(f"    {letter}. {opt}")
    lines.append("    T. Type something（自己输入）")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试 → 应 PASS**

```bash
python -m pytest tests/nodes/test_clarify.py::test_render_choices_normal tests/nodes/test_clarify.py::test_render_choices_two_options tests/nodes/test_clarify.py::test_render_choices_no_options -v
```
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent/nodes/clarify.py tests/nodes/test_clarify.py
git commit -m "feat: add render_choices() pure function for choice rendering"
```

---

### Task 3: 新增 JSON 解析兼容逻辑（新格式 + 老格式降级）

**Files:**
- Modify: `src/agent/nodes/clarify.py` — `clarify()` 函数内解析段
- Create test in: `tests/nodes/test_clarify.py`

- [ ] **Step 1: 写测试 — 新格式解析**

在 `test_clarify.py` 中新增：

```python
@patch("agent.nodes.clarify.get_llm_client")
def test_parse_new_json_format(mock_get_client, tmp_path):
    """LLM 返回 [{question, options}] 格式 → 正确解析问题与选项。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
        {"question": "数据库？", "options": ["Pg", "MySQL"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["A", "B"]
        result = clarify(state)

    assert result["clarify_questions"] == ["认证方式？", "数据库？"]
    assert result["user_answers"] == ["JWT", "MySQL"]
    assert result["clarification_round"] == 1


@patch("agent.nodes.clarify.get_llm_client")
def test_parse_old_format_fallback(mock_get_client, tmp_path):
    """LLM 返回老格式 ["q1", "q2"] → 降级为自由输入，不崩溃。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = '["问题1", "问题2"]'
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["自由答案1", "自由答案2"]
        result = clarify(state)

    assert result["clarify_questions"] == ["问题1", "问题2"]
    assert result["user_answers"] == ["自由答案1", "自由答案2"]
```

注意：需要在 `test_clarify.py` 顶部新增 `import json`。

- [ ] **Step 2: 运行测试 → FAIL**

```bash
python -m pytest tests/nodes/test_clarify.py::test_parse_new_json_format tests/nodes/test_clarify.py::test_parse_old_format_fallback -v
```
Expected: 2 FAIL

- [ ] **Step 3: 修改 clarify() 解析逻辑**

将 `clarify()` 中解析 JSON 后的处理改为抽一个 `_parse_questions()` 内部函数。找到 `src/agent/nodes/clarify.py` 中以下代码：

```python
    try:
        questions = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", stripped, re.DOTALL)
        try:
            questions = json.loads(match.group()) if match else [raw]
        except json.JSONDecodeError:
            questions = [raw]
```

在其下方新增：

```python
    # 规范化为统一格式：[(question_text, options_list_or_none), ...]
    parsed_questions: list[tuple[str, list[str] | None]] = []
    for item in questions:
        if isinstance(item, dict):
            q = item.get("question", "")
            opts = item.get("options", [])
            if not isinstance(opts, list):
                opts = []
            parsed_questions.append((q, opts))
        elif isinstance(item, str):
            parsed_questions.append((item, None))
```

然后修改后面的交互逻辑（先在 Task 3 完成解析，Task 4 改交互）。

- [ ] **Step 4: 运行解析相关测试 → SHOULD PASS if just parsing, but will FAIL due to interaction rewrite**

```bash
python -m pytest tests/nodes/test_clarify.py::test_parse_new_json_format tests/nodes/test_clarify.py::test_parse_old_format_fallback -v
```
Expected: will fail — interactive logic not rewritten yet → proceed to Task 4

- [ ] **Step 5: Commit**

```bash
git add src/agent/nodes/clarify.py tests/nodes/test_clarify.py
git commit -m "feat: parse new {question, options} format with old-format fallback"
```

---

### Task 4: 实现选择题交互循环（A/B/C + T.Type something + 默认 A）

**Files:**
- Modify: `src/agent/nodes/clarify.py` — `clarify()` 函数内交互段
- Create test in: `tests/nodes/test_clarify.py`

- [ ] **Step 1: 写测试 — 用户选选项**

在 `test_clarify.py` 中新增：

```python
@patch("agent.nodes.clarify.get_llm_client")
def test_user_selects_option(mock_get_client, tmp_path):
    """用户选 B → user_answers 含对应选项文字。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session", "OAuth"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["B"]
        result = clarify(state)

    assert result["user_answers"] == ["Session"]


@patch("agent.nodes.clarify.get_llm_client")
def test_user_types_custom(mock_get_client, tmp_path):
    """用户选 T 再输入自定义文字 → user_answers 含自定义文字。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        # 第一次 ask 选 T，第二次 ask 是自定义输入
        mock_prompt.ask.side_effect = ["T", "使用 Firebase Auth"]
        result = clarify(state)

    assert result["user_answers"] == ["使用 Firebase Auth"]


@patch("agent.nodes.clarify.get_llm_client")
def test_user_default_enter_selects_a(mock_get_client, tmp_path):
    """Prompt.ask 传入 default='A'。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        # 模拟回车（返回默认值 A）
        mock_prompt.ask.return_value = "A"
        result = clarify(state)

    # 验证 Prompt.ask 被调用时传了 default="A"
    call_kwargs = mock_prompt.ask.call_args_list[0][1]
    assert call_kwargs.get("default") == "A"
    assert result["user_answers"] == ["JWT"]
```

- [ ] **Step 2: 运行测试 → FAIL**

```bash
python -m pytest tests/nodes/test_clarify.py::test_user_selects_option tests/nodes/test_clarify.py::test_user_types_custom tests/nodes/test_clarify.py::test_user_default_enter_selects_a -v
```
Expected: 3 FAIL（交互逻辑还是老的）

- [ ] **Step 3: 重写 clarify() 中的交互逻辑**

找到 `clarify()` 中人工交互段（`else:` 分支），替换为：

```python
    else:
        console.print(f"\n[bold yellow]澄清轮次 {state['clarification_round'] + 1}[/bold yellow]")
        for q_text, opts in parsed_questions:
            if opts and len(opts) > 0:
                # 有选项 → 选择题
                rendered = render_choices(q_text, opts)
                console.print(rendered)
                letters = [chr(65 + i) for i in range(len(opts))] + ["T"]
                answer_letter = Prompt.ask(
                    "  请选择",
                    choices=letters,
                    default="A",
                    case_sensitive=False,
                )
                if answer_letter.upper() == "T":
                    answer = Prompt.ask("  请输入你的答案")
                else:
                    idx = ord(answer_letter.upper()) - 65  # 'A'=0, 'B'=1, ...
                    answer = opts[idx]
            else:
                # 无选项 → 自由输入（老行为）
                answer = Prompt.ask(f"  [cyan]{q_text}[/cyan]")
            answers.append(answer)
```

- [ ] **Step 4: 运行全部 clarify 测试 → 应 PASS**

```bash
python -m pytest tests/nodes/test_clarify.py -v
```
Expected: 10 PASS（2 个老 + 3 个 render_choices + 2 个解析 + 3 个交互）

- [ ] **Step 5: Commit**

```bash
git add src/agent/nodes/clarify.py tests/nodes/test_clarify.py
git commit -m "feat: implement choice-based (A/B/C/T) clarify interaction with default=A"
```

---

### Task 5: 验证澄清记录格式不变

**Files:**
- Create test in: `tests/nodes/test_clarify.py`

- [ ] **Step 1: 写测试 — 澄清记录只记问答文字**

在 `test_clarify.py` 末尾新增：

```python
@patch("agent.nodes.clarify.get_llm_client")
def test_clarify_log_unchanged(mock_get_client, tmp_path):
    """澄清记录.md 只记问答文字，不记选项结构。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["B"]
        clarify(state)

    clarify_path = output_dir / "澄清记录.md"
    assert clarify_path.exists()
    content = clarify_path.read_text(encoding="utf-8")
    assert "认证方式？" in content
    assert "Session" in content
    assert "澄清轮次 1" in content
    # 不应包含选项结构
    assert "JWT" not in content
    assert "options" not in content
```

- [ ] **Step 2: 运行测试 → PASS**

```bash
python -m pytest tests/nodes/test_clarify.py::test_clarify_log_unchanged -v
```
Expected: PASS（澄清记录格式本就不变，这个测试只是显式验证）

- [ ] **Step 3: 运行全部测试最终确认**

```bash
python -m pytest tests/ -v
```
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/nodes/test_clarify.py
git commit -m "test: add clarify log format regression test"
```

---

## 自审

| 检查项 | 结果 |
|--------|------|
| **Spec 覆盖**：每个需求都能对应到一个 Task | ✅ Task 1=prompt, Task 2=渲染, Task 3=解析, Task 4=交互, Task 5=日志 |
| **无占位符**：所有 step 都有完整代码 | ✅ |
| **类型一致**：`render_choices(question: str, options: list[str]) -> str`，`parsed_questions: list[tuple[str, list[str] \| None]]`，全程一致 | ✅ |
