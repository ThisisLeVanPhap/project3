import os
import time
from dataclasses import dataclass
from typing import List, Optional, Protocol

from .claude_provider import call_claude_api
from .runtime_config import TRUE_VALUES


@dataclass
class LLMResult:
    text: str = ""
    called: bool = False
    skip_reason: str = ""
    error_type: str = ""
    latency_ms: int = 0


class LLMClient(Protocol):
    def complete(
        self,
        *,
        prompt: str,
        mode: str,
        purpose: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        ...


def _real_claude_disabled_in_pytest() -> bool:
    if os.getenv("RUN_REAL_CLAUDE_TESTS", "0").strip().lower() in TRUE_VALUES:
        return False
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


class ClaudeLLMClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        api_model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else (
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY") or ""
        )
        self.api_model = api_model or os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6"
        self.api_base_url = api_base_url or os.getenv("CLAUDE_API_BASE_URL") or "https://api.anthropic.com"
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        *,
        prompt: str,
        mode: str,
        purpose: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        if _real_claude_disabled_in_pytest():
            raise RuntimeError("pytest_real_claude_disabled")
        if not self.api_key:
            return LLMResult(called=False, skip_reason="missing_api_key")

        started = time.time()
        text, error_type, _preview = call_claude_api(
            prompt,
            self.api_key,
            self.api_model,
            self.api_base_url,
            max_tokens,
            temperature,
            1.0,
            self.timeout_seconds,
        )
        latency_ms = int((time.time() - started) * 1000)
        if error_type:
            return LLMResult(
                text="",
                called=True,
                error_type=error_type,
                skip_reason="claude_error",
                latency_ms=latency_ms,
            )
        return LLMResult(text=text or "", called=True, latency_ms=latency_ms)


class FakeLLMClient:
    def __init__(self, responses: Optional[List[str]] = None) -> None:
        self.responses = list(responses or [])
        self.calls: List[dict] = []

    def complete(
        self,
        *,
        prompt: str,
        mode: str,
        purpose: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        self.calls.append({
            "prompt": prompt,
            "mode": mode,
            "purpose": purpose,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        if not self.responses:
            return LLMResult(text="", called=True, skip_reason="fake_empty")
        return LLMResult(text=self.responses.pop(0), called=True)
