from typing import Optional, Tuple


def call_claude_api(
    prompt: str,
    api_key: str,
    api_model: str,
    api_base_url: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout_seconds: float = 120.0,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Call Anthropic Claude API and return (text, error_code, error_preview)."""
    if not api_key:
        return "", "missing_api_key", "Claude API key was not provided"

    import requests

    cleaned_prompt = prompt.rstrip()
    if "Response:" in cleaned_prompt:
        cleaned_prompt = cleaned_prompt.split("Response:")[0].rstrip()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    data = {
        "model": api_model,
        "messages": [{"role": "user", "content": cleaned_prompt}],
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        data["temperature"] = temperature
    if top_p is not None and temperature is None:
        data["top_p"] = top_p

    try:
        resp = requests.post(
            f"{api_base_url.rstrip('/')}/v1/messages",
            headers=headers,
            json=data,
            timeout=timeout_seconds,
        )
        if resp.status_code != 200:
            body_preview = resp.text[:500].replace("\n", "\\n")
            return "", "non_200", f"status={resp.status_code} body={body_preview}"

        result = resp.json()
        content = result.get("content")
        if not isinstance(content, list) or not content:
            return "", "parse_fail", (
                f"top_keys={list(result.keys())[:20]} content_type={type(content).__name__}"
            )

        first_block = content[0]
        if not isinstance(first_block, dict):
            preview = str(first_block)[:500]
            return "", "parse_fail", f"first_block_type={type(first_block).__name__} first_block={preview}"

        text = first_block.get("text")
        if first_block.get("type") != "text" or text is None:
            preview = str(first_block)[:500]
            return "", "parse_fail", f"first_block={preview}"
        if not text.strip():
            return "", "empty_text", "Claude returned an empty text block"
        return text, None, None
    except Exception as exc:
        message = str(exc).replace("\n", "\\n")[:300]
        return "", "exception", f"class={exc.__class__.__name__} message={message}"
