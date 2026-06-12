# src/agent/nodes/detailed.py
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def gen_module(
    high_level_doc_path: Path,
    module_name: str,
    max_retries: int = 3,
) -> str | None:
    """Phase 2: 为单个领域模块生成详细设计片段。"""
    client = get_llm_client()
    hl_content = high_level_doc_path.read_text(encoding="utf-8")

    user_content = f"# 总体设计\n\n{hl_content}\n\n---\n\n请为以下模块生成详细设计：**{module_name}**"

    for attempt in range(1, max_retries + 1):
        try:
            content = client.create_message(
                system_prompts=[
                    {"type": "text", "text": DETAIL_MODULE_GEN_PROMPT, "cache_control": {"type": "ephemeral"}},
                ],
                user_content=user_content,
                max_tokens=4096,
                node_name=f"gen_module_{module_name}",
            )
            return content
        except Exception:
            if attempt >= max_retries:
                return None

    return None


def merge_and_review(
    high_level_doc_path: Path,
    module_outputs: dict[str, str],
    max_retries: int = 3,
) -> str:
    """Phase 3: 汇总所有模块的详细设计片段，输出完整《详细设计.md》。"""
    client = get_llm_client()
    hl_content = high_level_doc_path.read_text(encoding="utf-8")

    parts = [f"# 总体设计\n\n{hl_content}\n\n---\n\n"]
    for name, content in module_outputs.items():
        parts.append(f"## 模块: {name}\n\n{content}\n\n---\n\n")

    user_content = "\n".join(parts)

    for attempt in range(1, max_retries + 1):
        try:
            content = client.create_message(
                system_prompts=[
                    {"type": "text", "text": DETAIL_MERGE_PROMPT, "cache_control": {"type": "ephemeral"}},
                ],
                user_content=user_content,
                max_tokens=12800,
                node_name="merge_detail",
            )
            return content
        except Exception:
            if attempt >= max_retries:
                # 兜底拼接
                header = "# 详细设计文档\n\n> 注意：汇总 LLM 调用失败，以下为各模块设计片段的简单拼接。\n\n"
                body = "\n\n---\n\n".join(
                    f"## {name}\n\n{content}" for name, content in module_outputs.items()
                )
                return header + body


def detailed_design(state: AgentState) -> dict:
    """生成《详细设计.md》—— 支持 subagent 并发机制。"""
    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    hl_path_str = state.get("high_level_doc_path")
    if not hl_path_str:
        return _fallback_single_llm(state, "总体设计文档路径缺失")

    hl_path = Path(hl_path_str)
    if not hl_path.exists():
        return _fallback_single_llm(state, "总体设计文档不存在")

    max_workers = int(os.environ.get("DETAIL_MAX_WORKERS", "12"))
    max_retries = int(os.environ.get("DETAIL_MODULE_MAX_RETRIES", "3"))

    # Phase 1: 提取模块
    modules = extract_modules(hl_path, max_retries=max_retries)
    log_execution(
        "detail_extract",
        input_summary=f"high_level_doc={hl_path_str}",
        decision=f"extracted {len(modules)} modules",
        output_summary=f"modules={modules}",
    )

    if len(modules) < 2:
        log_execution(
            "detail_extract",
            input_summary=f"modules={modules}",
            decision="fallback to single LLM mode",
            output_summary="too few modules",
        )
        return _fallback_single_llm(state, f"模块数不足（{len(modules)}），回退单次模式")

    # Phase 2: 并发生成各模块
    module_outputs: dict[str, str] = {}
    errors = state.get("errors", []).copy()

    def _gen_with_log(module_name: str) -> tuple[str, str | None]:
        result = gen_module(hl_path, module_name, max_retries=max_retries)
        if result is not None:
            log_execution(
                f"detail_module_{module_name}",
                input_summary=f"module={module_name}",
                decision="generated",
                output_summary=f"len={len(result)} chars",
            )
        else:
            log_execution(
                f"detail_module_{module_name}",
                input_summary=f"module={module_name}",
                decision="failed",
                output_summary="all retries exhausted",
            )
        return (module_name, result)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_gen_with_log, m): m for m in modules}
        for future in as_completed(futures):
            name, content = future.result()
            if content is not None:
                module_outputs[name] = content

    if not module_outputs:
        errors.append("detail: all modules failed to generate")
        result = _fallback_single_llm(state, "所有模块生成失败，回退单次模式")
        result["errors"] = errors
        return result

    skipped = [m for m in modules if m not in module_outputs]
    if skipped:
        errors.append(f"detail: skipped modules: {skipped}")

    # Phase 3: 汇总合并
    merged = merge_and_review(hl_path, module_outputs, max_retries=max_retries)
    doc_path = output_dir / "详细设计.md"
    doc_path.write_text(merged, encoding="utf-8")

    log_execution(
        "detail",
        input_summary=f"modules={len(modules)}, generated={len(module_outputs)}, skipped={len(skipped)}",
        decision="generated detailed design via subagent concurrency",
        output_summary=f"doc={doc_path}, size={len(merged)} chars",
    )

    return {
        "detail_doc_path": str(doc_path),
        "detail_modules": modules,
        "detail_module_outputs": module_outputs,
        "errors": errors,
    }


def _fallback_single_llm(state: AgentState, reason: str) -> dict:
    """回退到原单次 LLM 生成模式。"""
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
        node_name="detail_fallback",
    )

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "详细设计.md"
    doc_path.write_text(content, encoding="utf-8")

    log_execution(
        "detail_fallback",
        input_summary=f"reason={reason}",
        decision="used fallback single-LLM mode",
        output_summary=f"doc={doc_path}",
    )

    return {
        "detail_doc_path": str(doc_path),
        "detail_modules": [],
        "detail_module_outputs": {},
    }
