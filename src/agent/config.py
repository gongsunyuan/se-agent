# src/agent/config.py
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()


def get_llm_config() -> dict:
    """返回 LLM 配置字典，供节点使用"""
    return {
        "api_key": os.environ["ANTHROPIC_API_KEY"],
        "base_url": os.getenv("ANTHROPIC_BASE_URL"),   # None 则用官方端点
        "model_id": os.getenv("MODEL_ID", "claude-sonnet-4-6"),
    }


def get_client() -> anthropic.Anthropic:
    cfg = get_llm_config()
    kwargs = {"api_key": cfg["api_key"]}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return anthropic.Anthropic(**kwargs)


# 供节点直接 import 使用的模型 ID
MODEL_ID: str = os.getenv("MODEL_ID", "claude-sonnet-4-6")
