import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from app.answer_evaluator import extract_context_facts
from app.prompt import build_messages
from app.product_answer_renderer import render_product_answer
from app.retrieval_service import format_context, load_kb, search_hits
from app.retrievers.text import repair_mojibake
from app.sales_flow import build_sales_prefix


HttpPost = Callable[[str, Mapping[str, Any], float], Mapping[str, Any]]


def load_json_list(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return data


def _clean(value: Any) -> str:
    return repair_mojibake(str(value or "")).strip()


def _source_url_from_hit(hit: Any) -> str:
    metadata = hit.metadata if hasattr(hit, "metadata") else (hit.get("metadata") or {})
    if not isinstance(metadata, dict):
        metadata = {}
    return _clean(
        metadata.get("source_url")
        or metadata.get("canonical_url")
        or metadata.get("url")
        or getattr(hit, "source", "")
        or (hit.get("source") if isinstance(hit, dict) else "")
    )


def summarize_hit(hit: Any) -> Dict[str, Any]:
    metadata = hit.metadata if hasattr(hit, "metadata") else (hit.get("metadata") or {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "title": _clean(getattr(hit, "title", "") or (hit.get("title") if isinstance(hit, dict) else "")),
        "score": float(getattr(hit, "score", 0.0) or (hit.get("score", 0.0) if isinstance(hit, dict) else 0.0) or 0.0),
        "category": _clean(metadata.get("category")),
        "price": metadata.get("price"),
        "url": _source_url_from_hit(hit),
    }


def _query_asks_non_product_or_missing_field(query_spec: Mapping[str, Any]) -> bool:
    query_type = str(query_spec.get("type") or "")
    query = _clean(query_spec.get("query")).lower()
    if query_type in {"missing_field", "out_of_scope_or_policy", "out_of_scope"}:
        return True
    return any(
        term in query
        for term in (
            "bao hanh",
            "bảo hành",
            "van chuyen",
            "vận chuyển",
            "giao hang",
            "giao hàng",
            "lap dat",
            "lắp đặt",
            "dia chi",
            "địa chỉ",
            "showroom",
            "con hang",
            "còn hàng",
            "doi tra",
            "đổi trả",
        )
    )


def generate_fake_answer(query_spec: Mapping[str, Any], context: str) -> str:
    facts = extract_context_facts(context)
    products = list(facts["products"].values())
    behavior = query_spec.get("expected_behavior") or {}
    max_products = int(behavior.get("max_products_to_answer") or 3)

    if _query_asks_non_product_or_missing_field(query_spec):
        return (
            "Mình chưa thấy thông tin này trong dữ liệu hiện có. "
            "Bạn nên hỏi cửa hàng để xác nhận trước khi quyết định."
        )

    if not products:
        return (
            "Mình chưa thấy sản phẩm phù hợp trong dữ liệu hiện có. "
            "Bạn có thể cho mình thêm nhu cầu hoặc khoảng giá để kiểm tra lại."
        )

    selected = products[: max(1, min(max_products, 3))]
    lines = []
    for product in selected:
        pid = product.get("pid")
        name = _clean(product.get("product_name")) or "Sản phẩm trong context"
        price = _clean(product.get("price"))
        url = _clean(product.get("source_url"))
        bits = [f"- {name} [{pid}]"]
        if price:
            bits.append(f"giá {price}")
        if url:
            bits.append(f"nguồn: {url}")
            lines.append(", ".join(bits))
        else:
            lines.append(", ".join(bits) + ".")

    if str(query_spec.get("type") or "") == "comparison":
        intro = "Có thể so sánh nhanh các lựa chọn trong context như sau:"
    elif str(query_spec.get("type") or "") == "matching":
        intro = "Mình thấy các lựa chọn có thể phối cùng nhau trong context:"
    else:
        intro = "Mình tìm thấy một số sản phẩm phù hợp trong context:"
    return "\n".join([intro, *lines])


def build_prompt_payload(query: str, context: str) -> Dict[str, str]:
    return {
        "system": build_sales_prefix("propose", {}),
        "grounding_context": context,
        "user": query,
    }


def detect_live_config(
    env: Optional[Mapping[str, str]] = None,
    endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    has_anthropic = bool(env.get("ANTHROPIC_API_KEY"))
    has_claude_key = bool(env.get("CLAUDE_API_KEY"))
    local_enabled = str(env.get("LOCAL_MODEL_ENABLED") or "").strip().lower() == "true"
    has_base_model = bool(env.get("BASE_MODEL"))
    providers = []
    missing = []

    if has_anthropic or has_claude_key:
        providers.append("claude")
    else:
        missing.append("ANTHROPIC_API_KEY or CLAUDE_API_KEY")

    if local_enabled and has_base_model:
        providers.append("local")
    elif local_enabled and not has_base_model:
        missing.append("BASE_MODEL")

    strategies = []
    if "claude" in providers:
        strategies.append("internal_claude")
    if endpoint:
        strategies.append("endpoint")

    suggested_command = (
        "python chatbot/tools/run_answer_grounding_live.py "
        "--kb-dir chatbot/kb/demo-tenant-products-full "
        "--queries chatbot/benchmarks/answer_grounding_queries.json "
        "--mode live "
        "--output chatbot/benchmarks/answer_grounding_live_outputs.json "
        "--continue-on-error"
    )
    if endpoint:
        suggested_command += f" --endpoint {endpoint}"

    return {
        "provider_detected": providers or ["none"],
        "required_env_present": {
            "ANTHROPIC_API_KEY": has_anthropic,
            "CLAUDE_API_KEY": has_claude_key,
            "LOCAL_MODEL_ENABLED": local_enabled,
            "BASE_MODEL": has_base_model,
        },
        "missing_env": missing,
        "live_strategy_available": strategies or ["none"],
        "suggested_command": suggested_command,
    }


def _missing_env_message(config: Mapping[str, Any]) -> str:
    missing = ", ".join(config.get("missing_env") or ["provider configuration"])
    return f"Live mode is not configured. Missing env: {missing}"


def _post_json(url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Endpoint returned HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Endpoint request failed: {exc.reason}") from exc


def generate_endpoint_answer(
    query_spec: Mapping[str, Any],
    *,
    endpoint: str,
    tenant_id: Optional[str],
    timeout_seconds: float,
    k: int,
    chat_mode: str,
    answer_mode: Optional[str] = None,
    http_post: HttpPost = _post_json,
) -> Dict[str, Any]:
    query = _clean(query_spec.get("query"))
    payload = {
        "message": query,
        "history": [],
        "conversation_id": f"answer-grounding-{query_spec.get('id') or 'query'}",
        "channel": "web",
        "tenant_id": tenant_id,
        "gen": {
            "mode": chat_mode,
            "retrieval_mode": "keyword",
            "retrieval_top_k": k,
        },
    }
    if answer_mode:
        payload["gen"]["answer_mode"] = answer_mode
    response = dict(http_post(endpoint, payload, timeout_seconds))
    answer = _clean(response.get("reply"))
    if not answer:
        raise RuntimeError("Endpoint response did not contain a non-empty 'reply'")
    return {
        "answer": answer,
        "provider": _clean(response.get("model")) or "endpoint",
        "strategy": "endpoint",
        "provider_latency_ms": response.get("latency_ms"),
        "provider_response": {
            "model": response.get("model"),
            "adapter": response.get("adapter"),
            "debug": response.get("debug"),
        },
    }


def generate_internal_claude_answer(
    query_spec: Mapping[str, Any],
    context: str,
    *,
    timeout_seconds: float,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    api_key = env.get("ANTHROPIC_API_KEY") or env.get("CLAUDE_API_KEY")
    if not api_key:
        raise RuntimeError(_missing_env_message(detect_live_config(env)))

    from app import server
    from app.modes import ChatMode

    query = _clean(query_spec.get("query"))
    sales_prefix = build_sales_prefix("propose", {})
    sys_prompt = server._build_system_prompt(ChatMode.TENANT_SALES.value, sales_prefix, None)
    sys_prompt += (
        "\n\nLANGUAGE PREFERENCE:\n"
        "- Reply in Vietnamese by default for this tenant sales chat.\n"
        "- If the user writes a short greeting like 'hi' or 'hello', answer in Vietnamese and ask what furniture item they need.\n"
        "- Only switch to English if the user explicitly asks to use English."
    )
    messages = build_messages(query, [], sys_prompt, grounding_context=context if context else None)
    prompt_text = server._messages_to_plain_prompt(messages)
    api_model = env.get("CLAUDE_MODEL") or "claude-sonnet-4-6"
    api_base_url = env.get("CLAUDE_API_BASE_URL") or "https://api.anthropic.com"
    max_tokens = int(env.get("CLAUDE_MAX_NEW_TOKENS") or "768")
    answer, error_code, error_preview = server._call_claude_api(
        prompt_text,
        api_key,
        api_model,
        api_base_url,
        max_tokens,
        0.2,
        None,
        timeout_seconds=timeout_seconds,
    )
    if error_code:
        raise RuntimeError(f"Claude generation failed: {error_code}: {_clean(error_preview)[:300]}")
    answer = server._apply_grounding_guard(query, context, answer.strip())
    return {
        "answer": answer,
        "provider": api_model,
        "strategy": "internal_claude",
        "provider_latency_ms": None,
    }


def generate_live_answer(
    query_spec: Mapping[str, Any],
    context: str,
    *,
    endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    timeout_seconds: float = 60.0,
    k: int = 5,
    strategy: str = "auto",
    chat_mode: str = "tenant_sales",
    answer_mode: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    http_post: HttpPost = _post_json,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    config = detect_live_config(env, endpoint=endpoint)
    strategies = set(config["live_strategy_available"])

    if strategy not in {"auto", "internal", "endpoint"}:
        raise ValueError(f"Unsupported live strategy: {strategy}")
    if strategy in {"auto", "endpoint"} and endpoint:
        return generate_endpoint_answer(
            query_spec,
            endpoint=endpoint,
            tenant_id=tenant_id,
            timeout_seconds=timeout_seconds,
            k=k,
            chat_mode=chat_mode,
            answer_mode=answer_mode,
            http_post=http_post,
        )
    if strategy in {"auto", "internal"} and "internal_claude" in strategies:
        return generate_internal_claude_answer(
            query_spec,
            context,
            timeout_seconds=timeout_seconds,
            env=env,
        )
    raise RuntimeError(_missing_env_message(config))


def _error_row(
    query_spec: Mapping[str, Any],
    query: str,
    context: str,
    hits: Sequence[Any],
    kb_dir: str,
    k: int,
    mode: str,
    error: Exception,
    started_at: float,
    provider: str = "none",
    strategy: str = "none",
) -> Dict[str, Any]:
    return {
        "id": query_spec.get("id"),
        "query": query,
        "type": query_spec.get("type"),
        "context": context,
        "prompt": build_prompt_payload(query, context),
        "answer": "",
        "retrieval_hits": [summarize_hit(hit) for hit in hits],
        "error": _clean(error),
        "metadata": {
            "mode": mode,
            "provider": provider,
            "strategy": strategy,
            "kb_dir": kb_dir,
            "k": k,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "latency_ms": int((time.time() - started_at) * 1000),
            "prompt_has_grounding_contract": "GROUNDED PRODUCT ANSWER CONTRACT" in build_sales_prefix("propose", {}),
        },
    }


def capture_query(
    kb: Any,
    query_spec: Mapping[str, Any],
    kb_dir: str,
    mode: str = "fake",
    k: int = 5,
    *,
    endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    timeout_seconds: float = 60.0,
    strategy: str = "auto",
    chat_mode: str = "tenant_sales",
    answer_mode: Optional[str] = None,
    http_post: HttpPost = _post_json,
) -> Dict[str, Any]:
    started_at = time.time()
    query = _clean(query_spec.get("query"))
    hits = search_hits(kb, query, k=k)
    context = format_context(hits)
    prompt = build_prompt_payload(query, context)
    provider = "fake"
    live_strategy = "fake"
    provider_latency_ms = None
    provider_response = None

    if mode == "fake":
        answer = generate_fake_answer(query_spec, context)
    elif mode == "template":
        answer = render_product_answer(query, context)
        provider = "template"
        live_strategy = "template"
    elif mode == "live":
        live_result = generate_live_answer(
            query_spec,
            context,
            endpoint=endpoint,
            tenant_id=tenant_id,
            timeout_seconds=timeout_seconds,
            k=k,
            strategy=strategy,
            chat_mode=chat_mode,
            answer_mode=answer_mode,
            http_post=http_post,
        )
        answer = live_result["answer"]
        provider = live_result.get("provider") or "live"
        live_strategy = live_result.get("strategy") or strategy
        provider_latency_ms = live_result.get("provider_latency_ms")
        provider_response = live_result.get("provider_response")
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    metadata = {
        "mode": mode,
        "provider": provider,
        "strategy": live_strategy,
        "kb_dir": kb_dir,
        "k": k,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": int((time.time() - started_at) * 1000),
        "provider_latency_ms": provider_latency_ms,
        "prompt_has_grounding_contract": "GROUNDED PRODUCT ANSWER CONTRACT" in prompt["system"],
    }
    if provider_response is not None:
        metadata["provider_response"] = provider_response

    return {
        "id": query_spec.get("id"),
        "query": query,
        "type": query_spec.get("type"),
        "context": context,
        "prompt": prompt,
        "answer": answer,
        "retrieval_hits": [summarize_hit(hit) for hit in hits],
        "metadata": metadata,
    }


def run_capture(
    kb_dir: str,
    queries_path: str,
    mode: str = "fake",
    k: int = 5,
    *,
    endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    timeout_seconds: float = 60.0,
    strategy: str = "auto",
    chat_mode: str = "tenant_sales",
    answer_mode: Optional[str] = None,
    continue_on_error: bool = False,
    http_post: HttpPost = _post_json,
) -> List[Dict[str, Any]]:
    query_specs = load_json_list(queries_path)
    kb = load_kb(kb_dir)
    if kb is None:
        raise ValueError(f"Could not load KB from: {kb_dir}")

    rows = []
    for query_spec in query_specs:
        started_at = time.time()
        query = _clean(query_spec.get("query"))
        hits: List[Any] = []
        context = ""
        try:
            hits = search_hits(kb, query, k=k)
            context = format_context(hits)
            rows.append(
                capture_query(
                    kb,
                    query_spec,
                    kb_dir=kb_dir,
                    mode=mode,
                    k=k,
                    endpoint=endpoint,
                    tenant_id=tenant_id,
                    timeout_seconds=timeout_seconds,
                    strategy=strategy,
                    chat_mode=chat_mode,
                    answer_mode=answer_mode,
                    http_post=http_post,
                )
            )
        except Exception as exc:
            if not continue_on_error:
                raise
            rows.append(_error_row(query_spec, query, context, hits, kb_dir, k, mode, exc, started_at))
    return rows


def write_outputs(rows: List[Dict[str, Any]], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_outputs(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    with_answer = sum(1 for row in rows if str(row.get("answer") or "").strip())
    with_context = sum(1 for row in rows if str(row.get("context") or "").strip())
    failed = sum(1 for row in rows if row.get("error"))
    avg_hits = sum(len(row.get("retrieval_hits") or []) for row in rows) / len(rows) if rows else 0.0
    avg_latency = sum((row.get("metadata") or {}).get("latency_ms") or 0 for row in rows) / len(rows) if rows else 0.0
    return {
        "total_outputs": len(rows),
        "answers_present": with_answer,
        "contexts_present": with_context,
        "failed_count": failed,
        "avg_retrieval_hits": round(avg_hits, 3),
        "avg_latency_ms": round(avg_latency, 3),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Capture end-to-end answer grounding outputs.")
    parser.add_argument("--kb-dir")
    parser.add_argument("--queries")
    parser.add_argument("--mode", choices=["fake", "live", "template", "check"], default="fake")
    parser.add_argument("--output")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--endpoint")
    parser.add_argument("--tenant-id")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--strategy", choices=["auto", "internal", "endpoint"], default="auto")
    parser.add_argument("--chat-mode", default="tenant_sales")
    parser.add_argument("--answer-mode")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)

    if args.mode == "check" or args.check_only:
        print(json.dumps(detect_live_config(endpoint=args.endpoint), ensure_ascii=False, indent=2))
        return 0

    if not args.kb_dir:
        parser.error("--kb-dir is required for capture mode")
    if not args.queries:
        parser.error("--queries is required for capture mode")
    if not args.output:
        parser.error("--output is required for capture mode")

    try:
        rows = run_capture(
            args.kb_dir,
            args.queries,
            mode=args.mode,
            k=args.k,
            endpoint=args.endpoint,
            tenant_id=args.tenant_id,
            timeout_seconds=args.timeout_seconds,
            strategy=args.strategy,
            chat_mode=args.chat_mode,
            answer_mode=args.answer_mode,
            continue_on_error=args.continue_on_error,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    write_outputs(rows, args.output)
    print(json.dumps(summarize_outputs(rows), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
