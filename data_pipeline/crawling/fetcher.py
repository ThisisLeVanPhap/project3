import json
import random
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener
from urllib.robotparser import RobotFileParser

from data_pipeline.crawling.normalize import make_content_hash


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
WINDOWS_UNSAFE_FILENAME_CHARS = r'<>:"/\|?*'


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched after controlled retries."""


class RobotsDisallowedError(FetchError):
    """Raised when robots.txt disallows crawling a URL."""


@dataclass
class FetchConfig:
    timeout_seconds: float = 15
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 3.0
    max_retries: int = 3
    obey_robots_txt: bool = True
    user_agents: list[str] = field(default_factory=lambda: list(DEFAULT_USER_AGENTS))
    raw_dir: Optional[Path | str] = Path("data_pipeline/raw/pages")


@dataclass
class RawPage:
    url: str
    final_url: str
    status_code: int
    html: str
    fetched_at: datetime
    content_hash: str
    headers: dict[str, str]
    snapshot_html_path: Optional[str] = None
    snapshot_meta_path: Optional[str] = None


class HttpFetcher:
    """Small urllib-based fetcher with robots check, retries, and raw snapshots."""

    def __init__(self, config: Optional[FetchConfig] = None):
        self.config = config or FetchConfig()
        self._opener = build_opener()
        self._robot_cache: dict[str, Optional[RobotFileParser]] = {}
        self._closed = False

    def fetch(self, url: str) -> RawPage:
        if self._closed:
            raise FetchError("fetcher is closed")
        if not url or not str(url).strip():
            raise FetchError("url is required")

        url = str(url).strip()
        user_agent = random.choice(self.config.user_agents or DEFAULT_USER_AGENTS)
        if self.config.obey_robots_txt and not self._robots_allowed(url, user_agent):
            raise RobotsDisallowedError(f"robots.txt disallows fetching URL: {url}")

        attempts = max(0, self.config.max_retries) + 1
        last_error: Optional[BaseException] = None
        for attempt in range(attempts):
            self._delay()
            try:
                raw_page = self._fetch_once(url, user_agent)
                if raw_page.status_code in RETRYABLE_STATUS_CODES:
                    last_error = FetchError(f"retryable HTTP status {raw_page.status_code} for {url}")
                    self._backoff(attempt)
                    continue
                if raw_page.status_code >= 400:
                    raise FetchError(f"HTTP status {raw_page.status_code} for {url}")
                return raw_page
            except HTTPError as exc:
                status_code = int(exc.code)
                last_error = exc
                if status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                    self._backoff(attempt)
                    continue
                raise FetchError(f"HTTP status {status_code} for {url}") from exc
            except (TimeoutError, URLError, OSError) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self._backoff(attempt)
                    continue
                break

        raise FetchError(f"failed to fetch {url}") from last_error

    def save_snapshot(self, raw_page: RawPage) -> RawPage:
        if not self.config.raw_dir:
            return raw_page

        raw_dir = Path(self.config.raw_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)

        stem = _safe_filename_stem(raw_page.final_url or raw_page.url, raw_page.content_hash)
        html_path = raw_dir / f"{stem}.html"
        meta_path = raw_dir / f"{stem}.meta.json"

        html_path.write_text(raw_page.html, encoding="utf-8")
        metadata = {
            "url": raw_page.url,
            "final_url": raw_page.final_url,
            "status_code": raw_page.status_code,
            "fetched_at": raw_page.fetched_at.isoformat(),
            "content_hash": raw_page.content_hash,
            "headers": raw_page.headers,
            "html_path": str(html_path),
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return replace(
            raw_page,
            snapshot_html_path=str(html_path),
            snapshot_meta_path=str(meta_path),
        )

    def close(self):
        self._closed = True
        close = getattr(self._opener, "close", None)
        if close:
            close()

    def _fetch_once(self, url: str, user_agent: str) -> RawPage:
        request = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"})
        response = self._opener.open(request, timeout=self.config.timeout_seconds)
        try:
            body = response.read()
            headers = _headers_to_dict(getattr(response, "headers", {}))
            html = body.decode(_charset_from_headers(headers), errors="replace")
            final_url = response.geturl() if hasattr(response, "geturl") else url
            status_code = response.getcode() if hasattr(response, "getcode") else 200
            return RawPage(
                url=url,
                final_url=final_url,
                status_code=int(status_code),
                html=html,
                fetched_at=datetime.now(timezone.utc),
                content_hash=make_content_hash(html),
                headers=headers,
            )
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

    def _robots_allowed(self, url: str, user_agent: str) -> bool:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return True

        domain_key = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), "", "", ""))
        parser = self._robot_cache.get(domain_key)
        if domain_key not in self._robot_cache:
            parser = self._load_robot_parser(parts.scheme, parts.netloc, user_agent)
            self._robot_cache[domain_key] = parser
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    def _load_robot_parser(self, scheme: str, netloc: str, user_agent: str) -> Optional[RobotFileParser]:
        robots_url = urlunsplit((scheme, netloc, "/robots.txt", "", ""))
        request = Request(robots_url, headers={"User-Agent": user_agent})
        try:
            response = self._opener.open(request, timeout=min(self.config.timeout_seconds, 5))
            try:
                body = response.read()
            finally:
                close = getattr(response, "close", None)
                if close:
                    close()
        except (HTTPError, URLError, TimeoutError, OSError):
            return None

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        return parser

    def _delay(self):
        min_delay = max(0.0, self.config.min_delay_seconds)
        max_delay = max(min_delay, self.config.max_delay_seconds)
        if max_delay > 0:
            time.sleep(random.uniform(min_delay, max_delay))

    def _backoff(self, attempt: int):
        if attempt < max(0, self.config.max_retries):
            time.sleep(min(2 ** attempt, 8))


def _headers_to_dict(headers: Any) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def _charset_from_headers(headers: dict[str, str]) -> str:
    content_type = ""
    for key, value in headers.items():
        if key.lower() == "content-type":
            content_type = value
            break
    match = re.search(r"charset=([\w.-]+)", content_type, flags=re.IGNORECASE)
    return match.group(1) if match else "utf-8"


def _safe_filename_stem(url: str, content_hash: Optional[str] = None) -> str:
    parts = urlsplit(url)
    base = "_".join(part for part in (parts.netloc, parts.path.strip("/")) if part)
    base = base or "page"
    for char in WINDOWS_UNSAFE_FILENAME_CHARS:
        base = base.replace(char, "_")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")[:80] or "page"
    suffix = (content_hash or make_content_hash(url))[:12]
    return f"{base}-{suffix}"
