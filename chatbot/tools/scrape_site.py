import re, json, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s

def extract_main_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.text if soup.title else "")

    # remove noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # ưu tiên các vùng content phổ biến
    candidates = []
    for sel in ["article", "main", ".entry-content", ".post-content", ".content", "#content"]:
        for node in soup.select(sel):
            txt = clean_text(node.get_text(" "))
            if len(txt) > 500:
                candidates.append(txt)

    if candidates:
        body = max(candidates, key=len)
    else:
        body = clean_text(soup.get_text(" "))

    return title, body

def fetch(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    title, body = extract_main_text(r.text)
    return {"url": url, "title": title, "content": body}

def main():
    # usage: python scrape_site.py gotrangtri kb/gotrangtri/raw_urls.txt kb/gotrangtri/docs.jsonl
    shop = sys.argv[1]
    in_urls = sys.argv[2]
    out_jsonl = sys.argv[3]

    urls = []
    with open(in_urls, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u and not u.startswith("#"):
                urls.append(u)

    with open(out_jsonl, "w", encoding="utf-8") as out:
        for u in urls:
            try:
                doc = fetch(u)
                doc["shop"] = shop
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                print("[OK]", u)
            except Exception as e:
                print("[FAIL]", u, e)

if __name__ == "__main__":
    main()
