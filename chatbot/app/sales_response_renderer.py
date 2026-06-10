from typing import Any, Dict, List


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _product_label(product: Dict[str, Any]) -> str:
    name = _clean(product.get("product_name")) or "Sản phẩm đã chọn"
    pid = _clean(product.get("pid"))
    return f"{name} [{pid}]" if pid else name


def _product_lines(products: List[Dict[str, Any]]) -> List[str]:
    if not products:
        return []
    product = products[0]
    lines = [f"- {_product_label(product)}"]
    price = _clean(product.get("price"))
    source_url = _clean(product.get("source_url"))
    if price:
        lines.append(f"- Giá tham khảo: {price}")
    if source_url:
        lines.append(f"- Link nguồn: {source_url}")
    return lines


def render_sales_response(action: str, draft: Dict[str, Any] | None, state: Any) -> str:
    products = list(getattr(state, "selected_products", []) or [])
    draft = draft or getattr(state, "purchase_request", None) or {}

    if action == "cancelled":
        return (
            "Mình đã hủy yêu cầu mua hàng nháp trong cuộc trò chuyện này. "
            "Bạn có thể tiếp tục xem sản phẩm khác nếu muốn."
        )

    if action == "confirmation_cancelled":
        return (
            "Mình đã hủy yêu cầu mua hàng nháp. "
            "Yêu cầu này chưa được gửi cho cửa hàng."
        )

    if action == "handoff_sent":
        handoff_id = _clean(getattr(state, "handoff_id", "")) or _clean(draft.get("handoff_id")) or "chưa có"
        return (
            "Mình đã gửi yêu cầu mua hàng cho cửa hàng.\n"
            "Cửa hàng sẽ liên hệ lại để xác nhận giá, tồn kho và vận chuyển trước khi chốt đơn.\n"
            f"Mã yêu cầu: {handoff_id}"
        )

    if action == "handoff_already_sent":
        handoff_id = _clean(getattr(state, "handoff_id", "")) or "chưa có"
        return (
            "Yêu cầu mua hàng này đã được gửi cho cửa hàng trước đó.\n"
            f"Mã yêu cầu: {handoff_id}"
        )

    if action == "confirmation_without_pending":
        return (
            "Mình chưa thấy yêu cầu mua hàng đang chờ xác nhận. "
            "Bạn vui lòng chọn lại sản phẩm hoặc gửi lại yêu cầu."
        )

    if action == "handoff_failed":
        return (
            "Mình chưa gửi được yêu cầu cho cửa hàng do lỗi hệ thống. "
            "Bạn có thể thử lại hoặc để lại lời nhắn để cửa hàng liên hệ sau."
        )

    if action == "handoff":
        return (
            "Mình đã ghi nhận yêu cầu gặp tư vấn viên. "
            "Bạn cho mình xin số điện thoại hoặc email để cửa hàng liên hệ lại nhé."
        )

    if action == "ask_product":
        return (
            "Bạn muốn đặt sản phẩm nào trong các mẫu mình vừa gợi ý? "
            "Bạn có thể nói \"P1\", \"mẫu thứ 2\" hoặc gửi tên sản phẩm."
        )

    if action == "ask_contact":
        lines = [
            "Mình đã ghi nhận bạn quan tâm sản phẩm:",
            *_product_lines(products),
            "",
            "Để cửa hàng liên hệ xác nhận giá, tồn kho và vận chuyển, "
            "bạn cho mình xin số điện thoại hoặc email nhé.",
        ]
        return "\n".join(line for line in lines if line is not None)

    if action in {"draft_created", "ask_confirmation"}:
        draft_products = draft.get("products") or []
        product = draft_products[0] if draft_products else {}
        contact = draft.get("contact") or {}
        contact_text = contact.get("phone") or contact.get("email") or "Chưa có"
        location_text = draft.get("address") or draft.get("location") or "Chưa có"
        lines = [
            "Mình đã tạo yêu cầu mua hàng nháp:",
            "",
            f"- Sản phẩm: {_clean(product.get('product_name')) or _product_label(products[0]) if products else 'Sản phẩm đã chọn'}",
            f"- Số lượng: {product.get('quantity') or 1}",
            f"- Giá tham khảo theo dữ liệu hiện có: {_clean(product.get('price')) or 'Chưa có'}",
            f"- Liên hệ: {contact_text}",
            f"- Khu vực/địa chỉ: {location_text}",
            "",
            "Lưu ý: Đây chưa phải đơn hàng đã chốt. "
            "Cửa hàng sẽ xác nhận lại giá, tồn kho và vận chuyển.",
            "",
            "Bạn xác nhận gửi yêu cầu này cho cửa hàng không?",
        ]
        return "\n".join(lines)

    return ""
