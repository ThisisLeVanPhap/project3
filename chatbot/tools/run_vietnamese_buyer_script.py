import argparse
import csv
import json
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request


CONVERSATION_ID = "00b57d38-d74c-414a-b37d-2b6112cce4d6"
API_KEY = "029269d7f5f445f7ac36c196dffa134e"
DEFAULT_WARMUP_MESSAGE = "Xin chào, tôi đang thử khởi động hệ thống chat."
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "vietnamese_buyer_script.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay the Vietnamese sofa buyer script against the Spring Boot chat API."
    )
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL of the Spring Boot API.")
    parser.add_argument("--path", default="/api/chat/send", help="Chat endpoint path. Default: /api/chat/send")
    parser.add_argument("--api-key", default=API_KEY, help="X-API-Key header value.")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Path to the structured buyer-script dataset JSON.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional CSV output path. Defaults to out/conversation_runs/vietnamese_buyer_<timestamp>.csv",
    )
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP timeout in seconds per request. Default: 180")
    parser.add_argument("--delay-between-turns", type=float, default=0.5, help="Optional sleep in seconds between turns. Default: 0.5")
    parser.add_argument("--warmup", action="store_true", help="Send a warmup request before the main scripted run.")
    parser.add_argument("--warmup-message", default=DEFAULT_WARMUP_MESSAGE, help="Warmup message to send before turn 1.")
    return parser.parse_args()


def configure_output_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("out") / "conversation_runs" / f"vietnamese_buyer_{timestamp}.csv"


def load_buyer_turns(dataset_path: Path) -> List[Dict[str, Any]]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    turns = payload.get("turns")
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"Dataset at {dataset_path} does not contain a non-empty 'turns' list.")

    normalized_turns: List[Dict[str, Any]] = []
    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            raise ValueError(f"Turn {index} in {dataset_path} is not an object.")

        stt = int(turn.get("stt", index))
        user_input = str(turn.get("user_input", "")).strip()
        if not user_input:
            raise ValueError(f"Turn {stt} in {dataset_path} is missing user_input.")

        normalized_turns.append(
            {
                "stt": stt,
                "user_input": user_input,
                "expected_behavior": str(
                    turn.get("expected_behavior", "General consultative reply in Vietnamese.")
                ).strip()
                or "General consultative reply in Vietnamese.",
                "stage_hint": str(turn.get("stage_hint", "")).strip(),
                "marker": str(turn.get("marker", "")).strip(),
            }
        )

    return normalized_turns


def build_payload(message: str) -> Dict[str, Any]:
    return {
        "conversationId": CONVERSATION_ID,
        "message": message,
    }


def normalize_text_for_check(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower().replace("đ", "d").replace("Đ", "d")


def merge_markers(*marker_values: str) -> str:
    merged: List[str] = []
    for marker_value in marker_values:
        for marker in str(marker_value or "").split("|"):
            marker = marker.strip()
            if marker and marker not in merged:
                merged.append(marker)
    return "|".join(merged)


def detect_markers(turn_number: int, user_message: str, reply: str) -> str:
    combined = normalize_text_for_check(f"{user_message} {reply}")
    markers: List[str] = []

    if turn_number in {25, 26} or any(token in combined for token in ["giam gia", "mac ca", "bot xuong", "re hon"]):
        markers.append("bargain")
    if turn_number == 28 or "thanh toan" in combined or "payment" in combined:
        markers.append("payment")
    if any(token in combined for token in ["giao hang", "delivery", "ship", "dia chi", "nhan hang"]):
        markers.append("delivery")
    if "confirm" in combined or "yeu cau mua hang" in combined or "purchase request" in combined:
        markers.append("confirm_or_purchase_request")

    return "|".join(markers)


def run_lightweight_checks(turn_number: int, reply: str) -> str:
    reply_low = normalize_text_for_check(reply)
    issues: List[str] = []

    if turn_number in {25, 26}:
        if any(phrase in reply_low for phrase in ["dong y giam", "chot gia", "price adjusted", "giam xuong dung"]):
            issues.append("Bargain guard may have reduced the price directly.")

    if turn_number == 28:
        if any(phrase in reply_low for phrase in ["thanh toan ngay", "xu ly thanh toan", "process payment", "complete payment"]):
            issues.append("Payment guard may have claimed full payment in chat.")

    if turn_number in {29, 30, 31}:
        required_signals = [
            "nguyen van a", "0912345678", "123 nguyen trai", "ha noi",
            "name", "phone", "address", "ten", "so dien thoai", "dia chi", "confirm",
        ]
        if not any(signal in reply_low for signal in required_signals):
            issues.append("Purchase-request flow may be missing buyer details or confirmation.")

    return " ".join(issues)


def print_turn(
    turn_label: str,
    user_message: str,
    reply: str,
    local_seconds: float,
    server_latency_ms: Any,
    http_status: int,
    marker: str,
) -> None:
    print(f"[{turn_label}] User: {user_message}", flush=True)
    print(f"[{turn_label}] Bot: {reply}", flush=True)
    print(
        f"[{turn_label}] Status: {http_status} | Local: {local_seconds:.2f}s | Server latencyMs: {server_latency_ms if server_latency_ms is not None else 'n/a'} | Marker: {marker or '-'}",
        flush=True,
    )
    print("-" * 100, flush=True)


def call_chat(url: str, api_key: str, payload: Dict[str, Any], timeout: float) -> Tuple[int, Dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"reply": text}
            return resp.status, parsed
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"reply": text}
        return exc.code, parsed


