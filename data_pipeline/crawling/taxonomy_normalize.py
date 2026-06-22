import json
import shutil
from pathlib import Path
from typing import Any

from data_pipeline.crawling.quality_audit import audit_product_dataset
from data_pipeline.crawling.rag_export import convert_product_jsonl_to_rag_jsonl
from data_pipeline.crawling.taxonomy_profiles import get_taxonomy_profile, infer_dataset_source
from data_pipeline.crawling.taxonomy_profiles.gotrangtri import decide_category


def normalize_dataset_taxonomy(
    dataset_dir: str | Path,
    changes_path: str | Path | None = None,
    apply: bool = False,
    backup: bool = True,
    source: str | None = None,
) -> dict[str, Any]:
    dataset_path = Path(dataset_dir)
    catalog_path = dataset_path / "catalog.jsonl"
    rag_path = dataset_path / "rag_products.jsonl"
    if not catalog_path.is_file():
        raise FileNotFoundError(f"catalog.jsonl not found: {catalog_path}")
    if not rag_path.is_file():
        raise FileNotFoundError(f"rag_products.jsonl not found: {rag_path}")

    resolved_source = source or infer_dataset_source(dataset_path)
    profile = get_taxonomy_profile(resolved_source, apply=apply)
    can_apply = apply and profile.mode != "report-only"

    rows = _read_jsonl(catalog_path)
    changes: list[dict[str, Any]] = []
    next_rows = []
    for row in rows:
        decision = profile.rules(row)
        old_category = row.get("category")
        if decision.category and old_category != decision.category and _allowed_change(old_category, decision.category):
            changes.append({
                "url": row.get("source_url") or row.get("canonical_url") or row.get("url"),
                "product_name": row.get("product_name"),
                "old_category": old_category,
                "new_category": decision.category,
                "matched_rule": decision.rule,
                "confidence": decision.confidence,
                "taxonomy_profile_used": profile.name,
            })
            if can_apply:
                row = dict(row)
                row["category"] = decision.category
        next_rows.append(row)

    output_changes = Path(changes_path) if changes_path else dataset_path / "taxonomy_changes.jsonl"
    output_changes.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_changes, changes)

    applied_count = len(changes) if can_apply else 0
    if can_apply and changes:
        if backup:
            _backup_once(catalog_path, ".bak.taxonomy")
            _backup_once(rag_path, ".bak.taxonomy")
        _write_jsonl(catalog_path, next_rows)
        convert_product_jsonl_to_rag_jsonl(catalog_path, rag_path)

    audit = audit_product_dataset(dataset_path, write_report=True)
    unresolved_suspects_count = int(audit.get("suspicious_category_count") or 0)
    warnings = [profile.warning] if profile.warning else []
    result = {
        "dataset_dir": str(dataset_path),
        "changes_path": str(output_changes),
        "dry_run": not can_apply,
        "input_rows": len(rows),
        "change_count": len(changes),
        "applied_count": applied_count,
        "category_distribution_before": _category_distribution(rows),
        "category_distribution_after": _category_distribution(next_rows),
        "source": resolved_source,
        "taxonomy_profile_used": profile.name,
        "normalization_mode": profile.mode,
        "warnings": warnings,
        "quality_audit_path": audit.get("quality_audit_path"),
        "unresolved_suspects_count": unresolved_suspects_count,
    }
    _merge_taxonomy_audit_metadata(
        dataset_path,
        taxonomy_profile_used=profile.name,
        normalization_mode=profile.mode,
        applied_changes_count=applied_count,
        unresolved_suspects_count=unresolved_suspects_count,
        warnings=warnings,
    )
    return result


def _allowed_change(old_category: Any, new_category: str) -> bool:
    old = str(old_category or "").strip()
    if not old:
        return True
    if new_category == "Tủ" and old in {"Kệ", "Giường"}:
        return True
    if new_category == "Kệ" and old in {"Tủ", "Giường", "Đồ trang trí"}:
        return True
    if new_category == "Đèn" and old in {"Kệ", "Tủ", "Bàn ăn", "Đồ trang trí"}:
        return True
    if new_category in {"Bàn làm việc", "Bàn trà", "Sofa", "Giường", "Rèm", "Gương"} and old in {"Kệ", "Tủ", "Đồ trang trí"}:
        return True
    return False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _backup_once(path: Path, suffix: str) -> None:
    backup = path.with_name(path.name + suffix)
    if not backup.exists():
        shutil.copy2(path, backup)


def _merge_taxonomy_audit_metadata(
    dataset_path: Path,
    taxonomy_profile_used: str,
    normalization_mode: str,
    applied_changes_count: int,
    unresolved_suspects_count: int,
    warnings: list[str],
) -> None:
    audit_path = dataset_path / "quality_audit.json"
    if audit_path.is_file():
        report = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    else:
        report = {}
    report.update({
        "taxonomy_profile_used": taxonomy_profile_used,
        "normalization_mode": normalization_mode,
        "applied_changes_count": applied_changes_count,
        "unresolved_suspects_count": unresolved_suspects_count,
    })
    if warnings:
        existing = report.get("warnings") if isinstance(report.get("warnings"), list) else []
        report["warnings"] = [*existing, *[warning for warning in warnings if warning not in existing]]
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        category = str(row.get("category") or "").strip() or "__missing__"
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
