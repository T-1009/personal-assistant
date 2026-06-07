"""LLM Provider 配置加载模块。

读取项目根目录的 config.yaml + 环境变量，
暴露统一的 get_model(provider: str = None) -> BaseChatModel 接口。

当 config.yaml 不存在时，fallback 到旧版环境变量：
  MODEL_URL / MODEL_API_KEY / MODEL_NAME
"""

import os
from pathlib import Path
from typing import Any

import yaml
from langchain.chat_models import BaseChatModel, init_chat_model

# 项目根目录 = app/llm_config.py 的上两级目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"

# 缓存加载的配置，避免重复 I/O
_config: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    """加载 config.yaml。若文件不存在则返回空 dict（触发 fallback）。"""
    global _config
    if _config is None:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                _config = yaml.safe_load(f)
        else:
            _config = {}  # 空配置 → 触发 fallback 逻辑
    return _config


def get_model(provider: str | None = None) -> BaseChatModel:
    """获取 LLM model 实例。

    Args:
        provider: provider 名称（对应 config.yaml 中 llm.providers 下的 key）。
                  为 None 时使用 llm.default 指定的默认 provider。
                  当 config.yaml 不存在或未配置对应 provider 时，
                  自动 fallback 到 MODEL_URL / MODEL_API_KEY / MODEL_NAME 环境变量。

    Returns:
        LangChain BaseChatModel 实例（OpenAI-compatible）。

    Raises:
        ValueError: 当必填的 api_key 环境变量未设置时。
    """
    cfg = _load_config()
    llm_cfg = cfg.get("llm", {})

    if llm_cfg and "providers" in llm_cfg:
        # ── 正常路径：config.yaml 已配置 ──
        provider = provider or llm_cfg.get("default", "maas")
        p = llm_cfg["providers"].get(provider)
        if not p:
            raise ValueError(
                f"LLM provider '{provider}' 未在 config.yaml 中配置。"
                f" 可用 providers: {list(llm_cfg['providers'].keys())}"
            )
        api_key = os.environ.get(p["api_key_env"])
        if not api_key:
            raise ValueError(
                f"环境变量 {p['api_key_env']} 未设置，provider={provider} 不可用。"
                f" 请设置 {p['api_key_env']} 环境变量后重试。"
            )
        return init_chat_model(
            model=f"openai:{p['model']}",
            base_url=p["base_url"],
            api_key=api_key,
        )
    else:
        # ── Fallback 路径：config.yaml 不存在或未配置 llm section ──
        model_url = os.environ.get(
            "MODEL_URL", "https://api.modelarts-maas.com/openai/v1"
        )
        model_api_key = os.environ.get("MODEL_API_KEY")
        model_name = os.environ.get("MODEL_NAME", "deepseek-v4-pro")

        if not model_api_key:
            raise ValueError(
                "config.yaml 未配置且 MODEL_API_KEY 环境变量未设置。"
                " 请创建 config.yaml 或设置 MODEL_API_KEY 环境变量。"
            )
        return init_chat_model(
            model=f"openai:{model_name}",
            base_url=model_url,
            api_key=model_api_key,
        )
