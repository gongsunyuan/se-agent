# se-agent

> 需求分析 + 软件设计 AI Agent — 输入自然语言需求，自动产出三份结构化设计文档。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

se-agent 是一个基于 LangGraph 的 LLM 流水线工具。你只需要用自然语言描述需求，Agent 就会自动完成结构化需求提取、澄清问答、需求说明书生成、总体设计、详细设计等全流程工作，最终输出三份带 Mermaid 图表的 Markdown 设计文档。

## 功能特性

- **结构化需求提取** — 从自然语言中自动提取功能需求、非功能需求、参与者、约束条件和待澄清问题
- **交互式澄清** — 对模糊点生成精准问题，支持多轮对话直到需求足够清晰
- **三份产出文档**:
  - `需求说明.md` — 包含用户故事、用例图（Mermaid）
  - `总体设计.md` — 包含架构图、数据流图、技术选型
  - `详细设计.md` — 包含类图、序列图、ER 图、接口定义
- **人工审核节点** — 通过 LangGraph interrupt 在关键阶段暂停，等待人工确认
- **双 LLM 后端** — 同时支持 Anthropic SDK 和 OpenAI SDK，自动检测或手动切换
- **自动测试模式** — 用 LLM 替代人工审核，支持全自动端到端测试
- **PDF 导出** — 通过 pandoc + mermaid-filter + XeLaTeX 将文档导出为 PDF

## 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone <repo-url> && cd se-agent

# 创建虚拟环境（推荐）
conda create -n se-agent python=3.11 -y && conda activate se-agent

# 安装
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```env
ANTHROPIC_API_KEY=sk-your-key-here

# 可选：自定义 API 端点（如 one-api / liteLLM 代理）
ANTHROPIC_BASE_URL=https://api.openai.com/v1

# 可选：强制指定提供者（anthropic / openai）
LLM_PROVIDER=openai

# 可选：模型 ID（默认 claude-sonnet-4-6）
MODEL_ID=deepseek/deepseek-v4-pro
```

### 3. 运行

```bash
se-agent "构建一个在线图书馆系统，支持借阅、归还、搜索功能"
```

Agent 将依次执行各阶段，在需求文档和总体设计完成后会暂停等待你的确认。

## 流水线架构

```
用户输入 (自然语言)
       │
       ▼
  ┌─────────┐     ┌─────────┐     ┌──────────┐
  │ process  │────▶│  judge   │────▶│ clarify  │◀──┐
  │ 结构化提取│     │ 清晰度判断│     │ 生成澄清问题│   │
  └─────────┘     └────┬─────┘     └────┬─────┘   │
                       │                │         │
                       │ 不够清晰        │ 用户回答  │
                       └───────────────▶│─────────┘
                       │
                       │ 足够清晰
                       ▼
                ┌─────────────┐
                │ gen_req_doc  │
                │ 生成需求说明书│
                └──────┬──────┘
                       ▼
              ╔═══════════════╗
              ║ checkpoint A  ║ ← 人工确认 / LLM 审查
              ╚═══════╤═══════╝
                      ▼
                ┌─────────────┐
                │ high_level   │
                │ 生成总体设计  │
                └──────┬──────┘
                       ▼
              ╔═══════════════╗
              ║ checkpoint B  ║ ← 人工确认 / LLM 审查
              ╚═══════╤═══════╝
                      ▼
                ┌─────────────┐
                │   detail     │
                │ 生成详细设计  │
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │     END      │
                └─────────────┘
```

### 七个核心节点

| 节点 | 功能 | 输出 |
|------|------|------|
| `process` | 从原始需求提取结构化信息 | `Requirements` (functional, non-functional, actors, constraints, open_questions) |
| `judge` | 判断需求是否足够清晰 | `is_clear` (规则优先，回退 LLM) |
| `clarify` | 生成澄清问题并收集回答 | Q&A 追加到 `澄清记录.md` |
| `gen_req_doc` | 生成需求说明书 | `需求说明.md`（含用例图） |
| `checkpoint_a` | 中断，等待人工确认需求文档 | 确认/修改意见 |
| `high_level` | 生成总体设计 | `总体设计.md`（含架构图、数据流图） |
| `checkpoint_b` | 中断，等待人工确认总体设计 | 确认/修改意见 |
| `detail` | 生成详细设计 | `详细设计.md`（含类图、序列图、ER 图） |

### LLM 双后端抽象

`LLMClient` 统一封装 Anthropic 和 OpenAI 两种后端：

