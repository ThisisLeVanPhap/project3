import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_pipeline.crawling.taxonomy_normalize import normalize_dataset_taxonomy


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Normalize product dataset taxonomy using conservative rules.")
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--changes", help="JSONL file to write proposed/applied changes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", help="Dataset source/profile, e.g. gotrangtri. Defaults to manifest source when present.")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    result = normalize_dataset_taxonomy(
        dataset_dir=Path(args.dataset_dir),
        changes_path=Path(args.changes) if args.changes else None,
        apply=args.apply,
        backup=not args.no_backup,
        source=args.source,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
