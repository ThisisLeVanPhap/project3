import json
import tempfile
import unittest
from pathlib import Path

from data_pipeline.crawling.fetcher import (
    FetchConfig,
    HttpFetcher,
    RobotsDisallowedError,
    _safe_filename_stem,
)


class FakeResponse:
    def __init__(self, body: str, status_code: int = 200, url: str = "https://shop.example/p/1", headers=None):
        self._body = body.encode("utf-8")
        self._status_code = status_code
        self._url = url
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.closed = False

    def read(self):
        return self._body

    def getcode(self):
        return self._status_code

    def geturl(self):
        return self._url

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeRobotParser:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def can_fetch(self, user_agent, url):
        return self.allowed


def _test_config(raw_dir=None, max_retries=0, obey_robots_txt=False):
    return FetchConfig(
        timeout_seconds=1,
        min_delay_seconds=0,
        max_delay_seconds=0,
        max_retries=max_retries,
        obey_robots_txt=obey_robots_txt,
        user_agents=["UnitTestBot/1.0"],
        raw_dir=raw_dir,
    )


class HttpFetcherTests(unittest.TestCase):
    def test_fetch_success_returns_raw_page_and_content_hash(self):
        fetcher = HttpFetcher(_test_config())
        fetcher._opener = FakeOpener([FakeResponse("<html>Sofa</html>")])

        raw_page = fetcher.fetch("https://shop.example/p/1")

        self.assertEqual(raw_page.url, "https://shop.example/p/1")
        self.assertEqual(raw_page.final_url, "https://shop.example/p/1")
        self.assertEqual(raw_page.status_code, 200)
        self.assertEqual(raw_page.html, "<html>Sofa</html>")
        self.assertTrue(raw_page.content_hash)
        self.assertIn("Content-Type", raw_page.headers)

    def test_save_snapshot_writes_html_and_metadata(self):
        raw_dir = Path(tempfile.mkdtemp(prefix="crawler-raw-"))
        fetcher = HttpFetcher(_test_config(raw_dir=raw_dir))
        fetcher._opener = FakeOpener([FakeResponse("<html>Sofa</html>")])
        raw_page = fetcher.fetch("https://shop.example/p/1?utm_source=x")

        saved = fetcher.save_snapshot(raw_page)

        self.assertTrue(saved.snapshot_html_path)
        self.assertTrue(saved.snapshot_meta_path)
        html_path = Path(saved.snapshot_html_path)
        meta_path = Path(saved.snapshot_meta_path)
        self.assertTrue(html_path.exists())
        self.assertTrue(meta_path.exists())
        self.assertEqual(html_path.read_text(encoding="utf-8"), "<html>Sofa</html>")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["url"], "https://shop.example/p/1?utm_source=x")
        self.assertEqual(metadata["status_code"], 200)
        self.assertEqual(metadata["content_hash"], saved.content_hash)
        self.assertEqual(metadata["html_path"], str(html_path))

    def test_robots_disallow_does_not_fetch(self):
        fetcher = HttpFetcher(_test_config(obey_robots_txt=True))
        fetcher._opener = FakeOpener([FakeResponse("<html>Should not fetch</html>")])
        fetcher._robot_cache["https://shop.example"] = FakeRobotParser(False)

        with self.assertRaises(RobotsDisallowedError):
            fetcher.fetch("https://shop.example/private/p/1")

        self.assertEqual(fetcher._opener.requests, [])

    def test_retry_503_then_success(self):
        fetcher = HttpFetcher(_test_config(max_retries=1))
        fetcher._backoff = lambda attempt: None
        fetcher._opener = FakeOpener([
            FakeResponse("temporary unavailable", status_code=503),
            FakeResponse("<html>Recovered</html>", status_code=200),
        ])

        raw_page = fetcher.fetch("https://shop.example/p/1")

        self.assertEqual(raw_page.status_code, 200)
        self.assertEqual(raw_page.html, "<html>Recovered</html>")
        self.assertEqual(len(fetcher._opener.requests), 2)

    def test_safe_filename_removes_windows_unsafe_characters(self):
        stem = _safe_filename_stem('https://shop.example/a:b<c>d"e/f\\g|h?i*j', "abcdef1234567890")

        self.assertTrue(stem.endswith("-abcdef123456"))
        self.assertFalse(any(char in stem for char in '<>:"/\\|?*'))


if __name__ == "__main__":
    unittest.main()