- **Anthropic 路径**: 保留 `cache_control: ephemeral`，使用 Messages API
- **OpenAI 路径**: 自动剥离 `cache_control`，将 system prompt 映射为 messages

后端自动检测规则：`LLM_PROVIDER` 环境变量 > `ANTHROPIC_BASE_URL` 启发式 > 默认 Anthropic。

## 配置参考

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `ANTHROPIC_API_KEY` | 是 | API Key（Anthropic 或代理端点） |
| `ANTHROPIC_BASE_URL` | 否 | 自定义 API 端点，设为非 `api.anthropic.com` 时自动切换为 OpenAI 兼容模式 |
| `LLM_PROVIDER` | 否 | 强制指定 `"openai"` 或 `"anthropic"` |
| `MODEL_ID` | 否 | 模型 ID，默认 `claude-sonnet-4-6` |

## 用法

### CLI

```bash
# 基本用法
se-agent "构建一个任务管理系统"

# 指定输出目录和最大澄清轮次
se-agent "构建一个在线图书馆系统" \
  --output-dir outputs/my-project \
  --max-rounds 3

# 指定 thread-id（用于中断恢复）
se-agent "..." --thread-id my-session-001
```

### 自动测试脚本

用于无人值守的端到端测试，用 LLM 替代人工审核：

```bash
# Simple 模式 — 全部自动确认，快速验证流水线
python scripts/auto_test.py "构建一个待办事项管理系统" --mode simple

# Review 模式 — LLM 审查文档质量，可能走 revise 分支
python scripts/auto_test.py "构建一个在线图书馆系统" --mode review

# 可选参数
python scripts/auto_test.py "需求描述" \
  --mode review \
  --max-rounds 5 \
  --output-dir outputs/my-test
```

### PDF 导出

```bash
# 将生成的设计文档转为 PDF（需要 pandoc 环境）
python scripts/export_pdf.py outputs/<session-id>
```

## 开发

### 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 单个测试文件
python -m pytest tests/test_llm_client.py -v

# 单个测试
python -m pytest tests/test_llm_client.py::TestGetLLMClient -v
```

所有测试使用 mock LLM 客户端，无需真实 API Key。

### 代码检查

```bash
ruff check src/ tests/
```

### 项目结构

```
se-agent/
├── src/agent/
│   ├── cli.py              # Typer CLI 入口
│   ├── config.py           # LLM 配置 + LLMClient 双后端抽象
│   ├── graph.py            # LangGraph 图定义 + 路由
│   ├── state.py            # AgentState / Requirements TypedDict
│   ├── prompts.py          # 所有节点的 system prompt
│   └── nodes/
│       ├── process.py      # 需求结构化提取
│       ├── judge.py        # 需求清晰度判断
│       ├── clarify.py      # 交互式澄清问答
│       ├── gen_req_doc.py  # 需求说明书生成
│       ├── high_level.py   # 总体设计生成
│       ├── detailed.py     # 详细设计生成
│       └── checkpoints.py  # LangGraph interrupt 节点
├── scripts/
│   ├── auto_test.py        # 自动测试脚本（LLM 替代人工）
│   ├── export_pdf.py       # Markdown → PDF 导出
│   └── export_pdf.sh       # PDF 导出（bash 版）
├── tests/
│   ├── conftest.py         # 共享 fixtures
│   ├── test_llm_client.py  # LLMClient 测试（15 个）
│   ├── test_graph_wiring.py# 图拓扑测试
│   ├── test_state.py       # 状态类型测试
│   └── nodes/
│       ├── test_process.py
│       ├── test_judge.py
│       └── test_gen_req_doc.py
├── pyproject.toml          # 项目配置 + 依赖
├── .env.example            # 环境变量模板
└── outputs/                # 生成的设计文档（gitignore）
```

## 技术栈

| 组件 | 用途 |
|------|------|
| [LangGraph](https://github.com/langchain-ai/langgraph) | 图编排 + 状态管理 + interrupt 机制 |
| [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) | Anthropic API + prompt caching |
| [OpenAI SDK](https://github.com/openai/openai-python) | OpenAI 兼容端点 |
| [Typer](https://typer.tiangolo.com/) | CLI 框架 |
| [Rich](https://github.com/Textualize/rich) | 终端美化输出 |
| [Pydantic](https://docs.pydantic.dev/) | 数据验证 |
| SQLite (SqliteSaver) | LangGraph 状态持久化 |

## License

MIT
