# SALES_CONSULTATION_FIX_SUMMARY

## Vấn đề ban đầu

Khi người dùng hỏi mơ hồ như "hey, tư vấn t 1 cái ghế đi", chatbot cũ:
1. Không hỏi thông tin chi tiết, vào thẳng listing sản phẩm.
2. Gợi ý sản phẩm sai loại (đèn, vách ngăn khi người dùng hỏi ghế).
3. Ép đủ 3 sản phẩm kể cả khi chỉ có 1 sản phẩm đúng loại.
4. Tiếng Việt không dấu, câu cứng.
5. Similar suggestion không filter category.

## Root cause chính

1. **consultation_stage_for**: chỉ cần product_type/category là trả "suggest" ngay, không cần thêm thông tin.
2. **sales_nlu.py**: `material="go"` match substring "go" trong "gợi ý/goi y" (false positive).
3. **Không filter category sau retrieval**: top-k context chứa sản phẩm từ mọi category.
4. **Similar suggestion**: re-search không filter category.

## Các phase đã sửa

| Phase | Scope | File chính |
|-------|-------|------------|
| 1 | Wording tiếng Việt, English hardcode | product_answer_renderer.py, sales_templates.py, response_guards.py, server.py |
| 2 | consultation_stage_for không suggest sớm | sales_state.py (_has_recommendation_readiness, _has_specific_product_subtype) |
| 2B | Fix false-positive material "go" từ "gợi ý" | sales_nlu.py (word boundary regex) |
| 3 | Câu hỏi discovery tự nhiên hơn, runtime test | sales_response_renderer.py (category-aware questions) |
| 4 | Filter category sau retrieval, không ép top-k | product_filters.py (filter_by_category), server.py |
| 4B | Similar suggestion không bypass filter | server.py (_tenant_sales_requested_cat scope rộng) |
| 4C | Runtime test coverage cho similar + no-padding | test_sales_runtime_integration.py |

## File/hàm chính đã sửa

| File | Hàm | Thay đổi |
|------|-----|----------|
| `sales_state.py` | `consultation_stage_for` | Dùng `_has_recommendation_readiness` thay vì check category đơn thuần |
| `sales_state.py` | `_has_recommendation_readiness` | Mới: product + ít nhất 1 constraint (budget/room/material...) mới suggest |
| `sales_state.py` | `_has_specific_product_subtype` | Mới: phân biệt "ghế" (bare) vs "ghế văn phòng" (subtype) |
| `sales_nlu.py` | `_extract_entities` | material patterns dùng `re.search(r"\bgo\b")` thay vì `"go" in text` |
| `product_filters.py` | `filter_by_category` | Mới: filter retrieval hits theo category/title |
| `product_answer_renderer.py` | `_reason_line`, `render_listing_answer` | Wording tiếng Việt |
| `sales_response_renderer.py` | `render_sales_response("ask_discovery")` | Category-aware discovery questions |
| `server.py` | (sau search_hits) | Thêm filter call + _tenant_sales_requested_cat cho main + similar path |
| `sales_templates.py` | Tất cả render functions | Wording tiếng Việt |
| `response_guards.py` | Guard fallback strings | Wording tiếng Việt |

## Các test quan trọng

| File | Test | Mục đích |
|------|------|----------|
| `test_sales_state.py` | `RecommendationReadinessTests` (7 tests) | Bare category → discover, có constraint → suggest |
| `test_sales_state.py` | `MaterialFalsePositiveFixTests` (5 tests) | "gợi ý sofa đi" không ra material |
| `test_sales_state.py` | `CategoryAwareDiscoveryQuestionTests` (5 tests) | Câu hỏi discovery đúng category |
| `test_sales_state.py` | `ConsultationStageForIntegrationTests` (5 tests) | Integration stage machine |
| `test_product_filters.py` | `filter_by_category` tests (4 tests) | Filter đúng, không pad |
| `test_sales_runtime_integration.py` | test_vague_ghe/sofa_query (2 tests) | Runtime không listing cho câu mơ hồ |
| `test_sales_runtime_integration.py` | test_tenant_sales_filters_products (1 test) | Mixed KB → output chỉ đúng category |
| `test_sales_runtime_integration.py` | test_main_listing_one_match/zero_match (2 tests) | Không pad, no-result đúng |
| `test_sales_runtime_integration.py` | test_similar_suggestion_* (2 tests) | Similar suggestion filter category |
| `test_product_answer_renderer.py` | test_listing_answer_has_diacritic_cta (1 test) | Wording có dấu |
| `test_server_tenant_sales_wording.py` | test_close_cta, test_similar_suggestion (2 tests) | Server wording |

## Kịch bản test thủ công

### 1. "hey, tư vấn t 1 cái ghế đi"
- **Kỳ vọng**: Stage=discover, action=ask_discovery.
- **Output**: Hỏi mục đích (ghế làm việc/ăn/thư giãn/trang trí) + ngân sách + chất liệu.
- **Không có**: Listing sản phẩm, link nguồn, [P1].

### 2. "gợi ý sofa đi"
- **Kỳ vọng**: Stage=discover, action=ask_discovery.
- **Output**: Hỏi không gian/diện tích + ngân sách + chất liệu/màu sắc.
- **Không có**: Listing sản phẩm, material false-positive từ "gợi ý".

### 3. "tư vấn ghế văn phòng dưới 3 triệu"
- **Kỳ vọng**: Stage=suggest.
- **Output**: Chỉ ghế văn phòng, không đèn/vách ngăn/sofa.
- **Không có**: Sản phẩm sai loại.

### 4. Retrieval chỉ có 1 ghế đúng loại
- **Kỳ vọng**: Output chỉ có 1 sản phẩm ghế.
- **Không có**: Pad thêm đèn/vách ngăn để đủ 3.

### 5. Retrieval không có ghế đúng loại
- **Kỳ vọng**: Output "Mình chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có."
- **Không có**: Listing đèn/vách ngăn sai loại.

### 6. Similar suggestion
- **Kỳ vọng**: Gợi ý sản phẩm cùng category.
- **Không có**: Sản phẩm sai loại trong danh sách gợi ý.

## Residual notes

1. **filter_by_category substring match**: `"Ghế"` match cả `"Ghế văn phòng"`, `"Bộ bàn ghế"`, v.v. Rủi ro: "Bộ bàn ghế" có category metadata là "Bộ" có thể match "Ghế" nếu trong tên sản phẩm có "ghế". Chấp nhận tạm vì combo liên quan.

2. **product_subtype**: "ghế văn phòng" (2 words) được coi là subtype → suggest. Nếu chỉ "ghế" (1 word, bare) → discover. Chưa tách hoàn hảo nếu không có budget/context kèm theo.

3. **Stage machine lệch**: Có 2 stage machine song song: `sales_state.current_stage` và `ConversationState.stage` (legacy). Phase 2/3 sửa sales_state. Legacy stage chưa được đồng bộ. Hiện tại chưa gây lỗi rõ ràng nhưng cần ghi nhận.

4. **Discovery question giới hạn**: Sau 2 lần hỏi (discovery_question_count=MAX_DISCOVERY_QUESTION_TURNS=2) mà vẫn thiếu thông tin, bot tự động chuyển sang listing dù chưa đủ. Đây là behavior cũ, Phase 3 chưa xử lý.

5. **Runtime test hiệu suất**: test_sales_runtime_integration.py mất ~2 phút chạy do stub generator và FastAPI overhead. Cần optimize sau này.
