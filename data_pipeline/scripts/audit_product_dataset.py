import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_pipeline.crawling.quality_audit import audit_product_dataset


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audit a materialized product dataset folder.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset folder containing manifest.json and rag_products.jsonl.")
    parser.add_argument("--output", help="Output quality audit JSON path. Defaults to <dataset-dir>/quality_audit.json.")
    parser.add_argument("--fail-on-fail", action="store_true", help="Exit non-zero when audit status is fail.")
    args = parser.parse_args()

    report = audit_product_dataset(
        Path(args.dataset_dir),
        output_path=Path(args.output) if args.output else None,
        write_report=True,
    )
    print(json.dumps(report, ensure_ascii=False))
    if args.fail_on_fail and report.get("status") == "fail":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
