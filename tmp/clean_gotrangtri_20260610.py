import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

MOJIBAKE_RE = re.compile(r"(RÃ|Ã¨|Ã©|Ãª|Ã´|Ã¡|Ã¢|Ã|á»|áº|Ä|Æ|�|cá»|gá»|tháº|sáº|ná»)")
VIETNAMESE_RE = re.compile(r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", re.I)

TEXT_FIELDS = ("product_name",)
RAG_TEXT_FIELDS = ("title", "text", "content")


def has_mojibake(value):
    return bool(value and MOJIBAKE_RE.search(str(value)))


def mojibake_score(value):
    text = str(value or "")
    return len(MOJIBAKE_RE.findall(text)) + text.count("�") * 3


def vietnamese_score(value):
    return len(VIETNAMESE_RE.findall(str(value or "")))


def repair_text(value):
    if not isinstance(value, str) or not has_mojibake(value):
        return value, False
    candidates = []
    for enc in ("latin1", "cp1252"):
        try:
            candidate = value.encode(enc).decode("utf-8")
            candidates.append(candidate)
        except UnicodeError:
            pass
    if not candidates:
        return value, False
    original_moji = mojibake_score(value)
    original_vn = vietnamese_score(value)
    best = min(candidates, key=lambda text: (mojibake_score(text), -vietnamese_score(text), abs(len(text) - len(value))))
    if mojibake_score(best) < original_moji and vietnamese_score(best) >= original_vn and len(best.strip()) >= max(3, int(len(value.strip()) * 0.6)):
        return unicodedata.normalize("NFC", best), True
    return value, False


def read_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if line.strip():
                rows.append((line_no, json.loads(line)))
    return rows


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ": ")) + "\n")


def catalog_key(row):
    return row.get("content_hash") or row.get("canonical_url") or row.get("source_url") or row.get("product_name")


def rag_key(row):
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return metadata.get("content_hash") or row.get("url") or row.get("source") or metadata.get("canonical_url") or metadata.get("source_url")


def excerpt(value, size=240):
    text = str(value or "")
    return text[:size]


def scan_candidates(catalog_rows, rag_rows, output_path):
    rag_by_key = {rag_key(row): row for _, row in rag_rows if rag_key(row)}
    count_catalog = count_rag_title = count_rag_text = 0
    emitted = 0
    with Path(output_path).open("w", encoding="utf-8", newline="\n") as handle:
        for line_no, row in catalog_rows:
            key = catalog_key(row)
            rag = rag_by_key.get(key) or {}
            suspected = []
            if has_mojibake(row.get("product_name")):
                suspected.append("catalog.product_name")
                count_catalog += 1
            if has_mojibake(rag.get("title")):
                suspected.append("rag.title")
                count_rag_title += 1
            if has_mojibake(rag.get("text")) or has_mojibake(rag.get("content")):
                suspected.append("rag.text")
                count_rag_text += 1
            if suspected:
                handle.write(json.dumps({
                    "catalog_line": line_no,
                    "url": row.get("source_url") or row.get("canonical_url"),
                    "old_product_name": row.get("product_name"),
                    "old_rag_title": rag.get("title"),
                    "old_rag_text_excerpt": excerpt(rag.get("text") or rag.get("content")),
                    "suspected_fields": suspected,
                }, ensure_ascii=False) + "\n")
                emitted += 1
    return {
        "candidate_rows": emitted,
        "catalog_product_name": count_catalog,
        "rag_title": count_rag_title,
        "rag_text": count_rag_text,
    }


