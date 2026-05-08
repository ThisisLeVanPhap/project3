import re
from typing import Any, Dict, List


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def build_shortlist(hits: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, str]]:
    shortlist: List[Dict[str, str]] = []
    seen_titles = set()

    for hit in hits:
        title = (hit.get("title") or "").strip()
        url = (hit.get("url") or "").strip()
        content = (hit.get("content") or "").strip()
        if not title:
            continue

        normalized_title = title.lower()
        if normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)

        shortlist.append({
            "title": title,
            "url": url,
            "summary": _extract_summary(content),
        })

        if len(shortlist) >= limit:
            break

    return shortlist


def rank_shortlist(shortlist: List[Dict[str, str]], state: Dict[str, Any]) -> List[Dict[str, str]]:
    preferences = [str(item).lower() for item in state.get("preferences", []) if item]
    rejected_attributes = [
        str(item).lower() for item in state.get("rejected_attributes", []) if item
    ]
    category = str(state.get("category") or "").lower()

    scored_items = []
    for index, item in enumerate(shortlist):
        haystack = " ".join([
            item.get("title", ""),
            item.get("summary", ""),
            item.get("url", ""),
        ]).lower()

        score = 0
        if category and category in haystack:
            score += 3

        for preference in preferences:
            if preference and preference in haystack:
                score += 2

        for rejected in rejected_attributes:
            if rejected and rejected in haystack:
                score -= 3

        scored_items.append((score, index, item))

    scored_items.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for _, _, item in scored_items]


def _extract_summary(content: str) -> str:
    if not content:
        return ""

    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(content)
        if sentence and len(sentence.strip()) > 20
    ]
    if sentences:
        return " ".join(sentences[:2]).strip()

    compact = " ".join(content.split())
    return compact[:220].strip()
