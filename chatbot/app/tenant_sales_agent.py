import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List


BRIEF_SLOT = "customer_brief"


@dataclass
class TenantSalesDecision:
    action: str
    reason: str


def _fold(value: Any) -> str:
    text = str(value or "").replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _add_unique(items: List[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _new_brief() -> Dict[str, Any]:
    return {
        "who_for": "",
        "room": "",
        "product_focus": "",
        "subtype": "",
        "needs": [],
        "budget": "",
        "style": "",
        "dislikes": [],
        "conversation_goal": "consult",
        "answered_topics": [],
    }


def _brief_from_state(state: Any) -> Dict[str, Any]:
    raw = dict((getattr(state, "slots", {}) or {}).get(BRIEF_SLOT) or {})
    brief = _new_brief()
    brief.update({k: v for k, v in raw.items() if k in brief})
    brief["needs"] = _as_list(brief.get("needs"))
    brief["dislikes"] = _as_list(brief.get("dislikes"))
    brief["answered_topics"] = _as_list(brief.get("answered_topics"))
    return brief


def _has_lamp_category_signal(text: str, raw_text: str = "") -> bool:
    raw = str(raw_text or "").lower()
    if re.search(r"\bđèn\b", raw):
        return True
    return bool(
        re.search(r"\b(?:mua|tim|chon|lay|can|xem|goi\s+y|tu\s+van)\s+(?:\d+\s+)?(?:cai\s+)?den\b", text)
        or re.search(r"\bden\s+(?:trang\s+tri|decor|chum|tha|tran|tuong|ban|cay|ngu|led|hoc|doc\s+sach|phong)\b", text)
        or re.search(r"\b(?:bong|choa)\s+den\b", text)
        or re.search(r"\b(?:lamp|light)\b", text)
    )


def _has_table_category_signal(text: str, raw_text: str = "") -> bool:
    raw = str(raw_text or "").lower()
    if re.search(r"\bbàn\b", raw):
        return True
    return bool(
        re.search(r"\b(?:mua|tim|chon|lay|can|xem|goi\s+y|tu\s+van|kiem)\s+(?:\d+\s+)?(?:cai\s+)?ban\b", text)
        or re.search(r"\bban\s+(?:tra|an|hoc|lam\s+viec|sofa|may\s+tinh|trang\s+diem|phu|go|nho|lon|keo|gap)\b", text)
        or re.search(r"\b(?:bo\s+ban|mat\s+ban|chan\s+ban|table|desk)\b", text)
    )


def _category_from_text(text: str, raw_text: str = "") -> str:
    if re.search(r"\b(ghe|chair|sofa)\b", text):
        return "Ghế"
    if _has_table_category_signal(text, raw_text):
        return "Bàn"
    ignore_bare_tu = bool(re.search(r"\btu\s*\d", text) or re.search(r"\btuong\s+tu\b", text))
    if re.search(r"\b(cabinet|wardrobe)\b", text) or (not ignore_bare_tu and re.search(r"\btu\b", text)):
        return "Tủ"
    if re.search(r"\b(giuong|bed)\b", text):
        return "Giường"
    if _has_lamp_category_signal(text, raw_text):
        return "Đèn"
    if re.search(r"\b(tranh|picture|painting)\b", text):
        return "Tranh"
    return ""


def update_customer_brief(state: Any, message: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    brief = _brief_from_state(state)
    text = _fold(message)
    slots = slots or {}

    category = slots.get("product_category") or slots.get("product_type") or _category_from_text(text, message)
    subtype = slots.get("product_subtype") or ""

    if re.search(r"\b(ghe\s+thu\s*gian|ghe\s+em|ghe\s+mem|sofa\s+don|ghe\s+boc\s+nem|ghe\s+boc\s+vai|ghe\s+boc\s+da)\b", text):
        category = "Ghế"
        subtype = "Ghế thư giãn"
        _add_unique(brief["needs"], "êm và thư giãn")
    elif re.search(r"\b(bo\s+ghe|bo\s+sofa|sofa)\b", text):
        category = "Ghế"
        subtype = subtype or "Bộ ghế/sofa"

    if category:
        old_focus = brief.get("product_focus") or ""
        if old_focus and _fold(old_focus) != _fold(category):
            _add_unique(brief["dislikes"], old_focus)
        brief["product_focus"] = category
        _add_unique(brief["answered_topics"], "product_focus")
    if subtype:
        brief["subtype"] = subtype
        _add_unique(brief["answered_topics"], "subtype")

    room = slots.get("room") or slots.get("space") or ""
    if not room and re.search(r"\b(phong\s+khach|living room)\b", text):
        room = "phòng khách"
    if not room and re.search(r"\b(phong\s+ngu|bedroom)\b", text):
        room = "phòng ngủ"
    if not room and re.search(r"\b(phong\s+an|bep|kitchen|dining room)\b", text):
        room = "phòng ăn"
    if not room and re.search(r"\b(phong\s+lam\s+viec|goc\s+hoc\s+tap|study room|home office)\b", text):
        room = "phòng làm việc"
    if room:
        brief["room"] = str(room)
        _add_unique(brief["answered_topics"], "room")

    budget = slots.get("budget") or slots.get("budget_text") or slots.get("budget_usd") or ""
    if budget:
        brief["budget"] = str(budget)
        _add_unique(brief["answered_topics"], "budget")

    style = slots.get("style") or ""
    if style:
        brief["style"] = str(style)
        _add_unique(brief["answered_topics"], "style")

    if re.search(r"\b(bo\s+me|ba\s+me|ong\s+ba|nguoi\s+gia|nguoi\s+lon\s+tuoi|elderly|senior)\b", text):
        brief["who_for"] = "bố mẹ/người lớn tuổi"
        _add_unique(brief["needs"], "hợp người lớn tuổi")
        _add_unique(brief["needs"], "an toàn và dễ đứng lên ngồi xuống")
    if re.search(r"\b(de\s+lau|de\s+ve\s+sinh|it\s+bam\s+bui|chong\s+ban|easy clean|washable)\b", text) or slots.get("easy_clean"):
        _add_unique(brief["needs"], "dễ lau vệ sinh")
    if re.search(r"\b(mem|em|em\s+ai|thu\s+gian|ngoi\s+lau|tua\s+lung|dau\s+lung)\b", text) or slots.get("back_pain"):
        _add_unique(brief["needs"], "êm và có tựa đỡ tốt")
    if slots.get("constraints"):
        for item in _as_list(slots.get("constraints")):
            label = {
                "elder_friendly": "hợp người lớn tuổi",
                "easy_clean": "dễ lau vệ sinh",
                "back_pain": "êm và có tựa đỡ tốt",
                "pets": "dễ vệ sinh khi nhà có thú cưng",
                "children": "an toàn cho trẻ nhỏ",
                "small_room": "gọn cho phòng nhỏ",
            }.get(item, item)
            _add_unique(brief["needs"], label)

    if re.search(r"\b(het\s+thich|khong\s+thich|thoi)\b.*\bban\b", text):
        _add_unique(brief["dislikes"], "Bàn")
    if re.search(r"\b(cho\s+(?:t|toi|minh)\s+vai|tham\s+khao|mau|goi\s+y|loc|tim)\b", text):
        brief["conversation_goal"] = "browse_products"
    elif re.search(r"\b(nen\s+mua\s+gi|tu\s+van|goi\s+y)\b", text):
        brief["conversation_goal"] = "idea_advice"

    state.slots[BRIEF_SLOT] = brief
    if brief.get("product_focus"):
        state.slots["product_category"] = brief["product_focus"]
        state.slots.setdefault("product_type", brief["product_focus"])
    if brief.get("subtype"):
        state.slots["product_type"] = brief["subtype"]
        state.slots["product_subtype"] = brief["subtype"]
    if brief.get("room"):
        state.slots["room"] = brief["room"]
    if brief.get("budget"):
        state.slots["budget"] = brief["budget"]
    if brief.get("needs"):
        state.slots["constraints"] = brief["needs"]
    return brief


def wants_style_advice(message: str) -> bool:
    text = _fold(message)
    if re.search(r"\b(phong\s+cach|style)\b", text):
        return True
    return bool(
        re.search(r"\b(cua\s+hang|shop|ben)\b", text)
        and re.search(r"\b(co|ban)\b", text)
        and re.search(r"\b(kieu|kieu\s+dang|loai)\b", text)
    )


def is_transactional_turn(action: str, slots: Dict[str, Any]) -> bool:
    intents = slots.get("intents") or []
    if action in {
        "ask_contact", "ask_confirmation", "handoff", "handoff_sent", "handoff_failed",
        "handoff_already_sent", "confirmation_cancelled", "confirmation_without_pending",
        "ask_product",
    }:
        return True
    if "contact_provided" in intents or "handoff_request" in intents:
        return True
    if slots.get("product_sku_ref") or slots.get("has_product_reference"):
        return True
    if "cancel" in intents and not _category_from_text(_fold(slots.get("raw_message") or "")):
        return True
    return False


def decide_next_response(message: str, brief: Dict[str, Any], action: str, slots: Dict[str, Any]) -> TenantSalesDecision:
    slots = dict(slots or {})
    slots["raw_message"] = message
    if is_transactional_turn(action, slots):
        return TenantSalesDecision("legacy", "transactional_turn")

    text = _fold(message)
    if wants_style_advice(message):
        return TenantSalesDecision("advice", "style_question")
    if re.search(r"\b(nen\s+mua\s+gi|mua\s+gi\s+cho|goi\s+y\s+thu)\b", text) and not brief.get("product_focus"):
        return TenantSalesDecision("advice", "open_idea_advice")
    if re.search(r"\b(cho\s+(?:t|toi|minh)\s+vai|tham\s+khao|mau|loc|tim|goi\s+y)\b", text) and brief.get("product_focus"):
        return TenantSalesDecision("retrieve", "browse_request")
    if brief.get("product_focus") and (brief.get("budget") or (brief.get("room") and brief.get("needs"))):
        return TenantSalesDecision("retrieve", "brief_ready_with_constraints")
    if brief.get("product_focus") and brief.get("subtype") and (brief.get("needs") or brief.get("budget") or brief.get("room")):
        return TenantSalesDecision("retrieve", "brief_ready")
    if action == "ask_discovery" or not brief.get("product_focus") or (brief.get("product_focus") and not brief.get("subtype")):
        return TenantSalesDecision("advice", "continue_consultation")
    return TenantSalesDecision("retrieve", "default_product_context")


def build_search_query(brief: Dict[str, Any], fallback: str) -> str:
    parts = [
        brief.get("subtype"),
        brief.get("product_focus"),
        brief.get("room"),
        brief.get("style"),
        brief.get("budget"),
        " ".join(brief.get("needs") or []),
    ]
    query = " ".join(str(p) for p in parts if p).strip()
    return query or fallback


def compose_advice(message: str, brief: Dict[str, Any]) -> str:
    focus = brief.get("product_focus")
    subtype = brief.get("subtype")
    room = brief.get("room") or "không gian đó"
    needs = brief.get("needs") or []
    text = _fold(message)

    if wants_style_advice(message):
        if _fold(focus) == "ghe":
            return (
                f"Với ghế cho {room}, mình sẽ chia thành vài hướng dễ chọn: hiện đại gọn, tối giản, Bắc Âu sáng màu, "
                "cafe/lounge mềm mại và cổ điển nhẹ. Nếu ưu tiên người lớn tuổi hoặc dễ lau, mình sẽ nghiêng về ghế có tựa chắc, "
                "đệm vừa phải và chất liệu da/giả da hoặc vải dễ vệ sinh. Bạn muốn mình lọc vài mẫu theo hướng êm thư giãn luôn không?"
            )
        return (
            "Bên mình có thể tư vấn theo các hướng hiện đại, tối giản, Bắc Âu, cổ điển nhẹ hoặc ấm cúng tự nhiên. "
            "Bạn muốn mình ưu tiên cảm giác gọn sáng hay mềm ấm hơn?"
        )

    if not focus:
        if re.search(r"\b(noi\s+that|nha\s+moi|can\s+ho\s+moi|moi\s+mua\s+nha|setup\s+nha|set\s+up\s+nha)\b", text):
            return (
                "Nhà mới mua thì mình sẽ đi từ cách sinh hoạt trước, rồi mới chia ngân sách theo từng khu để tránh mua lẻ tẻ mà không khớp nhau. "
                "Thường nên ưu tiên phòng khách và phòng ngủ trước, sau đó đến bàn ăn/khu bếp, lưu trữ và đèn/trang trí để hoàn thiện cảm giác ấm nhà. "
                "Bạn muốn mình bắt đầu lập hướng chọn cho phòng khách, phòng ngủ hay khu bếp/phòng ăn trước?"
            )
        if brief.get("who_for"):
            return (
                "Nếu mua cho bố mẹ, mình sẽ ưu tiên món dùng hằng ngày, an toàn và dễ vệ sinh hơn là đồ chỉ để trang trí. "
                "Một vài hướng hợp lý là ghế thư giãn có tựa tốt, đèn đọc sách dịu mắt, bàn phụ nhỏ cạnh ghế hoặc kệ gọn cho phòng khách. "
                "Bạn muốn mình tư vấn theo hướng ghế thư giãn hay một món tiện ích nhỏ trước?"
            )
        if brief.get("room"):
            room_fold = _fold(brief.get("room"))
            if "phong ngu" in room_fold:
                return (
                    "Với phòng ngủ, mình sẽ ưu tiên cảm giác nghỉ ngơi trước: giường hoặc nệm/táp đầu giường nếu thiếu điểm chính, "
                    "tủ áo/kệ gọn nếu cần thêm lưu trữ, còn bàn trang điểm hoặc đèn ngủ nếu muốn phòng ấm hơn. "
                    "Bạn muốn mình gợi ý theo hướng nghỉ ngơi, lưu trữ hay góc làm việc nhỏ trong phòng ngủ?"
                )
            if "phong an" in room_fold or "bep" in room_fold:
                return (
                    "Với phòng ăn, nên chọn quanh cách sinh hoạt của nhà mình: bàn ăn là trung tâm, ghế ăn quyết định độ thoải mái, "
                    "còn tủ/kệ bát đĩa giúp khu vực gọn hơn. "
                    "Bạn muốn mình tư vấn bộ bàn ghế ăn trước hay các món phụ để phòng ăn gọn và ấm hơn?"
                )
            if "phong khach" in room_fold:
                return (
                    "Với phòng khách, mình sẽ nhìn theo ba hướng: chỗ ngồi tiếp khách, bàn/kệ để cân không gian, và đèn/trang trí để phòng bớt trống. "
                    "Bạn muốn ưu tiên món dùng hằng ngày như sofa/bàn trà hay món tạo điểm nhấn trước?"
                )
            return (
                f"Với {brief.get('room')}, mình sẽ chọn theo cách bạn dùng không gian đó trước, rồi mới lọc kiểu dáng và ngân sách. "
                "Bạn muốn ưu tiên món chính trong phòng hay vài món nhỏ để hoàn thiện không gian?"
            )
        return (
            "Mình có thể gợi ý theo người dùng, phòng đặt và thói quen sinh hoạt."
        )

    if _fold(focus) == "ghe" and not subtype:
        return (
            "Được, với ghế mình sẽ chọn theo cách dùng trước: ghế thư giãn để ngồi lâu, ghế ăn cho bàn ăn, ghế làm việc hoặc ghế trang trí. "
            "Nếu mua cho bố mẹ thì ghế thư giãn có tựa chắc và dễ lau thường đáng cân nhắc nhất. Bạn muốn đi theo hướng ghế thư giãn không?"
        )

    if _fold(subtype) == "ghe thu gian":
        need_text = ", ".join(needs[:2]) if needs else "êm, có tựa tốt"
        return (
            f"Ổn, ghế thư giãn thì mình sẽ ưu tiên loại {need_text}, ngồi lên không bị lún quá sâu và đứng dậy không quá khó. "
            "Bạn có muốn mình lọc vài mẫu đang có trong dữ liệu theo tiêu chí đó không?"
        )

    return (
        f"Với {str(subtype or focus).lower()} cho {room}, mình sẽ ưu tiên mục đích dùng và kích thước trước rồi mới chốt kiểu dáng. "
        "Bạn định đặt trong phòng nào hoặc dùng chính để ăn, học/làm việc hay tiếp khách để mình lọc mẫu sát hơn?"
    )


def _hit_meta(hit: Any) -> Dict[str, Any]:
    meta = getattr(hit, "metadata", {}) if hasattr(hit, "metadata") else {}
    return meta if isinstance(meta, dict) else {}


def compose_listing(message: str, hits: List[Any], brief: Dict[str, Any]) -> str:
    focus = brief.get("subtype") or brief.get("product_focus") or "sản phẩm"
    room = brief.get("room") or "không gian của bạn"
    needs = brief.get("needs") or []
    intro = f"Mình lọc được vài mẫu {str(focus).lower()} hợp với {room}"
    if needs:
        intro += ", ưu tiên " + ", ".join(needs[:2])
    lines = [intro + ":"]
    for idx, hit in enumerate((hits or [])[:3], start=1):
        meta = _hit_meta(hit)
        name = str(meta.get("product_name") or getattr(hit, "title", "") or f"Mẫu {idx}").strip()
        sku = str(meta.get("sku") or "").strip()
        price = meta.get("price")
        detail = []
        if sku:
            detail.append(sku)
        if price not in (None, ""):
            try:
                detail.append(f"{int(float(price)):,} VND".replace(",", "."))
            except (TypeError, ValueError):
                detail.append(str(price))
        suffix = f" ({' - '.join(detail)})" if detail else ""
        if idx == 1 and needs:
            reason = "hợp nhất để xem trước vì bám sát tiêu chí bạn vừa nói"
        elif idx == 2:
            reason = "là phương án dự phòng nếu bạn muốn so thêm kiểu dáng"
        else:
            reason = "để bạn có thêm một lựa chọn tham khảo"
        lines.append(f"{idx}. {name}{suffix}: {reason}.")
    lines.append("Bạn muốn mình so kỹ 2 mẫu đầu theo độ êm, dễ vệ sinh và hợp người lớn tuổi không?")
    return "\n".join(lines)
