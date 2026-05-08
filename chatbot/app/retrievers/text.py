import unicodedata
from typing import List


def repair_mojibake(text: str) -> str:
    value = text or ""
    if not value:
        return value
    if not any(marker in value for marker in ("Ã", "Ä", "á»", "áº", "â", "Â")):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if repaired else value


def fold_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", repair_mojibake(text or ""))
    chars = []
    for ch in normalized:
        if unicodedata.category(ch) == "Mn":
            continue
        if ch == "đ":
            chars.append("d")
        elif ch == "Đ":
            chars.append("D")
        else:
            chars.append(ch)
    return "".join(chars)


def tokenize(text: str) -> List[str]:
    lowered = repair_mojibake(text or "").lower()
    base_tokens: List[str] = []
    current: List[str] = []

    for ch in lowered:
        if ch.isalnum() or ch == "đ":
            current.append(ch)
            continue
        if current:
            base_tokens.append("".join(current))
            current = []

    if current:
        base_tokens.append("".join(current))

    if not base_tokens:
        return []

    tokens: List[str] = []
    for token in base_tokens:
        tokens.append(token)
        folded = fold_accents(token).lower()
        if folded and folded != token:
            tokens.append(folded)
    return tokens
