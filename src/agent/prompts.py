# src/agent/prompts.py
"""
所有节点的 system prompt。
通过 anthropic prompt caching 的 cache_control 传递。
"""

SYSTEM_BASE = """你是一名资深软件工程师，专注于需求分析和软件设计。
你的输出必须结构清晰、无歧义，使用中文，代码和图表使用 Mermaid 语法。"""

PROCESS_PROMPT = """分析用户描述，提取并补全以下字段（JSON格式输出）：
- functional: 功能需求列表
- non_functional: 非功能需求列表（性能、安全、可用性等）
- actors: 参与者/角色列表
- constraints: 约束条件列表
- open_questions: 仍不清楚或存在歧义的问题列表

如果描述中缺少字段，尝试从上下文推断，若无法推断则加入 open_questions。"""

JUDGE_PROMPT = """判断当前需求信息是否足够清晰、无歧义，可以进入设计阶段。
输出 JSON：{"is_clear": true/false, "reason": "简短说明"}
判断标准：
- functional 列表非空
- open_questions 为空或已全部澄清
- 没有互相矛盾的约束"""

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

AUTO_ANSWER_PROMPT = """你正在帮助澄清软件需求。请站在用户/产品经理的角度，基于已知需求信息合理推测以下问题的答案。给出简洁、合理的回答，不要编造超出合理范围的内容。

请以 JSON 数组格式输出答案，与问题一一对应。每个答案控制在 1-2 句话。"""

REQ_DOC_PROMPT = """根据需求信息生成完整的《需求说明书》，Markdown 格式，包含：
## 1. 项目概述
## 2. 功能需求（用户故事格式）
## 3. 非功能需求
## 4. 系统约束
## 5. 参与者与角色
## 6. 用例图（Mermaid）
末尾附上澄清记录摘要。"""

HIGH_LEVEL_PROMPT = """根据需求说明书生成《总体设计文档》，Markdown 格式，包含：
## 1. 系统架构概述
## 2. 架构图（Mermaid graph TD）
## 3. 模块划分与职责
## 4. 技术选型与依据
## 5. 数据流图（Mermaid sequenceDiagram）
## 6. 关键接口定义（概要）"""

DETAIL_PROMPT = """根据总体设计文档生成《详细设计文档》，Markdown 格式，包含：
## 1. 各模块详细设计
## 2. 类图（Mermaid classDiagram）
## 3. 序列图（核心流程，Mermaid sequenceDiagram）
## 4. 数据库/数据结构设计（Mermaid erDiagram 或表格）
## 5. 接口详细定义（输入/输出/错误码）
## 6. 算法说明（如有）"""
