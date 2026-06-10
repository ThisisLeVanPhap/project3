import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.retrievers.text import tokenize


REQUIRED_CHUNK_FIELDS = (
    "shop",
    "url",
    "title",
    "content",
    "doc_id",
    "chunk_id",
    "text",
    "source",
    "tenant_id",
    "metadata",
)


def normalize_product_chunk(chunk: Dict[str, Any], idx: int = 0) -> Dict[str, Any]:
    normalized = dict(chunk)
    metadata = normalized.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    normalized["metadata"] = metadata

    content = normalized.get("content") or normalized.get("text") or ""
    text = normalized.get("text") or normalized.get("content") or ""
    url = normalized.get("url") or normalized.get("source") or metadata.get("source_url") or metadata.get("canonical_url") or ""
    source = normalized.get("source") or normalized.get("url") or url
    tenant_id = normalized.get("tenant_id") or metadata.get("tenant_id") or normalized.get("shop") or ""
    shop = normalized.get("shop") or tenant_id
    title = normalized.get("title") or metadata.get("product_name") or ""
    doc_id = normalized.get("doc_id") or normalized.get("id") or url or f"product-{idx}"
    chunk_id = normalized.get("chunk_id") or normalized.get("id") or f"{doc_id}#chunk-{idx}"

    normalized.update(
        {
            "shop": shop,
            "url": url,
            "title": title,
            "content": content,
            "doc_id": str(doc_id),
            "chunk_id": str(chunk_id),
            "text": text,
            "source": source,
            "tenant_id": tenant_id,
        }
    )

    for field in REQUIRED_CHUNK_FIELDS:
        normalized.setdefault(field, {} if field == "metadata" else "")

    return normalized


def load_product_chunks(input_path: Path) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            chunks.append(normalize_product_chunk(json.loads(line), idx=idx))
    return chunks


def build_index(chunks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    chunk_list = list(chunks)
    df: Counter[str] = Counter()
    for chunk in chunk_list:
        indexed_text = (chunk.get("title") or "") + " " + (chunk.get("content") or "")
        for token in set(tokenize(indexed_text)):
            df[token] += 1

    total = len(chunk_list)
    idf = {token: 1.0 + math.log((total + 1) / (count + 1)) for token, count in df.items()}
    return {
        "N": total,
        "idf": idf,
        "tokenization": {
            "mode": "unicode_with_accent_fold_aliases",
            "preserves_diacritics": True,
            "mixed_query_support": "Vietnamese tokens are indexed in original and accent-folded forms.",
        },
        "source": {
            "mode": "product_chunks_normalized",
            "indexed_fields": ["title", "content"],
            "notes": [
                "Uses the same tokenizer and IDF formula as tools.build_kb.",
                "Chunks are already pre-split product records; crawler extraction is not modified.",
            ],
        },
    }


def build_product_kb(input_path: str, kb_dir: str, overwrite: bool = False) -> int:
    input_file = Path(input_path)
    output_dir = Path(kb_dir)
    chunks_path = output_dir / "chunks.jsonl"
    index_path = output_dir / "index.json"

    if not input_file.exists():
        raise FileNotFoundError(f"Input product chunks not found: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing_outputs = [path for path in (chunks_path, index_path) if path.exists()]
    if existing_outputs and not overwrite:
        existing = ", ".join(str(path) for path in existing_outputs)
        raise FileExistsError(f"Refusing to overwrite existing KB files without --overwrite: {existing}")

    chunks = load_product_chunks(input_file)
    index = build_index(chunks)

    with chunks_path.open("w", encoding="utf-8") as out:
        for chunk in chunks:
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    with index_path.open("w", encoding="utf-8") as out:
        json.dump(index, out, ensure_ascii=False)

    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a BaselineRetriever-compatible product KB.")
    parser.add_argument("--input", required=True, help="Path to product chunks JSONL.")
    parser.add_argument("--kb-dir", required=True, help="Directory that will receive chunks.jsonl and index.json.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing chunks.jsonl/index.json in kb-dir.")
    args = parser.parse_args()

    total_chunks = build_product_kb(args.input, args.kb_dir, overwrite=args.overwrite)
    print(f"Built product KB: {total_chunks} chunks")


if __name__ == "__main__":
    main()
