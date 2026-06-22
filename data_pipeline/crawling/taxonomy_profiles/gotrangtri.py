import re
from typing import Any
from urllib.parse import urlsplit

from data_pipeline.crawling.taxonomy_profiles.common import TaxonomyDecision

CATEGORY_PRIORITY = (
    "Bàn làm việc",
    "Bàn trà",
    "Sofa",
    "Tủ",
    "Kệ",
    "Giường",
    "Rèm",
    "Ghế",
    "Đèn",
    "Gương",
    "Đồ trang trí",
)


def decide_category(product: dict[str, Any]) -> TaxonomyDecision:
    title = str(product.get("product_name") or product.get("title") or "")
    url = str(product.get("source_url") or product.get("canonical_url") or product.get("url") or "")
    current_category = str(product.get("category") or "").strip()
    title_folded = _fold(title)
    slug = _slug(url)
    matched: dict[str, str] = {}

    if "ghe-sofa" in slug or "sofa" in title_folded or "sofa" in slug:
        matched["Sofa"] = "sofa"
    if "ban-lam-viec" in slug or "ban lam viec" in title_folded:
        matched["Bàn làm việc"] = "ban_lam_viec"
    if _slug_has(slug, "ban-tra") or _slug_has(slug, "ban-sofa") or _phrase(title_folded, "ban tra") or _phrase(title_folded, "ban sofa"):
        matched["Bàn trà"] = "ban_tra"
    if _has_tu(title, slug):
        matched["Tủ"] = "tu"
    if _has_ke(title, slug):
        matched["Kệ"] = "ke"
    if "giuong" in slug or "giuong" in title_folded:
        matched["Giường"] = "giuong"
    if slug.startswith("rem-") or "-rem-" in slug or _word(title_folded, "rem"):
        matched["Rèm"] = "rem"
    if _has_ghe(title, slug):
        matched["Ghế"] = "ghe"
    if slug.startswith("den-") or "-den-" in slug or _word(title_folded, "den"):
        matched["Đèn"] = "den"
    if "guong" in slug or _word(title_folded, "guong"):
        matched["Gương"] = "guong"
    if _has_decor(title_folded, slug) and current_category in ("", "Đồ trang trí"):
        matched["Đồ trang trí"] = "decor"

    if not matched:
        return TaxonomyDecision(None, None, 0.0)
    for category in CATEGORY_PRIORITY:
        if category in matched:
            return TaxonomyDecision(category, matched[category], 0.95)
    return TaxonomyDecision(None, None, 0.0)


def _has_tu(title: str, slug: str) -> bool:
    title_lower = title.lower()
    return (
        "tủ" in title_lower
        or slug.startswith("tu-")
        or "-tu-quan-ao" in slug
        or "-tu-de-do" in slug
        or "-tu-giay" in slug
        or "-tu-bep" in slug
        or "-tu-dau-giuong" in slug
    )


def _has_ke(title: str, slug: str) -> bool:
    title_lower = title.lower()
    return "kệ" in title_lower or slug.startswith("ke-") or "-ke-sach" in slug or "-ke-tivi" in slug or "-ke-trang-tri" in slug or "-ke-de-do" in slug


def _has_ghe(title: str, slug: str) -> bool:
    title_lower = title.lower()
    return re.search(r"\bghế\b", title_lower) is not None or slug.startswith("ghe-") or "-ghe-" in slug


def _has_decor(title_folded: str, slug: str) -> bool:
    return (
        "trang tri" in title_folded
        or "trang-tri" in slug
        or slug.startswith("dong-ho")
        or _word(title_folded, "dong ho")
        or slug.startswith("binh-")
        or slug.startswith("lo-hoa")
    )


def _word(text: str, word: str) -> bool:
    padded = f" {text.replace('-', ' ')} "
    return f" {word} " in padded


def _phrase(text: str, phrase: str) -> bool:
    return _word(text, phrase)


def _slug(url: str) -> str:
    parsed = urlsplit(url)
    return _fold(parsed.path.strip("/").split("/")[-1])


def _slug_has(slug: str, token: str) -> bool:
    return slug == token or slug.startswith(token + "-") or slug.endswith("-" + token) or f"-{token}-" in slug


def _fold(value: str) -> str:
    text = value.lower()
    replacements = {
        "ủ": "u", "ũ": "u", "ụ": "u", "ư": "u", "ứ": "u", "ừ": "u", "ử": "u", "ữ": "u", "ự": "u", "ù": "u", "ú": "u",
        "ô": "o", "ố": "o", "ồ": "o", "ổ": "o", "ỗ": "o", "ộ": "o", "ơ": "o", "ớ": "o", "ờ": "o", "ở": "o", "ỡ": "o", "ợ": "o", "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a", "ă": "a", "ắ": "a", "ằ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a", "â": "a", "ấ": "a", "ầ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e", "ê": "e", "ế": "e", "ề": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i", "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y", "đ": "d",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text
