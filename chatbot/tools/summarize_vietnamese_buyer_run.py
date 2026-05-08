import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_RUN_DIR = Path("out") / "conversation_runs"
MARKER_ORDER = [
    "bargain",
    "payment",
    "delivery",
    "confirm_or_purchase_request",
]
TIMEOUT_TOKENS = [
    "timed out",
    "timeout",
    "time out",
    "read timed out",
    "taking longer than expected",
    "quá thời gian",
    "het thoi gian",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a Vietnamese buyer-script CSV run into a short report-friendly summary."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="",
        help="CSV file to summarize. Defaults to the newest file in out/conversation_runs.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "text"],
        default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--group-by-marker",
        action="store_true",
        help="Include per-marker stats when marker data is present.",
    )
    parser.add_argument(
        "--group-by-stage",
        action="store_true",
        help="Include per-stage stats when stage data is present.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional JSON output path for report/demo reuse.",
    )
    return parser.parse_args()


TIMEOUT_FALLBACK_REPLIES = [
    "sorry, the chatbot is taking longer than expected. please try again in a moment.",
]


def resolve_csv_path(csv_path_arg: str) -> Path:
    if csv_path_arg:
        return Path(csv_path_arg)

    candidates = sorted(DEFAULT_RUN_DIR.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No CSV files found in {DEFAULT_RUN_DIR}")
    return candidates[0]


def load_rows(csv_path: Path) -> List[Dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def configure_output_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def parse_float(value: str) -> Optional[float]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def latency_for_row(row: Dict[str, str]) -> Optional[float]:
    return parse_float(row.get("local_response_time_seconds", "")) or parse_float(row.get("response_time_seconds", ""))


def parse_status(row: Dict[str, str]) -> Optional[int]:
    raw = (row.get("http_status", "") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def row_text(row: Dict[str, str], *fields: str) -> str:
    return " ".join((row.get(field, "") or "") for field in fields).lower()


def is_timeout_fallback_row(row: Dict[str, str]) -> bool:
    status = parse_status(row)
    if status in {408, 504}:
        return True

    reply_text = row_text(row, "chatbot_reply")
    if any(token in reply_text for token in TIMEOUT_FALLBACK_REPLIES):
        return True

    combined_text = row_text(row, "chatbot_reply", "notes")
    return any(token in combined_text for token in TIMEOUT_TOKENS)


def is_transport_success_row(row: Dict[str, str]) -> bool:
    status = parse_status(row)
    return status is not None and 200 <= status < 300


def is_real_answer_row(row: Dict[str, str]) -> bool:
    if not is_transport_success_row(row):
        return False
    if is_timeout_fallback_row(row):
        return False
    return bool((row.get("chatbot_reply", "") or "").strip())


def compute_stats(rows: Iterable[Dict[str, str]]) -> Dict[str, Optional[float]]:
    rows = list(rows)
    latencies = [value for value in (latency_for_row(row) for row in rows) if value is not None]
    transport_success_count = sum(1 for row in rows if is_transport_success_row(row))
    real_answer_count = sum(1 for row in rows if is_real_answer_row(row))
    timeout_fallback_count = sum(1 for row in rows if is_timeout_fallback_row(row))

    return {
        "total_turns": len(rows),
        "success_count": transport_success_count,
        "transport_success_count": transport_success_count,
        "real_answer_count": real_answer_count,
        "timeout_count": timeout_fallback_count,
        "timeout_fallback_count": timeout_fallback_count,
        "average_latency": statistics.mean(latencies) if latencies else None,
        "median_latency": statistics.median(latencies) if latencies else None,
        "max_latency": max(latencies) if latencies else None,
    }


def marker_groups(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        raw_marker = (row.get("marker", "") or "").strip()
        if not raw_marker:
            continue
        for marker in [part.strip() for part in raw_marker.split("|") if part.strip()]:
            groups.setdefault(marker, []).append(row)
    return groups


def stage_groups(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        stage = (row.get("stage", "") or "").strip()
        if not stage:
            continue
        groups.setdefault(stage, []).append(row)
    return groups


def format_latency(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}s"


def render_marker_section(groups: Dict[str, List[Dict[str, str]]], output_format: str) -> str:
    ordered_markers = [marker for marker in MARKER_ORDER if marker in groups] + [
        marker for marker in groups.keys() if marker not in MARKER_ORDER
    ]
    if not ordered_markers:
        return ""

    if output_format == "text":
        lines = ["By marker:"]
        for marker in ordered_markers:
            stats = compute_stats(groups[marker])
            lines.append(
                f"- {marker}: turns={stats['total_turns']}, transport_success={stats['transport_success_count']}, real_answers={stats['real_answer_count']}, timeout_fallbacks={stats['timeout_fallback_count']}, avg={format_latency(stats['average_latency'])}, median={format_latency(stats['median_latency'])}, max={format_latency(stats['max_latency'])}"
            )
        return "\n".join(lines)

    lines = [
        "## By Marker",
        "",
        "| Marker | Turns | Transport Success | Real Answers | Timeout Fallbacks | Avg Latency | Median Latency | Max Latency |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for marker in ordered_markers:
        stats = compute_stats(groups[marker])
        lines.append(
            f"| {marker} | {stats['total_turns']} | {stats['transport_success_count']} | {stats['real_answer_count']} | {stats['timeout_fallback_count']} | {format_latency(stats['average_latency'])} | {format_latency(stats['median_latency'])} | {format_latency(stats['max_latency'])} |"
        )
    return "\n".join(lines)


def render_group_section(groups: Dict[str, List[Dict[str, str]]], output_format: str, heading: str, label: str) -> str:
    ordered_names = sorted(groups.keys())
    if not ordered_names:
        return ""

    if output_format == "text":
        lines = [f"By {label.lower()}:"]
        for name in ordered_names:
            stats = compute_stats(groups[name])
            lines.append(
                f"- {name}: turns={stats['total_turns']}, transport_success={stats['transport_success_count']}, real_answers={stats['real_answer_count']}, timeout_fallbacks={stats['timeout_fallback_count']}, avg={format_latency(stats['average_latency'])}, median={format_latency(stats['median_latency'])}, max={format_latency(stats['max_latency'])}"
            )
        return "\n".join(lines)

    lines = [
        f"## {heading}",
        "",
        f"| {label} | Turns | Transport Success | Real Answers | Timeout Fallbacks | Avg Latency | Median Latency | Max Latency |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ordered_names:
        stats = compute_stats(groups[name])
        lines.append(
            f"| {name} | {stats['total_turns']} | {stats['transport_success_count']} | {stats['real_answer_count']} | {stats['timeout_fallback_count']} | {format_latency(stats['average_latency'])} | {format_latency(stats['median_latency'])} | {format_latency(stats['max_latency'])} |"
        )
    return "\n".join(lines)


def render_summary(
    csv_path: Path,
    rows: List[Dict[str, str]],
    output_format: str,
    group_by_marker: bool,
    group_by_stage: bool,
) -> str:
    stats = compute_stats(rows)
    extra_sections: List[str] = []
    if group_by_marker:
        marker_section = render_marker_section(marker_groups(rows), output_format)
        if marker_section:
            extra_sections.append(marker_section)
    if group_by_stage:
        stage_section = render_group_section(stage_groups(rows), output_format, "By Stage", "Stage")
        if stage_section:
            extra_sections.append(stage_section)

    if output_format == "text":
        lines = [
            f"Buyer-script summary for {csv_path.name}",
            f"File: {csv_path}",
            f"Total turns: {stats['total_turns']}",
            f"Transport success count: {stats['transport_success_count']}",
            f"Real answer count: {stats['real_answer_count']}",
            f"Timeout fallback count: {stats['timeout_fallback_count']}",
            f"Legacy success count alias: {stats['success_count']}",
            f"Legacy timeout count alias: {stats['timeout_count']}",
            f"Average latency: {format_latency(stats['average_latency'])}",
            f"Median latency: {format_latency(stats['median_latency'])}",
            f"Max latency: {format_latency(stats['max_latency'])}",
        ]
        if extra_sections:
            for section in extra_sections:
                lines.extend(["", section])
        return "\n".join(lines)

    lines = [
        f"# Buyer Script Summary",
        "",
        f"- File: `{csv_path}`",
        f"- Total turns: {stats['total_turns']}",
        f"- Transport success count: {stats['transport_success_count']}",
        f"- Real answer count: {stats['real_answer_count']}",
        f"- Timeout fallback count: {stats['timeout_fallback_count']}",
        f"- Legacy success count alias: {stats['success_count']}",
        f"- Legacy timeout count alias: {stats['timeout_count']}",
        f"- Average latency: {format_latency(stats['average_latency'])}",
        f"- Median latency: {format_latency(stats['median_latency'])}",
        f"- Max latency: {format_latency(stats['max_latency'])}",
    ]
    for section in extra_sections:
        lines.extend(["", section])
    return "\n".join(lines)


def build_json_summary(csv_path: Path, rows: List[Dict[str, str]], group_by_marker: bool, group_by_stage: bool) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "file": str(csv_path),
        "stats": compute_stats(rows),
    }
    if group_by_marker:
        payload["markers"] = {name: compute_stats(group_rows) for name, group_rows in marker_groups(rows).items()}
    if group_by_stage:
        payload["stages"] = {name: compute_stats(group_rows) for name, group_rows in stage_groups(rows).items()}
    return payload


def main() -> int:
    configure_output_streams()
    args = parse_args()
    csv_path = resolve_csv_path(args.csv_path)
    rows = load_rows(csv_path)
    print(render_summary(csv_path, rows, args.format, args.group_by_marker, args.group_by_stage))
    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_payload = build_json_summary(csv_path, rows, args.group_by_marker, args.group_by_stage)
        json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
