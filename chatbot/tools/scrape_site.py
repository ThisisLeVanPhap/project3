import json
import re
import sys

import requests
from requests.exceptions import SSLError
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean_text(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").replace("\u200b", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_main_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.text if soup.title else "")

    # remove noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Prefer common article/content containers when present.
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
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except SSLError:
        # Some demo/runtime environments do not expose a working CA bundle.
        # Retry once for curator-provided sources so KB rebuilds can still proceed.
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    title, body = extract_main_text(r.text)
    return {"url": url, "title": title, "content": body}


def load_curated_urls(in_urls: str) -> list[str]:
    urls = []
    seen = set()
    with open(in_urls, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in seen:
                seen.add(line)
                urls.append(line)
    return urls


def scrape_curated_urls(shop: str, urls: list[str], out_jsonl: str, fetcher=fetch) -> int:
    written = 0
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for url in urls:
            try:
                doc = fetcher(url)
                doc["shop"] = shop
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                written += 1
                print("[OK]", url)
            except Exception as e:
                print("[FAIL]", url, e)
    return written


def main():
    # usage: python scrape_site.py gotrangtri kb/gotrangtri/raw_urls.txt kb/gotrangtri/docs.jsonl
    # raw_urls.txt is a curated allowlist: one URL per line, optional # comments, no crawling.
    shop = sys.argv[1]
    in_urls = sys.argv[2]
    out_jsonl = sys.argv[3]

    urls = load_curated_urls(in_urls)
    scrape_curated_urls(shop, urls, out_jsonl)


if __name__ == "__main__":
    main()
