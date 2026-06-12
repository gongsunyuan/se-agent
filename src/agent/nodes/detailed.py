# src/agent/nodes/detailed.py
import json
import re
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import (
    SYSTEM_BASE, DETAIL_PROMPT,
    DETAIL_MODULE_EXTRACT_PROMPT, DETAIL_MODULE_GEN_PROMPT, DETAIL_MERGE_PROMPT,
)
from agent.logger import log_execution


def extract_modules(high_level_doc_path: Path, max_retries: int = 3) -> list[str]:
    """Phase 1: 从总体设计文档中提取领域模块列表。"""
    client = get_llm_client()

    if not high_level_doc_path or not high_level_doc_path.exists():
        return []

    hl_content = high_level_doc_path.read_text(encoding="utf-8")

    for attempt in range(1, max_retries + 1):
        try:
            raw = client.create_message(
                system_prompts=[
                    {"type": "text", "text": DETAIL_MODULE_EXTRACT_PROMPT, "cache_control": {"type": "ephemeral"}},
                ],
                user_content=hl_content,
                max_tokens=1024,
                node_name="extract_modules",
            )

            # 解析 JSON 数组
            raw = raw.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)

            modules = json.loads(raw)
            if isinstance(modules, list) and len(modules) >= 2:
                return modules[:6]  # 限制最多 6 个

            return []

        except json.JSONDecodeError:
            # JSON 解析失败：正则兜底
            # 统一提取所有引号包裹的模块名（单模块匹配，避免成对匹配丢奇数模块）
            fallback = re.findall(r'[“”"]([^“”"]{2,6}(?:模块|系统|管理|服务|中心|平台))[“”"]', raw)
            if len(fallback) >= 2:
                return fallback[:6]

            # 无引号兜底：用、或，分隔的中文模块名
            no_quote = re.findall(r'([\u4e00-\u9fff]{2,6}(?:模块|系统|管理))', raw)
            if len(no_quote) >= 2:
                return no_quote[:6]

            return []

        except Exception:
            if attempt >= max_retries:
                return []

    return []


def detailed_design(state: AgentState) -> dict:
    client = get_llm_client()

    hl_content = ""
    if state.get("high_level_doc_path"):
        hl_content = Path(state["high_level_doc_path"]).read_text(encoding="utf-8")

    content = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": DETAIL_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=hl_content or "根据总体设计生成详细设计",
        max_tokens=8192,
        node_name="detail",
    )

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "详细设计.md"
    doc_path.write_text(content, encoding="utf-8")

    log_execution(
        "detail",
        input_summary=f"high_level_doc={state.get('high_level_doc_path', 'N/A')}",
        decision="generated detailed design document",
        output_summary=f"doc={doc_path}",
    )

    return {"detail_doc_path": str(doc_path)}
