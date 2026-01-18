import json, re, math, sys
from collections import Counter

def chunk_text(text: str, max_words=350, overlap=60):
    words = (text or "").split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_words]
        chunks.append(" ".join(chunk))
        i += max_words - overlap
    return chunks

def tokenize(s: str):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.split()

def main():
    # usage: python build_kb.py kb/shop/docs.jsonl kb/shop/chunks.jsonl kb/shop/index.json
    docs_path, chunks_path, index_path = sys.argv[1], sys.argv[2], sys.argv[3]

    chunks = []
    with open(docs_path, "r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            for c in chunk_text(doc.get("content", "")):
                chunks.append({
                    "shop": doc.get("shop", ""),
                    "url": doc.get("url", ""),
                    "title": doc.get("title", ""),
                    "content": c
                })

    with open(chunks_path, "w", encoding="utf-8") as out:
        for ch in chunks:
            out.write(json.dumps(ch, ensure_ascii=False) + "\n")

    # build IDF (lightweight)
    df = Counter()
    for ch in chunks:
        toks = set(tokenize((ch.get("title") or "") + " " + (ch.get("content") or "")))
        for t in toks:
            df[t] += 1

    N = len(chunks)
    idf = {t: math.log((N + 1) / (df[t] + 1)) for t in df}

    data = {"N": N, "idf": idf}
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Built KB: {N} chunks")

if __name__ == "__main__":
    main()
