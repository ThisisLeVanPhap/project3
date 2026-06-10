import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.build_product_kb import build_product_kb


def read_manifest(dataset_dir: Path) -> Dict[str, Any]:
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.json not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8-sig"))


def manifest_file(dataset_dir: Path, manifest: Dict[str, Any], key: str, fallback: str) -> Path:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return dataset_dir / str(files.get(key) or fallback)


def import_dataset(dataset_dir: Path, tenant_code: str, kb_base: Path, version_tag: str | None) -> Dict[str, Any]:
    dataset_dir = dataset_dir.resolve()
    kb_base = kb_base.resolve()
    manifest = read_manifest(dataset_dir)
    dataset_id = str(manifest.get("dataset_id") or dataset_dir.name)
    rag_products = manifest_file(dataset_dir, manifest, "rag_products", "rag_products.jsonl")
    if not rag_products.is_file():
        raise FileNotFoundError(f"rag_products.jsonl not found: {rag_products}")

    tenant_kb_dir = kb_base / tenant_code
    build_dir = tenant_kb_dir / "versions" / version_tag if version_tag else tenant_kb_dir
    build_dir.mkdir(parents=True, exist_ok=True)

    products_path = build_dir / "products.jsonl"
    shutil.copy2(rag_products, products_path)

    chunk_count = build_product_kb(str(products_path), str(build_dir), overwrite=True)
    result = {
        "success": True,
        "tenant_code": tenant_code,
        "dataset_id": dataset_id,
        "kb_dir": str(build_dir),
        "products_path": str(products_path),
        "chunk_count": chunk_count,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a product dataset into a tenant KB directory.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset folder containing manifest.json and rag_products.jsonl.")
    parser.add_argument("--tenant-code", required=True, help="Tenant code used under kb-base.")
    parser.add_argument("--kb-base", required=True, help="Base directory for tenant KB folders.")
    parser.add_argument("--version-tag", help="Optional KB version folder name under <tenant>/versions.")
    args = parser.parse_args()

    try:
        result = import_dataset(
            Path(args.dataset_dir),
            args.tenant_code.strip(),
            Path(args.kb_base),
            args.version_tag.strip() if args.version_tag else None,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
