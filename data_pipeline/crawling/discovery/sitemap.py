from typing import Callable, Optional
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


class SitemapDiscoveryError(RuntimeError):
    """Raised when sitemap discovery cannot parse or fetch a sitemap."""


class SitemapProductUrlDiscoverer:
    """Discover product URLs from sitemap XML without fetching product pages."""

    def __init__(
        self,
        fetcher: Optional[Callable[[str], str]] = None,
        timeout_seconds: float = 10,
        max_sitemaps: int = 20,
    ):
        self.fetcher = fetcher or self._fetch_xml
        self.timeout_seconds = timeout_seconds
        self.max_sitemaps = max_sitemaps

    def discover(
        self,
        sitemap_url: str,
        product_url_patterns: Optional[list[str]] = None,
        max_urls: int = 100,
        allowed_domains: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> list[str]:
        if not sitemap_url or not str(sitemap_url).strip():
            raise SitemapDiscoveryError("sitemap_url is required")
        if max_urls <= 0:
            return []

        seen: set[str] = set()
        discovered: list[str] = []
        self._discover_from_sitemap(
            str(sitemap_url).strip(),
            product_url_patterns or [],
            max_urls,
            seen,
            discovered,
            visited_sitemaps=set(),
            allowed_domains=allowed_domains or [],
            exclude_patterns=exclude_patterns or [],
        )
        return discovered

    def _discover_from_sitemap(
        self,
        sitemap_url: str,
        product_url_patterns: list[str],
        max_urls: int,
        seen: set[str],
        discovered: list[str],
        visited_sitemaps: set[str],
        allowed_domains: list[str],
        exclude_patterns: list[str],
    ):
        if len(discovered) >= max_urls or sitemap_url in visited_sitemaps:
            return
        if len(visited_sitemaps) >= self.max_sitemaps:
            return
        visited_sitemaps.add(sitemap_url)

        root = self._load_root(sitemap_url)
        root_name = _local_name(root.tag)
        if root_name == "urlset":
            for loc in _loc_values(root):
                if len(discovered) >= max_urls:
                    break
                if _is_allowed_url(loc, product_url_patterns, allowed_domains, exclude_patterns) and loc not in seen:
                    seen.add(loc)
                    discovered.append(loc)
            return

        if root_name == "sitemapindex":
            for child_sitemap_url in _loc_values(root):
                if len(discovered) >= max_urls:
                    break
                self._discover_from_sitemap(
                    child_sitemap_url,
                    product_url_patterns,
                    max_urls,
                    seen,
                    discovered,
                    visited_sitemaps,
                    allowed_domains,
                    exclude_patterns,
                )
            return

        raise SitemapDiscoveryError(f"unsupported sitemap root: {root_name}")

    def _load_root(self, sitemap_url: str) -> ElementTree.Element:
        try:
            xml_text = self.fetcher(sitemap_url)
            return ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise SitemapDiscoveryError(f"malformed sitemap XML: {sitemap_url}") from exc
        except SitemapDiscoveryError:
            raise
        except Exception as exc:
            raise SitemapDiscoveryError(f"failed to load sitemap: {sitemap_url}") from exc

    def _fetch_xml(self, sitemap_url: str) -> str:
        request = Request(
            sitemap_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DataPipelineCrawler/1.0)",
                "Accept": "application/xml,text/xml,*/*",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            content_type = response.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type.lower():
                charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
            return response.read().decode(charset or "utf-8", errors="replace")


def _loc_values(root: ElementTree.Element) -> list[str]:
    values: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) == "loc" and element.text:
            value = element.text.strip()
            if value:
                values.append(value)
    return values


def _is_allowed_url(
    url: str,
    include_patterns: list[str],
    allowed_domains: list[str],
    exclude_patterns: list[str],
) -> bool:
    if allowed_domains and not _matches_domain(url, allowed_domains):
        return False
    if any(pattern and pattern in url for pattern in exclude_patterns):
        return False
    return _matches_patterns(url, include_patterns)


def _matches_patterns(url: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    for pattern in patterns:
        if pattern not in url:
            continue
        if pattern.endswith("/") and not url.split(pattern, 1)[1].strip("/"):
            continue
        return True
    return False


def _matches_domain(url: str, allowed_domains: list[str]) -> bool:
    host = urlsplit(url).netloc.lower().split("@").pop().split(":")[0]
    if not host:
        return False
    for raw_domain in allowed_domains:
        domain = urlsplit(raw_domain).netloc if "://" in raw_domain else raw_domain
        domain = domain.lower().split("@").pop().split(":")[0].strip("/")
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
