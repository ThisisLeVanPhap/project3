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

    if action == "ask_discovery":
        missing = list(getattr(state, "missing_fields", []) or [])
        if "product_type" in missing:
            return "Bạn đang muốn tìm sản phẩm nội thất nào: sofa, bàn, giường, tủ hay món khác?"
        if "room_or_space" in missing:
            return "Bạn định đặt sản phẩm ở phòng nào hoặc không gian rộng/chật khoảng bao nhiêu?"
        if "budget" in missing:
            return "Ngân sách dự kiến của bạn khoảng bao nhiêu để mình lọc lựa chọn phù hợp hơn?"
        return "Bạn chia sẻ thêm 1–2 ưu tiên chính như phòng đặt, ngân sách hoặc phong cách mong muốn nhé."

    if action == "handle_objection":
        objection = _clean(getattr(state, "slots", {}).get("objection_type"))
        if objection == "too_expensive":
            return "Mình hiểu băn khoăn về giá. Bạn cho mình biết mức ngân sách thoải mái hơn, mình sẽ ưu tiên các lựa chọn tương tự nhưng mềm hơn nếu KB có dữ liệu."
        if objection == "pets":
            return "Nhà có thú cưng thì nên ưu tiên chất liệu dễ vệ sinh, ít bám lông và màu ít lộ vết bẩn. Bạn muốn mình lọc các mẫu dễ lau chùi trong dữ liệu hiện có không?"
        if objection == "children":
            return "Nếu nhà có trẻ nhỏ, mình sẽ ưu tiên kiểu dáng bo mềm, chắc chắn và chất liệu dễ vệ sinh. Bạn muốn mình gợi ý theo tiêu chí an toàn và dễ lau không?"
        if objection == "back_pain":
            return "Với nhu cầu ngồi lâu hoặc đau lưng, nên ưu tiên tựa lưng tốt, đệm không quá lún và kích thước phù hợp tư thế ngồi. Bạn muốn mình tìm mẫu thiên về hỗ trợ lưng trong KB không?"
        if objection == "easy_clean":
            return "Nếu ưu tiên dễ vệ sinh, mình sẽ chú ý chất liệu, màu sắc và bề mặt ít bám bẩn. Bạn muốn mình lọc các mẫu dễ lau trong dữ liệu hiện có không?"
        if objection == "durability":
            return "Về độ bền, mình chỉ nên dựa trên chất liệu và thông tin trong KB. Bạn gửi tên/mã mẫu hoặc chọn P1/P2 để mình kiểm tra phần chất liệu cụ thể nhé."
        if objection == "small_room_fit":
            return "Với phòng nhỏ, mình sẽ ưu tiên kích thước gọn, dáng thấp hoặc mẫu ít chiếm lối đi. Bạn cho mình biết phòng khoảng bao nhiêu m² hoặc vị trí đặt nhé."
        return "Mình hiểu bạn vẫn đang cân nhắc. Bạn muốn mình so sánh thêm theo giá, chất liệu hay độ phù hợp không gian?"

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