def run_request(url: str, api_key: str, timeout: float, message: str) -> Tuple[int, Dict[str, Any], float]:
    payload = build_payload(message)
    started_at = time.perf_counter()
    status, body = call_chat(url, api_key, payload, timeout=timeout)
    elapsed = time.perf_counter() - started_at
    return status, body, elapsed


def maybe_warmup(chat_url: str, args: argparse.Namespace) -> None:
    if not args.warmup:
        return

    print("Warmup: sending one pre-run request...", flush=True)
    try:
        status, body, elapsed = run_request(chat_url, args.api_key, args.timeout, args.warmup_message)
        reply = str(body.get("reply", "")) if 200 <= status < 300 else str(body)
        marker = detect_markers(0, args.warmup_message, reply)
        print_turn("Warmup", args.warmup_message, reply, elapsed, body.get("latencyMs"), status, marker)
    except Exception as exc:
        print(f"[Warmup] Failed: {exc}", flush=True)
        print("-" * 100, flush=True)


def main() -> int:
    configure_output_streams()
    args = parse_args()
    dataset_path = Path(args.dataset)
    buyer_turns = load_buyer_turns(dataset_path)
    chat_url = args.base_url.rstrip("/") + args.path
    output_path = Path(args.output) if args.output else default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    print(f"Chat URL: {chat_url}", flush=True)
    print(f"Conversation ID: {CONVERSATION_ID}", flush=True)
    print(f"Dataset: {dataset_path}", flush=True)
    print(f"CSV output: {output_path}", flush=True)
    print(f"Timeout per request: {args.timeout:.1f}s", flush=True)
    print(f"Delay between turns: {args.delay_between_turns:.1f}s", flush=True)
    print(f"Warmup enabled: {'yes' if args.warmup else 'no'}", flush=True)
    print("=" * 100, flush=True)

    maybe_warmup(chat_url, args)

    for turn in buyer_turns:
        turn_number = int(turn["stt"])
        user_message = str(turn["user_input"])
        expected_behavior = str(turn["expected_behavior"])
        stage_hint = str(turn["stage_hint"])
        marker_hint = str(turn["marker"])
        reply = ""
        http_status = 0
        notes = ""
        local_seconds = 0.0
        server_latency_ms = None

        try:
            http_status, body, local_seconds = run_request(chat_url, args.api_key, args.timeout, user_message)
            server_latency_ms = body.get("latencyMs")
            if 200 <= http_status < 300:
                reply = str(body.get("reply", ""))
            else:
                reply = str(body)
                notes = f"HTTP error response: {body}"
        except Exception as exc:
            reply = f"[ERROR] {exc}"
            notes = f"Request failed: {exc}"

        marker = merge_markers(marker_hint, detect_markers(turn_number, user_message, reply))
        check_notes = run_lightweight_checks(turn_number, reply)
        if check_notes:
            notes = f"{notes} {check_notes}".strip()

        print_turn(f"Turn {turn_number:02d}", user_message, reply, local_seconds, server_latency_ms, http_status, marker)

        rows.append({
            "stt": turn_number,
            "stage_hint": stage_hint,
            "marker": marker,
            "user_input": user_message,
            "chatbot_reply": reply,
            "local_response_time_seconds": f"{local_seconds:.3f}",
            "server_latency_ms": server_latency_ms if server_latency_ms is not None else "",
            "http_status": http_status,
            "expected_behavior": expected_behavior,
            "notes": notes,
        })

        if args.delay_between_turns > 0 and turn_number < len(buyer_turns):
            time.sleep(args.delay_between_turns)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "stt",
                "stage_hint",
                "marker",
                "user_input",
                "chatbot_reply",
                "local_response_time_seconds",
                "server_latency_ms",
                "http_status",
                "expected_behavior",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved CSV: {output_path}", flush=True)
    print(f"Turns logged: {len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
