import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.crawling.normalize import make_content_hash
from data_pipeline.crawling.quality_audit import audit_product_dataset
from data_pipeline.crawling.rag_export import convert_product_jsonl_to_rag_jsonl


DEFAULT_SOURCE_URL = "https://gotrangtri.vn"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def count_jsonl_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def detect_source_name(input_path: Path, explicit_source: Optional[str]) -> str:
    if explicit_source and explicit_source.strip():
        return explicit_source.strip()
    name = input_path.stem.lower()
    if "gotrangtri" in name:
        return "gotrangtri"
    return input_path.stem


def load_report(report_path: Path) -> Dict[str, Any]:
    if not report_path.is_file():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def infer_created_at(report: Dict[str, Any]) -> str:
    value = report.get("generated_at") or report.get("created_at") or utc_now_iso()
    return str(value)


def infer_product_count(report: Dict[str, Any], rag_products_path: Path) -> int:
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    extracted = counts.get("extracted_count")
    if isinstance(extracted, int) and extracted >= 0:
        return extracted
    return count_jsonl_rows(rag_products_path)


def build_manifest(
    dataset_id: str,
    source: str,
    source_url: str,
    version: Optional[str],
    created_at: str,
    product_count: int,
    rag_chunk_count: int,
    content_hash: str,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "source": source,
        "source_url": source_url,
        "created_at": created_at,
        "product_count": product_count,
        "rag_chunk_count": rag_chunk_count,
        "content_hash": content_hash,
        "files": {
            "rag_products": "rag_products.jsonl"
        },
    }
    if version:
        manifest["version"] = version
    return manifest


def materialize_product_dataset(
    input_path: str | Path,
    output_dir: str | Path,
    dataset_id: str,
    source: Optional[str] = None,
    source_url: Optional[str] = None,
    version: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    input_file = resolve_path(input_path)
    dataset_dir = resolve_path(output_dir)
    if not input_file.is_file():
        raise FileNotFoundError(f"Input product JSONL not found: {input_file}")

    if dataset_dir.exists() and any(dataset_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Dataset directory is not empty: {dataset_dir}")
    dataset_dir.mkdir(parents=True, exist_ok=True)

    source_name = detect_source_name(input_file, source)
    source_url_value = (source_url or "").strip() or DEFAULT_SOURCE_URL

    rag_products_path = dataset_dir / "rag_products.jsonl"
    with tempfile.TemporaryDirectory(prefix="materialize-product-dataset-") as tmp_dir:
        temp_rag_path = Path(tmp_dir) / "rag_products.jsonl"
        chunk_stats = convert_product_jsonl_to_rag_jsonl(input_file, temp_rag_path)
        shutil.copy2(temp_rag_path, rag_products_path)
    report = load_report(input_file.with_suffix(input_file.suffix + ".report.json"))
    product_count = infer_product_count(report, rag_products_path)
    rag_chunk_count = int(chunk_stats.get("count") or 0)
    created_at = infer_created_at(report)
    content_hash = make_content_hash(rag_products_path.read_text(encoding="utf-8"))

    manifest = build_manifest(
        dataset_id=dataset_id,
        source=source_name,
        source_url=source_url_value,
        version=version.strip() if version else None,
        created_at=created_at,
        product_count=product_count,
        rag_chunk_count=rag_chunk_count,
        content_hash=content_hash,
    )
    manifest_path = dataset_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    quality_report = audit_product_dataset(dataset_dir, write_report=True)

    return {
        "success": True,
        "dataset_id": dataset_id,
        "source": source_name,
        "source_url": source_url_value,
        "version": version,
        "input_path": str(input_file),
        "output_dir": str(dataset_dir),
        "manifest_path": str(manifest_path),
        "rag_products_path": str(rag_products_path),
        "product_count": product_count,
        "rag_chunk_count": rag_chunk_count,
        "created_at": created_at,
        "quality_audit_path": quality_report.get("quality_audit_path"),
        "quality_status": quality_report.get("status"),
        "quality_reasons": quality_report.get("reasons", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize a crawled product JSONL into a registerable product dataset folder.")
    parser.add_argument("--input", required=True, help="Path to product JSONL from data_pipeline output.")
    parser.add_argument("--output-dir", required=True, help="Directory that will receive manifest.json and rag_products.jsonl.")
    parser.add_argument("--dataset-id", required=True, help="Dataset ID stored in manifest.json.")
    parser.add_argument("--source", help="Optional source override, e.g. gotrangtri.")
    parser.add_argument("--source-url", help="Optional source URL override.")
    parser.add_argument("--version", help="Optional dataset version string.")
    parser.add_argument("--overwrite", action="store_true", help="Allow writing into a non-empty output directory.")
    args = parser.parse_args()

    result = materialize_product_dataset(
        input_path=args.input,
        output_dir=args.output_dir,
        dataset_id=args.dataset_id,
        source=args.source,
        source_url=args.source_url,
        version=args.version,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
