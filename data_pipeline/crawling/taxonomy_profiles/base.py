import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from data_pipeline.crawling.taxonomy_profiles.common import TaxonomyDecision, no_decision

RuleSet = Callable[[dict[str, Any]], TaxonomyDecision]


@dataclass(frozen=True)
class TaxonomyProfile:
    name: str
    mode: str
    rules: RuleSet
    warning: str | None = None


def get_taxonomy_profile(source: str | None, apply: bool = False) -> TaxonomyProfile:
    normalized = _normalize_source(source)
    if normalized == "gotrangtri":
        from data_pipeline.crawling.taxonomy_profiles.gotrangtri import decide_category

        return TaxonomyProfile(name="gotrangtri", mode="apply" if apply else "dry-run", rules=decide_category)
    return TaxonomyProfile(
        name="global",
        mode="report-only",
        rules=no_decision,
        warning="No source-specific taxonomy profile; report-only mode.",
    )


def infer_dataset_source(dataset_dir: str | Path) -> str | None:
    manifest_path = Path(dataset_dir) / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    source = manifest.get("source") or manifest.get("source_id")
    return str(source).strip() if source else None


def _normalize_source(source: str | None) -> str:
    text = str(source or "").strip().lower().replace("_", "-")
    aliases = {
        "go-trang-tri": "gotrangtri",
        "gotrangtri.vn": "gotrangtri",
        "gotrangtri": "gotrangtri",
    }
    return aliases.get(text, text)
