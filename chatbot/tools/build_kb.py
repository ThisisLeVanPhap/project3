import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.retrievers.text import repair_mojibake, tokenize


TRAILING_NOISE_MARKERS = (
    "● Ngày cập nhật :",
    "Share link",
    "SẢN PHẨM GỢI Ý & LIÊN QUAN",
    "SẢN PHẨM GỢI Ý",
    "LIÊN QUAN",
    "× HỆ THỐNG THÔNG BÁO",
    "Checkout Chọn kênh chat với Nội Thất CaCo",
    "Đội ngũ thợ lành nghề",
    "THÔNG TIN LIÊN HỆ CÔNG TY TNHH NỘI THẤT CACO",
    "THÔNG TIN LIÊN HỆ",
    "HỖ TRỢ KHÁCH HÀNG",
    "MAP SHOWROOM",
    "Đăng ký tư vấn miễn phí",
    "Cam kết bảo mật thông tin 100%. Hotline:",
    "Hotline",
    "Copyright 2024",
)

LEADING_NOISE_START_MARKERS = (
    "2,054 lượt check in",
    "Việt Nam Việt Nam English",
    "Menu Danh mục",
)

LEADING_BODY_MARKERS = (
    "Nội Thất CaCo là đơn vị",
    "I. QUY ĐỊNH",
    "CHI TIẾT SẢN PHẨM",
    "Chi tiết sản phẩm",
    "Nhà sản xuất:",
    "Tóm tắt sơ lược về sản phẩm",
    "Chính sách đổi trả",
)

INLINE_NOISE_PATTERNS = (
    re.compile(
        r"Checkout Chọn kênh chat với Nội Thất CaCo.*?Cam kết bảo mật thông tin 100%\. Hotline:\s*[\d\.\-\s]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"× HỆ THỐNG THÔNG BÁO.*?(?=THÔNG TIN LIÊN HỆ CÔNG TY TNHH NỘI THẤT CACO|THÔNG TIN LIÊN HỆ|$)",
        re.IGNORECASE,
    ),
)


def normalize_spaces(text: str) -> str:
    text = repair_mojibake(text or "").replace("\u00a0", " ").replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def trim_repeated_title_preamble(text: str, title: str) -> str:
    title = normalize_spaces(title)
    text = normalize_spaces(text)
    if not title or not text:
        return text

    first = text.find(title)
    if first < 0:
        return text

    second = text.find(title, first + len(title))
    if second < 0:
        return text

    if second <= 4000:
        return text[second:].strip()
    return text


def trim_known_leading_noise(text: str, title: str) -> str:
    title = normalize_spaces(title)
    candidates = []
    if title:
        candidates.append(title)
    candidates.extend(LEADING_BODY_MARKERS)

    best = None
    for start_marker in LEADING_NOISE_START_MARKERS:
        start = text.find(start_marker)
        if start < 0 or start > 1500:
            continue

        for end_marker in candidates:
            end = text.find(end_marker, start + len(start_marker))
            if end < 0 or end <= start or end - start > 5000:
                continue

            if best is None or start < best[0] or (start == best[0] and end < best[1]):
                best = (start, end)

    if not best:
        return text

    start, end = best
    return (text[:start] + " " + text[end:]).strip()


def strip_inline_noise(text: str) -> str:
    cleaned = text
    for pattern in INLINE_NOISE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return normalize_spaces(cleaned)


def trim_trailing_noise(text: str) -> str:
    cutoff = len(text)
    for marker in TRAILING_NOISE_MARKERS:
        idx = text.find(marker)
        if idx >= 0 and idx >= 80:
            cutoff = min(cutoff, idx)
    return text[:cutoff].strip()


def clean_doc_content(text: str, title: str) -> str:
    cleaned = normalize_spaces(text)
    cleaned = trim_repeated_title_preamble(cleaned, title)
    cleaned = trim_known_leading_noise(cleaned, title)
    cleaned = strip_inline_noise(cleaned)
    cleaned = trim_trailing_noise(cleaned)
    return normalize_spaces(cleaned)


def chunk_text(text: str, max_words=350, overlap=60):
    words = (text or "").split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + max_words]
        chunks.append(" ".join(chunk))
        i += max_words - overlap
    return chunks


def build_kb(docs_path: str, chunks_path: str, index_path: str) -> int:
    chunks = []
    with open(docs_path, "r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            cleaned_content = clean_doc_content(doc.get("content", ""), doc.get("title", ""))
            for c in chunk_text(cleaned_content):
                if not c.strip():
                    continue
                chunks.append(
                    {
                        "shop": doc.get("shop", ""),
                        "url": doc.get("url", ""),
                        "title": doc.get("title", ""),
                        "content": c,
                    }
                )

    with open(chunks_path, "w", encoding="utf-8") as out:
        for ch in chunks:
            out.write(json.dumps(ch, ensure_ascii=False) + "\n")

    df = Counter()
    for ch in chunks:
        toks = set(tokenize((ch.get("title") or "") + " " + (ch.get("content") or "")))
        for t in toks:
            df[t] += 1

    N = len(chunks)
    idf = {t: 1.0 + math.log((N + 1) / (df[t] + 1)) for t in df}

    data = {
        "N": N,
        "idf": idf,
        "tokenization": {
            "mode": "unicode_with_accent_fold_aliases",
            "preserves_diacritics": True,
            "mixed_query_support": "Vietnamese tokens are indexed in original and accent-folded forms.",
        },
        "cleaning": {
            "mode": "heuristic_boilerplate_trim",
            "notes": [
                "Trim duplicated title/menu preambles before chunking.",
                "Trim leading check-in/language/menu blocks when a nearby body marker is found.",
                "Strip inline chat popup and system-notice boilerplate spans before chunking.",
                "Trim repeated footer/support/chat popup boilerplate markers before chunking.",
                "Trim related-product and consultation call-to-action sections before chunking.",
                "Repair common mojibake text before cleaning and tokenization.",
            ],
        },
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    return N


def main():
    docs_path, chunks_path, index_path = sys.argv[1], sys.argv[2], sys.argv[3]
    total_chunks = build_kb(docs_path, chunks_path, index_path)
    print(f"Built KB: {total_chunks} chunks")


if __name__ == "__main__":
    main()