def apply_fix(catalog_rows, rag_rows):
    fixed_catalog_by_key = {}
    catalog_fixed = 0
    catalog_uncertain = 0
    new_catalog = []
    for _, row in catalog_rows:
        next_row = dict(row)
        if has_mojibake(row.get("product_name")):
            repaired, changed = repair_text(row.get("product_name"))
            if changed:
                next_row["product_name"] = repaired
                fixed_catalog_by_key[catalog_key(row)] = repaired
                catalog_fixed += 1
            else:
                catalog_uncertain += 1
        new_catalog.append(next_row)

    rag_fixed_rows = 0
    rag_uncertain_rows = 0
    new_rag = []
    for _, row in rag_rows:
        next_row = dict(row)
        key = rag_key(row)
        row_changed = False
        row_uncertain = False
        metadata = dict(next_row.get("metadata") or {})
        if key in fixed_catalog_by_key:
            fixed_name = fixed_catalog_by_key[key]
            old_meta_name = metadata.get("product_name")
            if old_meta_name:
                metadata["product_name"], _ = repair_text(old_meta_name)
            old_title = next_row.get("title") or ""
            if has_mojibake(old_title):
                suffix = ""
                if " - " in old_title:
                    suffix = " - " + old_title.split(" - ", 1)[1]
                    suffix, _ = repair_text(suffix)
                next_row["title"] = fixed_name + suffix if suffix else fixed_name
                row_changed = True
            for field in ("text", "content"):
                value = next_row.get(field)
                if isinstance(value, str) and has_mojibake(value):
                    repaired, changed = repair_text(value)
                    if changed:
                        next_row[field] = repaired
                        row_changed = True
                    else:
                        # Conservative fallback: only replace exact old mojibake product name with fixed name.
                        old_name = row.get("metadata", {}).get("product_name") if isinstance(row.get("metadata"), dict) else None
                        if old_name and has_mojibake(old_name) and old_name in value:
                            next_row[field] = value.replace(old_name, fixed_name)
                            row_changed = True
                        else:
                            row_uncertain = True
        else:
            for field in RAG_TEXT_FIELDS:
                value = next_row.get(field)
                if isinstance(value, str) and has_mojibake(value):
                    repaired, changed = repair_text(value)
                    if changed:
                        next_row[field] = repaired
                        row_changed = True
                    else:
                        row_uncertain = True
        if metadata:
            next_row["metadata"] = metadata
        if row_changed:
            rag_fixed_rows += 1
        elif row_uncertain:
            rag_uncertain_rows += 1
        new_rag.append(next_row)
    return new_catalog, new_rag, {
        "catalog_fixed_rows": catalog_fixed,
        "catalog_uncertain_rows": catalog_uncertain,
        "rag_fixed_rows": rag_fixed_rows,
        "rag_uncertain_rows": rag_uncertain_rows,
    }


def audit(catalog_rows, rag_rows):
    def non_empty(v):
        return v not in (None, "", [], {})
    return {
        "catalog_lines": len(catalog_rows),
        "rag_lines": len(rag_rows),
        "coverage": {
            "price": sum(1 for _, r in catalog_rows if non_empty(r.get("price"))),
            "material": sum(1 for _, r in catalog_rows if non_empty(r.get("material"))),
            "dimensions": sum(1 for _, r in catalog_rows if non_empty(r.get("dimensions"))),
        },
        "mojibake": {
            "product_name": sum(1 for _, r in catalog_rows if has_mojibake(r.get("product_name"))),
            "rag_title": sum(1 for _, r in rag_rows if has_mojibake(r.get("title"))),
            "rag_text": sum(1 for _, r in rag_rows if has_mojibake(r.get("text")) or has_mojibake(r.get("content"))),
        },
        "category_distribution": dict(Counter(str(r.get("category")) for _, r in catalog_rows if r.get("category"))),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dataset_dir = Path(args.dataset_dir)
    catalog_path = dataset_dir / "catalog.jsonl"
    rag_path = dataset_dir / "rag_products.jsonl"
    catalog_rows = read_jsonl(catalog_path)
    rag_rows = read_jsonl(rag_path)
    before = audit(catalog_rows, rag_rows)
    candidates = scan_candidates(catalog_rows, rag_rows, args.candidates)
    result = {"before": before, "candidates": candidates}
    if args.apply:
        new_catalog, new_rag, fix_stats = apply_fix(catalog_rows, rag_rows)
        write_jsonl(catalog_path, new_catalog)
        write_jsonl(rag_path, new_rag)
        after_catalog_rows = read_jsonl(catalog_path)
        after_rag_rows = read_jsonl(rag_path)
        result["fix"] = fix_stats
        result["after"] = audit(after_catalog_rows, after_rag_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
