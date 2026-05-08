import argparse
import json
import re
import sys
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


CHATBOT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CHATBOT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chatbot.app.retrieval_service import load_kb, normalize_retrieval_mode, search_hits  # noqa: E402

from chatbot.eval.metrics import (  # noqa: E402
    first_matching_ground_truth,
    normalize_identifier,
    recall_at_k,
    reciprocal_rank,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_DATASET = CHATBOT_ROOT / "eval" / "dataset.jsonl"
DEFAULT_DATASET_NOTES = CHATBOT_ROOT / "eval" / "dataset-notes.md"
DEFAULT_KB_DIR = CHATBOT_ROOT / "kb" / "noithatcaco"
DEFAULT_MODE = "keyword"


@dataclass
class EvalExample:
    question: str
    ground_truth: List[str]


@dataclass
class EvaluationSummary:
    mode: str
    recall_at_k: float
    mrr: float
    top_k: int
    total_questions: int


@dataclass
class DatasetMetadata:
    dataset_size: int
    category_coverage: dict[str, int]


def load_dataset(dataset_path: Path) -> List[EvalExample]:
    examples: List[EvalExample] = []
    # Use utf-8-sig so JSONL files still load if they were created with a BOM.
    with dataset_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[warn] skip line {line_number}: invalid JSON ({exc})", file=sys.stderr)
                continue

            question = str(row.get("question") or "").strip()
            raw_ground_truth = row.get("ground_truth") or []
            if isinstance(raw_ground_truth, str):
                ground_truth = [raw_ground_truth.strip()] if raw_ground_truth.strip() else []
            elif isinstance(raw_ground_truth, list):
                ground_truth = [str(item).strip() for item in raw_ground_truth if str(item).strip()]
            else:
                ground_truth = []

            if not question:
                print(f"[warn] skip line {line_number}: missing question", file=sys.stderr)
                continue
            if not ground_truth:
                print(f"[warn] skip line {line_number}: missing ground_truth", file=sys.stderr)
                continue

            examples.append(EvalExample(question=question, ground_truth=ground_truth))
    return examples


def load_dataset_metadata(dataset_path: Path, dataset_notes_path: Path) -> DatasetMetadata:
    dataset = load_dataset(dataset_path)
    dataset_size = len(dataset)
    category_coverage: dict[str, int] = {}

    if dataset_notes_path.exists():
        notes = dataset_notes_path.read_text(encoding="utf-8")
        for line in notes.splitlines():
            match = re.match(r"-\s+(.+?):\s+(\d+)\s*$", line.strip())
            if not match:
                continue
            category = match.group(1).strip()
            count = int(match.group(2))
            if category.lower() == "dataset size":
                dataset_size = count
            else:
                category_coverage[category] = count

    return DatasetMetadata(dataset_size=dataset_size, category_coverage=category_coverage)


def hit_identifiers(hit: object) -> List[str]:
    identifiers: List[str] = []
    for value in (
        getattr(hit, "source", ""),
        getattr(hit, "metadata", {}).get("url", "") if getattr(hit, "metadata", None) else "",
        getattr(hit, "title", ""),
        getattr(hit, "doc_id", ""),
    ):
        normalized = normalize_identifier(value)
        if normalized and normalized not in {normalize_identifier(item) for item in identifiers}:
            identifiers.append(str(value).strip())
    return identifiers


def primary_identifier(hit: object) -> str:
    identifiers = hit_identifiers(hit)
    return identifiers[0] if identifiers else ""


def retrieval_candidate(hit: object) -> dict[str, str]:
    return {
        "identifier": primary_identifier(hit),
        "title": (getattr(hit, "title", "") or "").strip(),
    }


def matched_identifier(predicted_candidates: Iterable[dict[str, str]], ground_truth_ids: Iterable[str]) -> str:
    for candidate in predicted_candidates:
        matched = first_matching_ground_truth(candidate, ground_truth_ids)
        if matched is not None:
            ground_truth, field = matched
            return f"{candidate.get(field, '')} <- matched by {ground_truth} ({field})"
    return "none"


def format_hit_debug(rank: int, hit: object) -> str:
    title = getattr(hit, "title", "").strip() or "(no title)"
    source = getattr(hit, "source", "").strip() or getattr(hit, "doc_id", "").strip() or "(no source)"
    score = getattr(hit, "score", 0.0)
    return f"  {rank}. score={score:.4f} title={title} source={source}"


def run_evaluation(
    mode: str,
    dataset_path: Path,
    kb_dir: Path,
    top_k: int,
    verbose: bool = True,
) -> EvaluationSummary | None:
    dataset = load_dataset(dataset_path)
    if not dataset:
        print(f"No valid examples found in {dataset_path}")
        return None

    normalized_mode = normalize_retrieval_mode(mode, use_heuristics=(mode != "baseline"))
    kb = load_kb(
        str(kb_dir),
        use_heuristics=(normalized_mode != "baseline"),
        mode=normalized_mode,
    )
    if kb is None:
        print(f"Could not load KB from {kb_dir}", file=sys.stderr)
        return None

    recall_scores: List[float] = []
    reciprocal_ranks: List[float] = []

    if verbose:
        print(f"Mode:     {normalized_mode}")
        print(f"Dataset:  {dataset_path}")
        print(f"KB dir:   {kb_dir}")
        print(f"Top-k:    {top_k}")
        print("")

    for index, example in enumerate(dataset, start=1):
        hits = search_hits(kb, example.question, k=top_k)
        predicted_candidates = [retrieval_candidate(hit) for hit in hits]
        recall_value = recall_at_k(predicted_candidates, example.ground_truth, top_k)
        rr_value = reciprocal_rank(predicted_candidates, example.ground_truth, top_k)
        recall_scores.append(recall_value)
        reciprocal_ranks.append(rr_value)

        if verbose:
            print(f"[{index}] Question: {example.question}")
            print(f"    Ground truth: {example.ground_truth}")
            if hits:
                print("    Retrieved:")
                for rank, hit in enumerate(hits, start=1):
                    print(format_hit_debug(rank, hit))
            else:
                print("    Retrieved: none")
            print(f"    Match: {matched_identifier(predicted_candidates[:top_k], example.ground_truth)}")
            print(f"    Recall@{top_k}: {recall_value:.4f}")
            print(f"    RR: {rr_value:.4f}")
            print("")

    avg_recall = sum(recall_scores) / len(recall_scores)
    avg_mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

    if verbose:
        print("Final metrics")
        print(f"Recall@{top_k}: {avg_recall:.4f}")
        print(f"MRR:       {avg_mrr:.4f}")

    return EvaluationSummary(
        mode=normalized_mode,
        recall_at_k=avg_recall,
        mrr=avg_mrr,
        top_k=top_k,
        total_questions=len(dataset),
    )


def print_comparison(*summaries: EvaluationSummary) -> None:
    print("===== COMPARISON =====")
    for summary in summaries:
        print(f"{summary.mode.capitalize()}:")
        print(f"  Recall@{summary.top_k}: {summary.recall_at_k:.4f}")
        print(f"  MRR: {summary.mrr:.4f}")
        print("")


def build_results_payload(
    dataset_path: Path,
    dataset_notes_path: Path,
    kb_dir: Path,
    top_k: int,
    command: str,
    summaries: List[EvaluationSummary],
) -> dict:
    metadata = load_dataset_metadata(dataset_path, dataset_notes_path)
    return {
        "dataset": {
            "path": str(dataset_path),
            "notes_path": str(dataset_notes_path),
            "size": metadata.dataset_size,
            "category_coverage": metadata.category_coverage,
        },
        "kb_dir": str(kb_dir),
        "top_k": top_k,
        "command": command,
        "results": [asdict(summary) for summary in summaries],
        "interpretation": [
            "Keyword is strongest on the current 48-question Vietnamese dataset.",
            "Vector, hybrid, and hybrid_rerank did not outperform the tuned keyword baseline on Recall@5 and MRR.",
        ],
    }


def write_results_json(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_results_markdown(output_path: Path, payload: dict) -> None:
    dataset = payload["dataset"]
    results = payload["results"]
    lines = [
        "# Retrieval benchmark summary",
        "",
        f"- Dataset: `{dataset['path']}`",
        f"- Dataset size: {dataset['size']}",
        f"- KB dir: `{payload['kb_dir']}`",
        f"- Top-k: {payload['top_k']}",
        "",
        "## Category coverage",
        "",
    ]

    if dataset["category_coverage"]:
        for category, count in dataset["category_coverage"].items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- No category coverage summary available.")

    lines.extend([
        "",
        "## Metrics",
        "",
        "| Mode | Recall@5 | MRR |",
        "| --- | ---: | ---: |",
    ])
    for result in results:
        lines.append(f"| {result['mode']} | {result['recall_at_k']:.4f} | {result['mrr']:.4f} |")

    lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    for line in payload["interpretation"]:
        lines.append(f"- {line}")

    lines.extend([
        "",
        "## Reproducible command",
        "",
        "```bash",
        payload["command"],
        "```",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(
    dataset_path: Path,
    kb_dir: Path,
    top_k: int,
    mode: str = DEFAULT_MODE,
    compare: bool = False,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> int:
    if compare:
        keyword = run_evaluation("keyword", dataset_path, kb_dir, top_k, verbose=False)
        vector = run_evaluation("vector", dataset_path, kb_dir, top_k, verbose=False)
        hybrid = run_evaluation("hybrid", dataset_path, kb_dir, top_k, verbose=False)
        hybrid_rerank = run_evaluation("hybrid_rerank", dataset_path, kb_dir, top_k, verbose=False)
        if keyword is None or vector is None or hybrid is None or hybrid_rerank is None:
            return 1
        summaries = [keyword, vector, hybrid, hybrid_rerank]
        print(f"Dataset:  {dataset_path}")
        print(f"KB dir:   {kb_dir}")
        print(f"Top-k:    {top_k}")
        print("")
        print_comparison(*summaries)

        if output_json is not None or output_md is not None:
            command = (
                f"python chatbot/eval/runner.py --dataset {dataset_path} "
                f"--kb-dir {kb_dir} --top-k {top_k} --compare"
            )
            payload = build_results_payload(
                dataset_path=dataset_path,
                dataset_notes_path=DEFAULT_DATASET_NOTES,
                kb_dir=kb_dir,
                top_k=top_k,
                command=command,
                summaries=summaries,
            )
            if output_json is not None:
                write_results_json(output_json, payload)
            if output_md is not None:
                write_results_markdown(output_md, payload)
        return 0

    summary = run_evaluation(mode, dataset_path, kb_dir, top_k, verbose=True)
    if summary is None:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality with Recall@k and MRR.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to JSONL eval dataset.")
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR, help="Path to KB directory containing chunks.jsonl and index.json.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieval results to evaluate.")
    parser.add_argument("--mode", choices=["keyword", "vector", "hybrid", "hybrid_rerank", "baseline", "improved"], default=DEFAULT_MODE, help="Retrieval scoring mode to evaluate.")
    parser.add_argument("--compare", action="store_true", help="Run keyword, vector, hybrid, and hybrid_rerank modes and print a summary comparison.")
    parser.add_argument("--output-json", type=Path, help="Optional path to export comparison results as JSON.")
    parser.add_argument("--output-md", type=Path, help="Optional path to export comparison results as Markdown.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        evaluate(
            args.dataset,
            args.kb_dir,
            args.top_k,
            mode=args.mode,
            compare=args.compare,
            output_json=args.output_json,
            output_md=args.output_md,
        )
    )
