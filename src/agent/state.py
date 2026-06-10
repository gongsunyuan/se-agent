# src/agent/state.py
from typing import TypedDict, Optional
from pathlib import Path


class Requirements(TypedDict, total=False):
    functional: list[str]
    non_functional: list[str]
    actors: list[str]
    constraints: list[str]
    open_questions: list[str]


class AgentState(TypedDict):
    raw_input: str
    auto_mode: bool  # 默认 False，--auto 时为 True
    requirements: Requirements
    clarification_round: int
    max_clarification_rounds: int
    is_clear: bool
    clarify_questions: list[str]
    user_answers: list[str]
    req_doc_confirmed: bool
    high_level_confirmed: bool
    revision_comment: Optional[str]
    output_dir: Path
    req_doc_path: Optional[str]
    high_level_doc_path: Optional[str]
    detail_doc_path: Optional[str]
    messages: list
    errors: list[str]
    uml_diagram_files: list[str]  # 生成的 .puml 文件路径列表
