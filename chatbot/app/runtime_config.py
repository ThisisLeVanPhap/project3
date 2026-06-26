import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}


def int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        print(f"[local_pipeline_cache] invalid_env={name} using_default={default}")
        return default
    if value < minimum:
        print(f"[local_pipeline_cache] invalid_env={name} minimum={minimum} using_default={default}")
        return default
    return value


@dataclass(frozen=True)
class RuntimeConfig:
    local_model_enabled: bool
    base_model_default: str | None
    tokenizer_default: str | None
    disabled_local_models: set[str]
    max_new_tokens_default: int
    claude_max_new_tokens: int
    local_fallback_max_tokens: int
    temperature_default: float
    top_p_default: float
    top_k_default: int
    retrieval_mode_default: str
    retrieval_top_k_default: int
    product_template_answers_default: bool
    fallback_to_local_enabled: bool
    local_fallback_timeout_seconds: int
    local_pipeline_max_cache: int
    local_pipeline_idle_ttl_seconds: int
    local_pipeline_cleanup_interval_seconds: int
    sales_state_ttl_seconds: int


def load_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        local_model_enabled=os.getenv("LOCAL_MODEL_ENABLED", "false").lower() in TRUE_VALUES,
        base_model_default=os.getenv("BASE_MODEL") or None,
        tokenizer_default=os.getenv("TOKENIZER_PATH") or None,
        disabled_local_models={"qwen/qwen2.5-1.5b-instruct"},
        max_new_tokens_default=int(os.getenv("MAX_NEW_TOKENS", "256")),
        claude_max_new_tokens=int(os.getenv("CLAUDE_MAX_NEW_TOKENS", "768")),
        local_fallback_max_tokens=int(os.getenv("LOCAL_FALLBACK_MAX_TOKENS", "128")),
        temperature_default=float(os.getenv("TEMPERATURE", "0.7")),
        top_p_default=float(os.getenv("TOP_P", "0.9")),
        top_k_default=int(os.getenv("TOP_K", "50")),
        retrieval_mode_default=os.getenv("RETRIEVAL_MODE", "keyword"),
        retrieval_top_k_default=int(os.getenv("RETRIEVAL_TOP_K", "4")),
        product_template_answers_default=os.getenv("PRODUCT_TEMPLATE_ANSWERS", "false").lower() in TRUE_VALUES,
        fallback_to_local_enabled=os.getenv("FALLBACK_TO_LOCAL_ENABLED", "false").lower() in TRUE_VALUES,
        local_fallback_timeout_seconds=int(os.getenv("LOCAL_FALLBACK_TIMEOUT_SECONDS", "45")),
        local_pipeline_max_cache=int_env("LOCAL_PIPELINE_MAX_CACHE", 2, minimum=1),
        local_pipeline_idle_ttl_seconds=int_env("LOCAL_PIPELINE_IDLE_TTL_SECONDS", 180, minimum=1),
        local_pipeline_cleanup_interval_seconds=int_env("LOCAL_PIPELINE_CLEANUP_INTERVAL_SECONDS", 30, minimum=1),
        sales_state_ttl_seconds=int(os.getenv("SALES_STATE_TTL_SECONDS", "1800")),
    )
