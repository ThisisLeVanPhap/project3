import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path

def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows

def pct(a, b):
    return 0.0 if b == 0 else (100.0 * a / b)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logdir", default="logs", help="Directory containing chat.jsonl and feedback.jsonl")
    ap.add_argument("--topk", type=int, default=10)
    args = ap.parse_args()

    logdir = Path(args.logdir)
    chat_path = logdir / "chat.jsonl"
    fb_path = logdir / "feedback.jsonl"

    chat = read_jsonl(chat_path)
    fb = read_jsonl(fb_path)

    # ---- Chat metrics ----
    events = Counter([r.get("event", "unknown") for r in chat])
    channels = Counter([r.get("channel", "unknown") for r in chat if r.get("event") in ("chat", "rule_hit", "similar_suggestion", "similar_list")])

    latencies = [r.get("latency_ms") for r in chat if r.get("event") == "chat" and isinstance(r.get("latency_ms"), (int, float))]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # count fallback-ish answers by heuristic
    fallback_markers = [
        "sorry, i couldn’t find enough information",
        "sorry, i couldn't find enough information",
        "connect you with a staff member",
        "i don't have real-time inventory",
        "unable to adjust prices directly",
    ]
    fallback_count = 0
    for r in chat:
        if r.get("event") == "chat":
            ans = (r.get("answer") or "").lower()
            if any(m in ans for m in fallback_markers):
                fallback_count += 1

    # ---- Feedback metrics ----
    fb_total = len(fb)
    fb_correct = sum(1 for r in fb if r.get("is_correct") is True)
    fb_wrong = sum(1 for r in fb if r.get("is_correct") is False)

    fb_by_channel = defaultdict(lambda: Counter())
    wrong_questions = Counter()
    for r in fb:
        ch = r.get("channel") or "unknown"
        fb_by_channel[ch]["total"] += 1
        if r.get("is_correct") is True:
            fb_by_channel[ch]["correct"] += 1
        elif r.get("is_correct") is False:
            fb_by_channel[ch]["wrong"] += 1
            q = (r.get("question") or "").strip()
            if q:
                wrong_questions[q] += 1

    # ---- Print report ----
    print("\n=== LOG SUMMARY ===")
    print(f"Chat log: {chat_path} ({len(chat)} rows)")
    print(f"Feedback log: {fb_path} ({len(fb)} rows)\n")

    print("=== EVENTS ===")
    for k, v in events.most_common():
        print(f"- {k}: {v}")

    print("\n=== CHANNELS (chat-related events) ===")
    for k, v in channels.most_common():
        print(f"- {k}: {v}")

    print("\n=== LATENCY (event=chat) ===")
    print(f"- Samples: {len(latencies)}")
    print(f"- Avg latency_ms: {avg_latency:.2f}")

    print("\n=== FALLBACK/SAFE RESPONSES (heuristic) ===")
    chats = events.get("chat", 0)
    print(f"- Count: {fallback_count} / {chats} chats ({pct(fallback_count, chats):.1f}%)")

    print("\n=== FEEDBACK ===")
    print(f"- Total: {fb_total}")
    print(f"- Correct: {fb_correct} ({pct(fb_correct, fb_total):.1f}%)")
    print(f"- Wrong:   {fb_wrong} ({pct(fb_wrong, fb_total):.1f}%)")

    print("\n=== FEEDBACK BY CHANNEL ===")
    for ch, c in fb_by_channel.items():
        total = c["total"]
        corr = c["correct"]
        wrong = c["wrong"]
        print(f"- {ch}: total={total}, correct={corr} ({pct(corr,total):.1f}%), wrong={wrong} ({pct(wrong,total):.1f}%)")

    print(f"\n=== TOP {args.topk} WRONG-ANSWER QUESTIONS ===")
    for q, n in wrong_questions.most_common(args.topk):
        print(f"- ({n}x) {q}")

    # Optional: write a machine-readable summary
    out = {
        "chat_rows": len(chat),
        "feedback_rows": len(fb),
        "events": dict(events),
        "channels": dict(channels),
        "avg_latency_ms": avg_latency,
        "fallback_count": fallback_count,
        "fallback_rate_pct": pct(fallback_count, events.get("chat", 0)),
        "feedback_total": fb_total,
        "feedback_correct": fb_correct,
        "feedback_wrong": fb_wrong,
        "feedback_correct_rate_pct": pct(fb_correct, fb_total),
        "feedback_by_channel": {ch: dict(cnt) for ch, cnt in fb_by_channel.items()},
        "top_wrong_questions": wrong_questions.most_common(args.topk),
    }
    summary_path = logdir / "summary.json"
    summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote: {summary_path}")

if __name__ == "__main__":
    main()
