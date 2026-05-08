import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.retrieval_service import load_kb, search_hits


DEFAULT_QUERIES = [
    "sofa phòng khách có những mẫu nào?",
    "tôi cần sofa gọn cho căn hộ nhỏ",
    "thiết kế nội thất chung cư hiện đại",
    "chính sách thanh toán như thế nào?",
    "chính sách giao hàng ra sao?",
    "chính sách đổi trả như thế nào?",
]


def build_result(kb_dir: str, top_k: int) -> List[Dict[str, Any]]:
    kb = load_kb(kb_dir)
    if kb is None:
        raise ValueError(f"Could not load KB from: {kb_dir}")

    results: List[Dict[str, Any]] = []
    for query in DEFAULT_QUERIES:
        hits = search_hits(kb, query, k=top_k)
        results.append(
            {
                "query": query,
                "hits": [
                    {
                        "rank": idx + 1,
                        "score": round(hit.score, 4),
                        "title": hit.title,
                        "source": hit.source,
                        "snippet": hit.text[:220],
                    }
                    for idx, hit in enumerate(hits)
                ],
            }
        )
    return results


def print_console(results: List[Dict[str, Any]]) -> None:
    for block in results:
        print("=" * 100)
        print(f"QUERY: {block['query']}")
        if not block["hits"]:
            print("NO HITS")
            continue

        for hit in block["hits"]:
            print(f"[{hit['rank']}] score={hit['score']:.4f}")
            print(f"title: {hit['title']}")
            print(f"url: {hit['source']}")
            print(f"snippet: {hit['snippet']}")
            print()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Run a fixed Vietnamese retrieval regression query set against the current KB."
    )
    parser.add_argument(
        "--kb-dir",
        default="F:/20251/prj3/chatbot/kb/noithatcaco",
        help="KB directory containing chunks.jsonl and index.json",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top retrieval hits to print per query",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path to save the regression output as JSON",
    )
    args = parser.parse_args()

    results = build_result(args.kb_dir, args.top_k)
    print_console(results)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved JSON output to: {out_path}")


if __name__ == "__main__":
    main()
