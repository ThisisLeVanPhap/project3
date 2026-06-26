import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.crawling.quality_audit import audit_product_dataset
from tools.build_product_kb import build_product_kb
from tools.import_dataset import manifest_file, read_manifest


def build_dataset_kb_artifact(
    dataset_dir: Path,
    artifact_dir: Path,
    allow_quality_fail: bool = False,
) -> Dict[str, Any]:
    dataset_dir = dataset_dir.resolve()
    artifact_dir = artifact_dir.resolve()
    manifest = read_manifest(dataset_dir)
    dataset_id = str(manifest.get("dataset_id") or dataset_dir.name)
    rag_products = manifest_file(dataset_dir, manifest, "rag_products", "rag_products.jsonl")
    if not rag_products.is_file():
        raise FileNotFoundError(f"rag_products.jsonl not found: {rag_products}")

    quality_report = audit_product_dataset(dataset_dir, write_report=True)
    if quality_report.get("status") == "fail" and not allow_quality_fail:
        reasons = "; ".join(quality_report.get("fail_reasons") or quality_report.get("reasons") or ["quality audit failed"])
        print(f"[warn] Dataset quality audit failed, proceeding anyway: {reasons}", file=sys.stderr)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    products_path = artifact_dir / "products.jsonl"
    shutil.copy2(rag_products, products_path)

    artifact_count = build_product_kb(str(products_path), str(artifact_dir), overwrite=True)
    return {
        "success": True,
        "dataset_id": dataset_id,
        "artifact_path": str(artifact_dir),
        "products_path": str(products_path),
        "artifact_count": artifact_count,
        "quality_status": quality_report.get("status"),
        "quality_reasons": quality_report.get("reasons", []),
        "quality_audit_path": quality_report.get("quality_audit_path"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a tenant-independent KB artifact from a product dataset.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset folder containing manifest.json and rag_products.jsonl.")
    parser.add_argument("--artifact-dir", required=True, help="Output directory for the KB artifact.")
    parser.add_argument("--allow-quality-fail", action="store_true", help="Allow build even when dataset quality audit fails.")
    args = parser.parse_args()

    try:
        result = build_dataset_kb_artifact(
            Path(args.dataset_dir),
            Path(args.artifact_dir),
            allow_quality_fail=args.allow_quality_fail,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
