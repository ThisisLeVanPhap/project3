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
        max_sitemaps: int = 50,
    ):
        self.fetcher = fetcher or self._fetch_xml
        self.timeout_seconds = timeout_seconds
        self.max_sitemaps = max_sitemaps

    def discover(
        self,
        sitemap_url: str,
        product_url_patterns: Optional[list[str]] = None,
        max_urls: int = 1000,
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
        xml_text = None
        try:
            xml_text = self.fetcher(sitemap_url)
            # Strip processing instructions and namespace prefixes that cause ParseError
            import re as _re
            cleaned = _re.sub(r'<\?[^>]+\?>', '', xml_text)  # <?xml-stylesheet ...?>
            cleaned = _re.sub(r'\s+xmlns:\w+="[^"]*"', '', cleaned)  # xmlns:image=...
            cleaned = _re.sub(r'\s+\w+:[^=]+="[^"]*"', '', cleaned)  # xsi:schemaLocation=...
            cleaned = _re.sub(r'</?\w+:[^>]*>', '', cleaned)  # <image:image>...
            root = ElementTree.fromstring(cleaned.encode('utf-8') if isinstance(cleaned, str) else cleaned)
            root_name = _local_name(root.tag)
            # Some servers (e.g. YoastSEO) return HTML instead of XML.
            # If parsed root is <html> or <body>, treat it as a wrapper and retry.
            if root_name == "html" or root_name == "body":
                return self._retry_with_googlebot(sitemap_url, xml_text)
            return root
        except ElementTree.ParseError:
            if xml_text and self._is_html_wrapper(xml_text):
                return self._retry_with_googlebot(sitemap_url, xml_text)
            raise SitemapDiscoveryError(f"malformed sitemap XML: {sitemap_url}")
        except SitemapDiscoveryError:
            raise
        except Exception as exc:
            raise SitemapDiscoveryError(f"failed to load sitemap: {sitemap_url}") from exc

    def _retry_with_googlebot(self, sitemap_url: str, failed_text: str) -> ElementTree.Element:
        """Retry fetching sitemap with Googlebot UA."""
        if self.fetcher is not None and self.fetcher is not self._fetch_xml:
            retry_text = self.fetcher(sitemap_url)
        else:
            retry_text = self._fetch_with_ua(
                sitemap_url,
                "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            )
        try:
            retry_root = ElementTree.fromstring(retry_text)
            retry_name = _local_name(retry_root.tag)
            if retry_name == "html" or retry_name == "body":
                preview = failed_text[:200].replace("\n", " ").strip()
                raise SitemapDiscoveryError(
                    f"malformed sitemap XML (retried with Googlebot): {sitemap_url}: {preview}"
                )
            return retry_root
        except ElementTree.ParseError:
            preview = failed_text[:200].replace("\n", " ").strip()
            raise SitemapDiscoveryError(
                f"malformed sitemap XML (retried with Googlebot): {sitemap_url}: {preview}"
            )

    def _is_html_wrapper(self, text: str) -> bool:
        """Check if text is an HTML wrapper (e.g. YoastSEO) instead of raw XML."""
        if not text:
            return False
        head = text[:500].strip().lower()
        if "<!doctype html" in head or "<html" in head:
            return True
        return "generated by yoastseo" in head or "xml sitemap" in head

    def _fetch_xml(self, sitemap_url: str) -> str:
        return self._fetch_with_ua(
            sitemap_url,
            "Mozilla/5.0 (compatible; DataPipelineCrawler/1.0)",
        )

    def _fetch_with_ua(self, sitemap_url: str, user_agent: str) -> str:
        request = Request(
            sitemap_url,
            headers={
                "User-Agent": user_agent,
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
