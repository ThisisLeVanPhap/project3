import re
import unicodedata
from typing import Any, Dict, List, Optional


def extract_candidate_price_vnd(message: str) -> Optional[float]:
    text = (message or "").lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(trieu|triệu|m|million)", text)
    if match:
        return float(match.group(1)) * 1_000_000

    match = re.search(r"(\d{6,})", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_price_values_from_context(context: str) -> List[float]:
    values: List[float] = []
    for match in re.finditer(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', context or ""):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    return values


def format_vnd_range(min_price: float, max_price: float) -> str:
    min_m = min_price / 1_000_000
    max_m = max_price / 1_000_000
    if min_price == max_price:
        return f"khoảng {min_m:.1f} triệu VND"
    return f"khoảng {min_m:.1f}-{max_m:.1f} triệu VND"


def format_vnd_value(price: float) -> str:
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} triệu VND"
    return f"{price:,.0f} VND"


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def market_price_subject(user_message: str, price_refs: List[Any]) -> str:
    message = user_message or ""
    code_match = re.search(r"\b[A-Z]{2,}[A-Z0-9-]*\d+[A-Z0-9-]*\b", message.upper())
    if code_match:
        return code_match.group(0)

    plain = strip_accents(message).lower()
    if "sofa" in plain and "go soi" in plain:
        return "sofa gỗ sồi"
    if "sofa" in plain:
        return "sofa"
    if "ban an" in plain:
        return "bàn ăn"
    if "tu quan ao" in plain or "tu ao" in plain:
        return "tủ quần áo"
    if "giuong" in plain:
        return "giường"

    return next(
        (
            str(value)
            for ref in price_refs
            for value in (getattr(ref, "product_id", None), getattr(ref, "name", None))
            if value
        ),
        "sản phẩm",
    )


def _fmt_price(val) -> str:
    if val is None:
        return "chua co du lieu"
    try:
        return f"{float(val):,.0f} VND".replace(",", ".")
    except (ValueError, TypeError):
        return str(val)


def _confidence_label(conf: str) -> str:
    return {
        "HIGH": "CAO",
        "MEDIUM": "TRUNG BINH",
        "LOW": "THAP",
        "INSUFFICIENT": "THAP (chua du mau)",
    }.get(conf, conf)


def build_market_price_insight_reply(
    query: str,
    insight: Any,
) -> str:
    """Render market price reply from BackendMarketPriceInsightProvider."""
    if insight is None or insight.stats.get("sampleCount", 0) == 0:
        return (
            "Hien minh chua co du du lieu gia cong khai phu hop voi cau hoi nay. "
            "Ban co the thu neu ro loai san pham, chat lieu hoac khoang gia cu the hon."
        )

    stats = insight.stats
    category = insight.category or "san pham"
    material = insight.material or ""
    material_text = f" chat lieu {material}" if material else ""

    sample_count = stats.get("sampleCount", 0)
    source_count = stats.get("sourceCount", 0)
    confidence = stats.get("confidence", "INSUFFICIENT")

    lines = []
    lines.append(f"Voi nhom {category}{material_text}, du lieu cong khai hien co {sample_count} mau.")
    if source_count == 1:
        lines.append("Luu y: du lieu hien chu yeu tu 1 nguon nen do tin cay o muc "
                      + _confidence_label(confidence) + ".")
    else:
        lines.append(f"Do tin cay: {_confidence_label(confidence)} ({source_count} nguon).")

    lines.append("")
    lines.append("Khoang gia quan sat duoc:")
    lines.append(f"  Thap nhat: {_fmt_price(stats.get('minPrice'))}")
    lines.append(f"  P25:       {_fmt_price(stats.get('p25Price'))}")
    lines.append(f"  Trung vi:  {_fmt_price(stats.get('medianPrice'))}")
    lines.append(f"  P75:       {_fmt_price(stats.get('p75Price'))}")
    lines.append(f"  Cao nhat:  {_fmt_price(stats.get('maxPrice'))}")

    assessment = insight.assessment
    if assessment:
        input_price = assessment.get("inputPrice")
        label = assessment.get("label", "")
        lines.append("")
        lines.append(f"Nhan xet: Gia {_fmt_price(input_price)} {label}.")

    samples = insight.samples
    if samples:
        lines.append("")
        lines.append("Mot so mau tham khao:")
        for s in samples[:3]:
            name = s.get("name", "?")
            price = _fmt_price(s.get("price"))
            src = s.get("sourceName") or s.get("source_code") or ""
            line = f"  - {name}: {price}"
            if src:
                line += f" ({src})"
            lines.append(line)

    lines.append("")
    lines.append("Thong tin gia mang tinh tham khao tai thoi diem thu thap. "
                 "Khong co y kien mua ban cu the.")
    return "\n".join(lines)


def build_market_price_reply(
    user_message: str,
    price_refs: List[Any],
) -> str:
    price_values = [
        float(getattr(ref, "price"))
        for ref in price_refs
        if getattr(ref, "price", None) is not None
    ]
    if not price_values:
        return (
            "Chưa có đủ dữ liệu giá có cấu trúc để ước lượng khoảng giá hoặc phát hiện bất thường. "
            "Bạn có thể gửi thêm tên sản phẩm, mã sản phẩm, vật liệu, kích thước hoặc một mức giá cụ thể "
            "để mình phân tích sát hơn."
        )

    min_price = min(price_values)
    max_price = max(price_values)
    candidate_price = extract_candidate_price_vnd(user_message)
    product_label = market_price_subject(user_message, price_refs)

    if candidate_price is None:
        judgement = (
            "Nếu chưa có mức giá cụ thể để đối chiếu, có thể dùng khoảng này làm mốc tham khảo ban đầu."
        )
    elif candidate_price < min_price:
        judgement = f"Mức {format_vnd_value(candidate_price)} đang thấp hơn khoảng tham chiếu."
    elif candidate_price > max_price:
        judgement = f"Mức {format_vnd_value(candidate_price)} đang cao hơn khoảng tham chiếu."
    else:
        judgement = f"Mức {format_vnd_value(candidate_price)} đang nằm trong khoảng tham chiếu."

    return (
        f"## Tham khảo giá {product_label}\n"
        f"Khoảng giá tham khảo: {format_vnd_range(min_price, max_price)}.\n"
        f"Dữ liệu đối chiếu: {len(price_values)} mẫu tham chiếu hiện có.\n"
        f"Nhận xét: {judgement}\n"
        "Lưu ý: Khoảng giá có thể thay đổi theo kích thước, chất liệu, độ mới, thương hiệu và chi phí vận chuyển/lắp đặt."
    )
