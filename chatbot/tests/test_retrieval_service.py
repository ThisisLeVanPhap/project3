import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from requests.exceptions import SSLError

from app.retrieval_service import (
    format_context,
    load_kb,
    normalize_hits,
    search_hits,
    should_allow_retrieval,
    summarize_retrieval_debug,
    top_similar_items,
)
from app.retrievers import BaseRetriever, BaselineRetriever, RetrievalResult
from tools.build_kb import build_kb
from tools.scrape_site import fetch, load_curated_urls, scrape_curated_urls


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class RetrievalServiceTests(unittest.TestCase):
    def test_fetch_retries_without_tls_verification_on_ssl_error(self):
        response = Mock()
        response.text = (
            "<html><head><title>Example Domain</title></head>"
            "<body><main>This domain is for use in illustrative examples in documents.</main></body></html>"
        )
        response.apparent_encoding = "utf-8"
        response.encoding = None
        response.raise_for_status = Mock()

        with patch("tools.scrape_site.requests.get", side_effect=[SSLError("cert"), response]) as mocked_get:
            doc = fetch("https://example.com/")

        self.assertEqual(doc["title"], "Example Domain")
        self.assertIn("illustrative examples in documents", doc["content"])
        self.assertEqual(mocked_get.call_count, 2)
        self.assertNotIn("verify", mocked_get.call_args_list[0].kwargs)
        self.assertFalse(mocked_get.call_args_list[1].kwargs["verify"])

    def test_curated_vietnamese_url_list_builds_searchable_policy_and_product_kb(self):
        tmp_path = TEST_TMP_ROOT / f"kb-curated-{uuid4().hex}"
        raw_urls = tmp_path / "raw_urls.txt"
        docs = tmp_path / "docs.jsonl"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        raw_urls.parent.mkdir(parents=True, exist_ok=True)
        raw_urls.write_text(
            "\n".join([
                "# curated allowlist only",
                "https://noi-that.example/sofa-go-soi",
                "https://noi-that.example/danh-muc/sofa-phong-khach",
                "https://noi-that.example/chinh-sach/giao-hang",
                "https://noi-that.example/chinh-sach/thanh-toan",
                "https://noi-that.example/chinh-sach/doi-tra",
                "https://noi-that.example/sofa-go-soi",
            ]),
            encoding="utf-8",
        )

        fake_docs = {
            "https://noi-that.example/sofa-go-soi": {
                "url": "https://noi-that.example/sofa-go-soi",
                "title": "Sofa gỗ sồi hiện đại",
                "content": "Sofa gỗ sồi hiện đại cho phòng khách nhỏ, phù hợp căn hộ và dễ vệ sinh.",
            },
            "https://noi-that.example/danh-muc/sofa-phong-khach": {
                "url": "https://noi-that.example/danh-muc/sofa-phong-khach",
                "title": "Danh mục sofa phòng khách",
                "content": "Danh mục sofa phòng khách gồm sofa văng, sofa góc và mẫu cho căn hộ nhỏ.",
            },
            "https://noi-that.example/chinh-sach/giao-hang": {
                "url": "https://noi-that.example/chinh-sach/giao-hang",
                "title": "Chính sách giao hàng",
                "content": "Chính sách giao hàng mô tả khu vực áp dụng, thời gian dự kiến và cách liên hệ khi cần hỗ trợ.",
            },
            "https://noi-that.example/chinh-sach/thanh-toan": {
                "url": "https://noi-that.example/chinh-sach/thanh-toan",
                "title": "Chính sách thanh toán",
                "content": "Chính sách thanh toán hỗ trợ chuyển khoản, tiền mặt và xác nhận đơn trước khi giao.",
            },
            "https://noi-that.example/chinh-sach/doi-tra": {
                "url": "https://noi-that.example/chinh-sach/doi-tra",
                "title": "Chính sách đổi trả",
                "content": "Chính sách đổi trả áp dụng khi sản phẩm còn nguyên trạng và được yêu cầu trong thời hạn quy định.",
            },
        }

        def fake_fetch(url: str) -> dict:
            return fake_docs[url]

        urls = load_curated_urls(str(raw_urls))
        self.assertEqual(len(urls), 5)

        scraped = scrape_curated_urls("tenant-vi", urls, str(docs), fetcher=fake_fetch)
        self.assertEqual(scraped, 5)

        build_kb(str(docs), str(chunks), str(index))
        kb = load_kb(str(tmp_path))

        product_hits = search_hits(kb, "sofa go soi cho phong khach", k=2, tenant_id="tenant-vi")
        delivery_hits = search_hits(kb, "chinh sach giao hang", k=2, tenant_id="tenant-vi")
        payment_hits = search_hits(kb, "thanh toan chuyen khoan", k=2, tenant_id="tenant-vi")
        return_hits = search_hits(kb, "doi tra san pham", k=2, tenant_id="tenant-vi")

        self.assertEqual(product_hits[0].title, "Sofa gỗ sồi hiện đại")
        self.assertEqual(delivery_hits[0].title, "Chính sách giao hàng")
        self.assertEqual(payment_hits[0].title, "Chính sách thanh toán")
        self.assertEqual(return_hits[0].title, "Chính sách đổi trả")

    def test_vietnamese_kb_retrieves_expected_chunk(self):
        tmp_path = TEST_TMP_ROOT / f"kb-vi-{uuid4().hex}"
        docs = tmp_path / "docs.jsonl"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(docs, [
            {
                "shop": "tenant-vi",
                "url": "kb://sofa-go-soi",
                "title": "Sofa go soi cho can ho nho",
                "content": "Sofa gỗ sồi hiện đại phù hợp căn hộ nhỏ, dễ vệ sinh và hợp với gia đình có trẻ em.",
            },
            {
                "shop": "tenant-vi",
                "url": "kb://doi-tra",
                "title": "Chinh sach doi tra",
                "content": "Chính sách đổi trả áp dụng trong 7 ngày nếu sản phẩm còn nguyên trạng.",
            },
        ])

        build_kb(str(docs), str(chunks), str(index))

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "sofa go soi cho can ho nho", k=2, tenant_id="tenant-vi")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].title, "Sofa go soi cho can ho nho")
        self.assertIn("căn hộ nhỏ", hits[0].text)

    def test_mixed_vietnamese_english_query_remains_searchable(self):
        tmp_path = TEST_TMP_ROOT / f"kb-mix-{uuid4().hex}"
        docs = tmp_path / "docs.jsonl"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(docs, [
            {
                "shop": "tenant-vi",
                "url": "kb://sofa-pet",
                "title": "Modern sofa for pet-friendly apartment",
                "content": "Sofa hiện đại chống bám lông thú cưng, hợp apartment nhỏ và dễ lau chùi.",
            },
        ])

        build_kb(str(docs), str(chunks), str(index))

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "modern sofa cho can ho co thu cung", k=2, tenant_id="tenant-vi")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].source, "kb://sofa-pet")

    def test_search_hits_returns_normalized_ranked_results(self):
        tmp_path = TEST_TMP_ROOT / f"kb-{uuid4().hex}"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(chunks, [
            {"id": "1", "title": "Modern Sofa", "content": "modern sofa for small apartment", "url": "kb://1"},
            {"id": "2", "title": "Dining Table", "content": "wooden dining table", "url": "kb://2"},
        ])
        index.write_text(
            json.dumps({"idf": {"modern": 2.0, "sofa": 2.0, "small": 1.5, "apartment": 1.5}}),
            encoding="utf-8",
        )

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "modern sofa", k=2, tenant_id="tenant-a")

        self.assertIsInstance(kb, BaseRetriever)
        self.assertIsInstance(kb, BaselineRetriever)
        self.assertEqual(len(hits), 1)
        self.assertIsInstance(hits[0], RetrievalResult)
        self.assertEqual(hits[0].title, "Modern Sofa")
        self.assertEqual(hits[0].tenant_id, "tenant-a")
        self.assertEqual(hits[0].text, "modern sofa for small apartment")
        self.assertEqual(hits[0].doc_id, "1")
        self.assertEqual(hits[0].chunk_id, "1")
        self.assertEqual(hits[0].source, "kb://1")
        self.assertGreater(hits[0].score, 0.0)
        self.assertEqual(hits[0].metadata, {"url": "kb://1"})

    def test_search_hits_handles_empty_results(self):
        tmp_path = TEST_TMP_ROOT / f"kb-{uuid4().hex}"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(chunks, [
            {"id": "1", "title": "Modern Sofa", "content": "modern sofa for small apartment", "url": "kb://1"},
        ])
        index.write_text(json.dumps({"idf": {"modern": 2.0, "sofa": 2.0}}), encoding="utf-8")

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "warranty", k=2, tenant_id="tenant-a")

        self.assertEqual(hits, [])
        self.assertEqual(format_context(hits), "")
        self.assertEqual(top_similar_items(hits), [])

    def test_build_kb_trims_product_footer_and_support_boilerplate(self):
        tmp_path = TEST_TMP_ROOT / f"kb-clean-product-{uuid4().hex}"
        docs = tmp_path / "docs.jsonl"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(docs, [
            {
                "shop": "tenant-vi",
                "url": "kb://product",
                "title": "Bo Sofa Go Soi SFG041",
                "content": (
                    "Bo Sofa Go Soi SFG041 2054 luot check in Menu Danh muc "
                    "Bo Sofa Go Soi SFG041 Chi tiet san pham go soi tu nhien, de ve sinh va hop can ho nho. "
                    "San pham bao hanh 2 nam. SẢN PHẨM GỢI Ý & LIÊN QUAN Mau khac. "
                    "Đội ngũ thợ lành nghề Ho tro khach hang 24/7. Đăng ký tư vấn miễn phí."
                ),
            }
        ])

        build_kb(str(docs), str(chunks), str(index))
        built_chunks = [json.loads(line) for line in chunks.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(built_chunks), 1)
        self.assertIn("Chi tiet san pham go soi tu nhien", built_chunks[0]["content"])
        self.assertNotIn("SẢN PHẨM GỢI Ý & LIÊN QUAN", built_chunks[0]["content"])
        self.assertNotIn("Đăng ký tư vấn miễn phí", built_chunks[0]["content"])

    def test_build_kb_keeps_policy_body_while_trimming_policy_page_boilerplate(self):
        tmp_path = TEST_TMP_ROOT / f"kb-clean-policy-{uuid4().hex}"
        docs = tmp_path / "docs.jsonl"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(docs, [
            {
                "shop": "tenant-vi",
                "url": "kb://policy",
                "title": "Chinh sach doi tra hang",
                "content": (
                    "Chinh sach doi tra hang Menu Danh muc Home Pages "
                    "Chinh sach doi tra hang Chính sách đổi trả và kiểm hàng. "
                    "Thời hạn hiệu lực cho việc đổi, trả hàng là 30 ngày. "
                    "THÔNG TIN LIÊN HỆ CÔNG TY TNHH NỘI THẤT CACO Hotline 0987.822.944 "
                    "HỔ TRỢ KHÁCH HÀNG Đổi trả - bảo hành."
                ),
            }
        ])

        build_kb(str(docs), str(chunks), str(index))
        built_chunks = [json.loads(line) for line in chunks.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(built_chunks), 1)
        self.assertIn("Thời hạn hiệu lực cho việc đổi, trả hàng là 30 ngày", built_chunks[0]["content"])
        self.assertNotIn("THÔNG TIN LIÊN HỆ", built_chunks[0]["content"])
        self.assertNotIn("HỔ TRỢ KHÁCH HÀNG", built_chunks[0]["content"])

    def test_policy_query_prefers_policy_page_over_product_footer_noise(self):
        tmp_path = TEST_TMP_ROOT / f"kb-policy-noise-{uuid4().hex}"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(chunks, [
            {
                "id": "policy",
                "title": "Chinh sach doi tra hang",
                "content": "Chinh sach doi tra ap dung trong 30 ngay neu san pham con nguyen trang va co hoa don hop le.",
                "url": "https://noi-that.example/page/chinh-sach-doi-tra",
            },
            {
                "id": "product",
                "title": "Sofa phong khach cao cap",
                "content": (
                    "Sofa phong khach hien dai cho can ho. "
                    "Ho tro khach hang. Doi tra - bao hanh. Hinh thuc thanh toan. "
                    "Van chuyen - giao nhan. Map showroom. Dang ky tu van mien phi."
                ),
                "url": "https://noi-that.example/collections/sofa-phong-khach",
            },
        ])
        index.write_text(
            json.dumps(
                {
                    "idf": {
                        "chinh": 2.0,
                        "sach": 2.0,
                        "doi": 2.0,
                        "tra": 2.0,
                        "hang": 1.0,
                        "san": 0.8,
                        "pham": 0.8,
                        "sofa": 1.5,
                    }
                }
            ),
            encoding="utf-8",
        )

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "chinh sach doi tra san pham", k=2, tenant_id="tenant-a")

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].doc_id, "policy")

    def test_sofa_query_prefers_product_page_over_policy_page_with_menu_text(self):
        tmp_path = TEST_TMP_ROOT / f"kb-sofa-boost-{uuid4().hex}"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(chunks, [
            {
                "id": "policy",
                "title": "Chinh sach giao hang",
                "content": (
                    "Chinh sach giao hang. Noi dung menu co sofa phong khach bo ban ghe sofa "
                    "va nhieu danh muc khac."
                ),
                "url": "https://noi-that.example/page/chinh-sach-giao-hang",
            },
            {
                "id": "product",
                "title": "Bo ban ghe sofa cho can ho nho",
                "content": "Bo ban ghe sofa nho gon cho phong khach nho, de ve sinh va toi uu dien tich can ho.",
                "url": "https://noi-that.example/collections/bo-ban-ghe-sofa",
            },
        ])
        index.write_text(
            json.dumps(
                {
                    "idf": {
                        "sofa": 2.0,
                        "can": 1.2,
                        "ho": 1.2,
                        "nho": 1.5,
                        "gon": 1.3,
                        "phong": 1.0,
                        "khach": 1.0,
                        "giao": 1.0,
                        "hang": 1.0,
                    }
                }
            ),
            encoding="utf-8",
        )

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "toi can sofa nho gon cho can ho nho", k=2, tenant_id="tenant-a")

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].doc_id, "product")

    def test_shorter_specific_chunk_outranks_long_generic_chunk(self):
        tmp_path = TEST_TMP_ROOT / f"kb-length-{uuid4().hex}"
        chunks = tmp_path / "chunks.jsonl"
        index = tmp_path / "index.json"

        _write_jsonl(chunks, [
            {
                "id": "generic",
                "title": "Sofa phong khach",
                "content": ("sofa phong khach " * 90).strip(),
                "url": "https://noi-that.example/collections/sofa-phong-khach",
            },
            {
                "id": "specific",
                "title": "Sofa phong khach nho gon",
                "content": "Sofa phong khach nho gon cho can ho nho va de ve sinh.",
                "url": "https://noi-that.example/products/sofa-nho-gon",
            },
        ])
        index.write_text(
            json.dumps(
                {
                    "idf": {
                        "sofa": 2.0,
                        "phong": 1.0,
                        "khach": 1.0,
                        "nho": 1.5,
                        "gon": 1.5,
                        "can": 1.2,
                        "ho": 1.2,
                    }
                }
            ),
            encoding="utf-8",
        )

        kb = load_kb(str(tmp_path))
        hits = search_hits(kb, "sofa phong khach nho gon", k=2, tenant_id="tenant-a")

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].doc_id, "specific")

    def test_normalize_hits_keeps_legacy_raw_hit_support_inside_retrieval_service(self):
        hits = normalize_hits(
            [
                {
                    "id": "legacy-1",
                    "title": "Legacy Sofa",
                    "content": "legacy normalized content",
                    "url": "kb://legacy-1",
                    "score": 3.5,
                }
            ],
            tenant_id="tenant-a",
        )

        self.assertEqual(len(hits), 1)
        self.assertIsInstance(hits[0], RetrievalResult)
        self.assertEqual(hits[0].doc_id, "legacy-1")
        self.assertEqual(hits[0].chunk_id, "legacy-1")
        self.assertEqual(hits[0].tenant_id, "tenant-a")
        self.assertEqual(format_context(hits), "- Legacy Sofa (kb://legacy-1): legacy normalized content")
        self.assertEqual(top_similar_items(hits), [("Legacy Sofa", "kb://legacy-1")])

    def test_should_allow_retrieval_preserves_early_discovery_gate(self):
        self.assertFalse(should_allow_retrieval("Hi, I need a sofa", "discover", {}))
        self.assertTrue(
            should_allow_retrieval(
                "Modern style and budget under $800",
                "discover",
                {"style": "modern", "budget_usd": 800},
            )
        )
        self.assertTrue(
            should_allow_retrieval(
                "Toi can sofa go cho can ho nho",
                "discover",
                {"space": "small", "style": "modern"},
            )
        )

    def test_should_allow_retrieval_for_policy_and_material_queries_in_discovery(self):
        self.assertTrue(should_allow_retrieval("Chinh sach thanh toan nhu the nao?", "discover", {}))
        self.assertTrue(should_allow_retrieval("Sofa vai hay sofa da de ve sinh hon?", "discover", {}))

    def test_load_kb_returns_none_without_directory(self):
        self.assertIsNone(load_kb(None))

    def test_summarize_retrieval_debug_returns_lightweight_summary(self):
        hits = normalize_hits(
            [
                {
                    "id": "legacy-1",
                    "title": "Legacy Sofa",
                    "content": "legacy normalized content",
                    "url": "kb://legacy-1",
                    "score": 3.56789,
                },
                {
                    "id": "legacy-2",
                    "title": "Legacy Chair",
                    "content": "chair content",
                    "url": "kb://legacy-2",
                    "score": 1.23456,
                },
            ]
        )

        summary = summarize_retrieval_debug(hits, format_context(hits))

        self.assertEqual(summary["retrieved_docs"], 2)
        self.assertEqual(summary["top_scores"], [3.5679, 1.2346])
        self.assertEqual(len(summary["selected_context_snippets"]), 2)
        self.assertGreater(summary["context_chars"], 0)


if __name__ == "__main__":
    unittest.main()
