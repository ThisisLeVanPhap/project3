import json, re
from collections import Counter

def tokenize(s: str):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.split()

class SimpleKb:
    def __init__(self, chunks_jsonl: str, index_json: str):
        self.chunks = []
        with open(chunks_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                self.chunks.append(json.loads(line))
        with open(index_json, "r", encoding="utf-8") as f:
            self.index = json.load(f)

    def search(self, query: str, k: int = 4):
        q = Counter(tokenize(query))
        idf = self.index["idf"]
        scored = []
        for ch in self.chunks:
            toks = tokenize((ch.get("title") or "") + " " + (ch.get("content") or ""))
            tf = Counter(toks)
            score = 0.0
            for t, qt in q.items():
                if t in tf:
                    score += (tf[t] * qt) * idf.get(t, 0.0)
            if score > 0:
                scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]
