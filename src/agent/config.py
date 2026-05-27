# src/agent/config.py
import json
import os
from dotenv import load_dotenv
import anthropic
import openai

load_dotenv(override=True)

# 供节点直接 import 使用的模型 ID
MODEL_ID: str = os.getenv("MODEL_ID", "claude-sonnet-4-6")


def get_llm_config() -> dict:
    """返回 LLM 配置字典"""
    return {
        "api_key": os.environ["ANTHROPIC_API_KEY"],
        "base_url": os.getenv("ANTHROPIC_BASE_URL"),
        "model_id": MODEL_ID,
    }


def get_client() -> anthropic.Anthropic:
    """仅创建 Anthropic 客户端（向后兼容）"""
    cfg = get_llm_config()
    kwargs = {"api_key": cfg["api_key"]}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return anthropic.Anthropic(**kwargs)


class LLMClient:
    """统一的 LLM 客户端，同时支持 Anthropic SDK 和 OpenAI SDK。

    根据 provider 参数自动选择底层 SDK：
    - "anthropic": 使用 anthropic.Anthropic，保留 cache_control
    - "openai": 使用 openai.OpenAI，system prompt 映射到 messages，
      cache_control 自动剥离
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "claude-sonnet-4-6",
    ):
        self.provider = provider
        self.model_id = model_id

        if provider == "openai":
            kwargs: dict = {"api_key": api_key}
            kwargs["base_url"] = base_url or "https://api.openai.com/v1"
            self._client = openai.OpenAI(**kwargs)
        else:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = anthropic.Anthropic(**kwargs)

    def create_message(
        self,
        system_prompts: list[dict],
        user_content: str,
        max_tokens: int = 2048,
        node_name: str = "",
    ) -> str:
        """发送消息并返回模型响应文本。

        Args:
            system_prompts: system prompt 块列表，每块 {"type": "text", "text": "...", "cache_control": ...}
            user_content: 用户消息内容
            max_tokens: 最大输出 token 数
            node_name: 调用节点名称，用于 trace 日志

        Returns:
            模型响应文本
        """
        from agent.logger import log_trace

        if self.provider == "openai":
            messages: list[dict] = []
            for block in system_prompts:
                messages.append({"role": "system", "content": block["text"]})
            messages.append({"role": "user", "content": user_content})

            response = self._client.chat.completions.create(
                model=self.model_id,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            text = response.choices[0].message.content or ""
        else:
            response = self._client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system_prompts,
                messages=[{"role": "user", "content": user_content}],
            )
            text = response.content[0].text

        log_trace({
            "node": node_name,
            "provider": self.provider,
            "model": self.model_id,
            "system_prompts": json.dumps(
                [{"type": b.get("type"), "text": b["text"]} for b in system_prompts],
                ensure_ascii=False,
            ),
            "user_content": user_content,
            "response": text,
            "max_tokens": max_tokens,
        })
        return text


def _auto_detect_provider(base_url: str | None) -> str:
    """根据 base_url 自动检测提供者类型"""
    if base_url and "api.anthropic.com" not in base_url:
        return "openai"
    return "anthropic"


def get_llm_client() -> LLMClient:
    """创建统一的 LLM 客户端，自动检测提供者类型。

    检测规则：
    1. LLM_PROVIDER 环境变量显式指定（"openai" 或 "anthropic"）
    2. 否则根据 ANTHROPIC_BASE_URL 自动检测（非 api.anthropic.com 则用 openai）
    3. 默认使用 anthropic
    """
    cfg = get_llm_config()
    provider = os.getenv("LLM_PROVIDER", "")
    if not provider:
        provider = _auto_detect_provider(cfg.get("base_url"))
    return LLMClient(
        provider=provider,
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model_id=cfg["model_id"],
    )
