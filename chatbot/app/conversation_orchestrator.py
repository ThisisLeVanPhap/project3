import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .llm_client import LLMClient
from .planner_schema import PlannerDecision, decision_from_planner_text, fallback_planner_decision
from .sales_slots import extract_sales_slots, fold_text, repair_mojibake


RetrievalTool = Callable[[str, Dict[str, Any]], List[Any]]


def _has_table_signal(message: str, folded: str) -> bool:
    raw = repair_mojibake(message or "").lower()
    if re.search(r"\bbàn\b", raw):
        return True
    return bool(
        re.search(r"\b(?:mua|tim|chon|lay|can|xem|goi y|tu van|kiem)\s+(?:\d+\s+)?(?:cai\s+)?ban\b", folded)
        or re.search(r"\bban\s+(?:tra|an|hoc|lam viec|sofa|may tinh|trang diem|phu|go|nho|lon|keo|gap)\b", folded)
        or re.search(r"\b(?:bo ban|mat ban|chan ban|table|desk)\b", folded)
    )


@dataclass
class OrchestratorRequest:
    message: str
    mode: str
    channel: Optional[str] = None
    tenant_id: Optional[str] = None
    conversation_id: Optional[str] = None


@dataclass
class OrchestratorContext:
    memory: Dict[str, Any] = field(default_factory=dict)
    retrieval_tool: Optional[RetrievalTool] = None


@dataclass
class OrchestratorResult:
    reply: str
    debug: Dict[str, Any]
    updated_memory: Dict[str, Any]
    retrieval_hits: List[Any]
    answer_mode: str


class ConversationOrchestrator:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def run(self, req: OrchestratorRequest, context: OrchestratorContext) -> OrchestratorResult:
        memory = dict(context.memory or {})
        memory_before = dict(memory)
        planner_prompt = self._build_planner_prompt(req, memory)
        planner_result = None
        planner_called = False
        planner_skip_reason = ""
        planner_error_type = ""
        fallback_reason = ""
        try:
            planner_result = self.llm_client.complete(
                prompt=planner_prompt,
                mode=req.mode,
                purpose="planner",
                max_tokens=700,
                temperature=0.0,
            )
            planner_called = planner_result.called
            planner_skip_reason = planner_result.skip_reason
            planner_error_type = planner_result.error_type
            decision, fallback_reason = decision_from_planner_text(
                planner_result.text,
                request_mode=req.mode,
                user_message=req.message,
            )
        except Exception as exc:
            decision = fallback_planner_decision(req.mode, exc.__class__.__name__)
            fallback_reason = "planner_exception"
            planner_error_type = exc.__class__.__name__
            planner_skip_reason = str(exc) or "planner_exception"

        self._merge_memory(memory, req.message, decision)

        retrieval_hits: List[Any] = []
        effective_filters = self._effective_filters(decision, memory)
        effective_retrieval_query = self._effective_retrieval_query(req.message, memory, decision)
        if decision.need_retrieval and context.retrieval_tool is not None:
            retrieval_hits = list(context.retrieval_tool(effective_retrieval_query, effective_filters) or [])

        evidence = self._build_evidence(retrieval_hits)
        phase_h_response_style = self._phase_h_response_style(req.mode, evidence)
        finalizer_prompt = self._build_finalizer_prompt(req, memory, decision, evidence)
        finalizer_called = False
        finalizer_skip_reason = ""
        finalizer_error_type = ""
        reply = ""
        try:
            finalizer_result = self.llm_client.complete(
                prompt=finalizer_prompt,
                mode=req.mode,
                purpose="finalizer",
                max_tokens=800,
                temperature=0.65,
            )
            finalizer_called = finalizer_result.called
            finalizer_skip_reason = finalizer_result.skip_reason
            finalizer_error_type = finalizer_result.error_type
            reply = (finalizer_result.text or "").strip()
        except Exception as exc:
            finalizer_error_type = exc.__class__.__name__
            finalizer_skip_reason = str(exc) or "finalizer_exception"
            fallback_reason = fallback_reason or "finalizer_exception"

        if not reply:
            reply = self._deterministic_reply(req.message, memory, decision, evidence)
            if not finalizer_skip_reason:
                finalizer_skip_reason = "empty_finalizer_fallback"
            fallback_reason = fallback_reason or "finalizer_fallback"
        reply = self._post_check(reply, bool(retrieval_hits))

        debug = {
            "planner_attempted": True,
            "planner_called": planner_called,
            "planner_skip_reason": planner_skip_reason,
            "planner_error_type": planner_error_type,
            "planner_intent": decision.intent,
            "planner_need_retrieval": decision.need_retrieval,
            "planner_decision": asdict(decision),
            "effective_retrieval_query": effective_retrieval_query,
            "effective_filters": effective_filters,
            "evidence": evidence,
            "phase_h_response_style": phase_h_response_style,
            "finalizer_attempted": True,
            "finalizer_called": finalizer_called,
            "finalizer_skip_reason": finalizer_skip_reason,
            "finalizer_error_type": finalizer_error_type,
            "orchestrator_fallback_reason": fallback_reason,
            "fallback_reason": fallback_reason,
            "tool_calls": ["retrieval"] if decision.need_retrieval and context.retrieval_tool is not None else [],
            "memory_updates": self._memory_updates(memory_before, memory),
            "memory_retained": self._memory_retained(memory_before, memory),
        }
        return OrchestratorResult(
            reply=reply,
            debug=debug,
            updated_memory=memory,
            retrieval_hits=retrieval_hits,
            answer_mode="orchestrator",
        )

    def _build_planner_prompt(self, req: OrchestratorRequest, memory: Dict[str, Any]) -> str:
        mode_rules = {
            "tenant_sales": (
                "Mode tenant_sales: tu van ban hang noi that; chi mode nay moi co the tao lead o tang server, "
                "planner khong tu xac nhan mua hang."
            ),
            "general_compare": (
                "Mode general_compare: so sanh lua chon/san pham/tieu chi; khong tao lead, khong chot mua, "
                "khong hoi thong tin lien he. Neu can du lieu san pham de so sanh thi need_retrieval=true."
            ),
            "market_price": (
                "Mode market_price: danh gia gia dat/re/hop ly dua tren evidence; khong tao lead, khong chot mua, "
                "khong bia gia thi truong. Neu can moc so sanh gia thi need_retrieval=true."
            ),
        }.get(req.mode, "")
        return (
            "Ban la chuyen gia dieu phoi tu van noi that.\n"
            "Tra JSON only, khong tra loi user.\n"
            "Khong bia san pham/SKU/gia/link/ton kho.\n"
            "Khong tu doi mode. Khong suy dien category neu user noi mo ho.\n"
            f"{mode_rules}\n"
            "Hieu cac ngu canh: nha moi, phong khach trong, cho bo me, cho con trai, doi y tu ban sang ghe.\n"
            "Schema keys: mode, intent, need_retrieval, search_query, filters, memory_delta, response_goal, ask_user, safety_notes.\n"
            f"mode_request={req.mode}\n"
            f"memory={json.dumps(memory, ensure_ascii=False)}\n"
            f"user_message={req.message}\n"
        )

    def _build_finalizer_prompt(
        self,
        req: OrchestratorRequest,
        memory: Dict[str, Any],
        decision: PlannerDecision,
        evidence: List[Dict[str, Any]],
    ) -> str:
        evidence_rules = (
            "Co product evidence: chi dung evidence; khong invent product/SKU/price/link/availability/stock; "
            "neu khong co field trong evidence thi bo qua; goi y toi da 3 san pham tru khi user hoi them."
            if evidence
            else "Khong co product evidence: khong noi 'minh tim thay'; khong noi SKU/gia/link/san pham cu the."
        )
        if req.mode == "general_compare":
            mode_rules = (
                "Vai tro general_compare: so sanh theo tieu chi ro rang nhu cong nang, kich thuoc, vat lieu, phong cach, gia neu co evidence. "
                "PHASE H FORMAT general_compare: neu co tu 2 lua chon hoac co product evidence, dung markdown table ngan voi cot Tieu chi va tung Lua chon; "
                "moi o chi dung evidence/user context, field thieu thi ghi chua co trong evidence. Sau bang co mot dong Ket luan nghieng ve lua chon nao neu dieu kien nao. "
                "Neu user hoi nen chon cai nao, dua trade-off va khuyen nghi theo ngu canh, khong chot mua/khong xin lien he."
            )
        elif req.mode == "market_price":
            mode_rules = (
                "Vai tro market_price: danh gia muc gia co hop ly khong dua tren evidence va ngu canh su dung. "
                "PHASE H FORMAT market_price: tra loi bang cac muc Muc hoi, Moc tham chieu, Nhan dinh, Ket luan. "
                "Chi neu gia do user dua hoac gia co trong evidence; neu thieu evidence thi noi ro chua du moc tham chieu, khong bia gia thi truong/khuyen mai/ton kho."
            )
        else:
            mode_rules = "Vai tro tenant_sales: tu van nhu nhan vien noi that, giu hoi thoai tu nhien va chi hoi tiep khi can."
        structure_rule = (
            "Voi general_compare/market_price, uu tien cau truc bang/bullet ngan gon ro rang; voi mode khac viet tu nhien, khong bullet-heavy robot."
            if req.mode in {"general_compare", "market_price"}
            else "Viet nhu tu van noi that that, khong bullet-heavy robot."
        )
        return (
            "Tra loi tieng Viet tu nhien, 2-5 cau, nhu nguoi ban noi that that.\n"
            "Khong dung cau phu dinh cung kieu 'minh khong...' hoac 'minh chua...'.\n"
            "Khong hoi lai dieu khach da noi. Hoi toi da 1 cau tiep theo.\n"
            f"{structure_rule}\n"
            f"{mode_rules}\n"
            f"{evidence_rules}\n"
            f"mode={req.mode}\n"
            f"memory={json.dumps(memory, ensure_ascii=False)}\n"
            f"planner={json.dumps(asdict(decision), ensure_ascii=False)}\n"
            f"evidence={json.dumps(evidence, ensure_ascii=False)}\n"
            f"user_message={req.message}\n"
        )

    def _merge_memory(self, memory: Dict[str, Any], message: str, decision: PlannerDecision) -> None:
        for key, value in (decision.memory_delta or {}).items():
            if value not in (None, "", [], {}):
                memory[key] = value
        slots = extract_sales_slots(message)
        for key in ("room", "space", "product_category", "product_type", "style", "budget", "budget_text", "health_need"):
            if slots.get(key):
                memory[key] = slots[key]
        text = fold_text(repair_mojibake(message or ""))
        if "nha moi" in text or "moi mua" in text:
            memory["home_context"] = "nha moi"
        if "phong khach" in text:
            memory["room"] = "phong khach"
        if any(token in text for token in ("nguoi gia", "bo me", "ba me", "ong ba")):
            memory["who_for"] = "nguoi lon tuoi"
        if any(token in text for token in ("tre con", "con nho", "tre nho")):
            memory["has_children"] = True
        if any(token in text for token in ("het thich ban", "khong thich ban", "thoi") ) and "ban" in text:
            dislikes = list(memory.get("dislikes") or [])
            if not any(fold_text(item) == "ban" for item in dislikes):
                dislikes.append("Bàn")
            memory["dislikes"] = dislikes
        if "ghe" in text:
            memory["product_focus"] = "Ghế"
        elif _has_table_signal(message, text) and not memory.get("product_focus"):
            memory["product_focus"] = "Bàn"
        if any(token in text for token in ("mem mem", "em ai", "ghe mem", "thu gian")):
            needs = list(memory.get("needs") or [])
            if "êm và mềm" not in needs:
                needs.append("êm và mềm")
            memory["needs"] = needs

    def _effective_filters(self, decision: PlannerDecision, memory: Dict[str, Any]) -> Dict[str, Any]:
        filters = dict(decision.filters or {})
        focus = (
            filters.get("product_category")
            or filters.get("product_type")
            or memory.get("product_focus")
            or memory.get("product_category")
            or memory.get("product_type")
        )
        if focus and not (filters.get("product_category") or filters.get("product_type")):
            filters["product_category"] = focus
        return filters

    def _effective_retrieval_query(self, message: str, memory: Dict[str, Any], decision: PlannerDecision) -> str:
        if (decision.search_query or "").strip():
            return decision.search_query.strip()
        parts = [
            memory.get("product_focus") or memory.get("product_category") or memory.get("product_type"),
            memory.get("subtype") or memory.get("product_subtype"),
            memory.get("room") or memory.get("space"),
            memory.get("style"),
            memory.get("budget") or memory.get("budget_text"),
        ]
        needs = memory.get("needs") or memory.get("constraints") or []
        if isinstance(needs, list):
            parts.append(" ".join(str(item) for item in needs if item))
        elif needs:
            parts.append(str(needs))
        query = " ".join(str(part) for part in parts if part).strip()
        text = fold_text(repair_mojibake(message or ""))
        generic_followup = bool(re.search(r"\b(tuong tu|mau khac|mau nao|cho xem them|tham khao|goi y|loc tiep|con mau)\b", text))
        if query and (generic_followup or len(text.split()) <= 5):
            return query
        return query or message

    def _memory_updates(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        changed: Dict[str, Any] = {}
        for key, value in after.items():
            if value not in (None, "", [], {}) and before.get(key) != value:
                changed[key] = value
        return changed

    def _memory_retained(self, before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
        retained: List[str] = []
        for key, value in before.items():
            if value not in (None, "", [], {}) and after.get(key) == value:
                retained.append(key)
        return retained

    def _phase_h_response_style(self, mode: str, evidence: List[Dict[str, Any]]) -> str:
        if mode == "general_compare":
            return "criteria_table" if evidence else "criteria_framework"
        if mode == "market_price":
            return "price_reasoning_with_evidence" if evidence else "price_reasoning_no_evidence"
        return "natural_consult"

    def _phase_h_item_label(self, item: Dict[str, Any], idx: int) -> str:
        name = str(item.get("name") or f"Lua chon {idx}").strip()
        sku = str(item.get("sku") or "").strip()
        return f"{name} ({sku})" if sku else name

    def _phase_h_price_text(self, value: Any) -> str:
        if value in (None, ""):
            return "chua co trong evidence"
        if isinstance(value, (int, float)):
            return f"{int(value):,} VND".replace(",", ".")
        return str(value)

    def _phase_h_compare_reply(self, evidence: List[Dict[str, Any]]) -> str:
        items = evidence[:3]
        labels = [self._phase_h_item_label(item, idx) for idx, item in enumerate(items, start=1)]
        header = "| Tieu chi | " + " | ".join(labels) + " |"
        divider = "|---|" + "|".join("---" for _ in labels) + "|"

        def row(title: str, values: List[str]) -> str:
            return "| " + title + " | " + " | ".join(values) + " |"

        category_values = [str(item.get("category") or "chua co trong evidence") for item in items]
        price_values = [self._phase_h_price_text(item.get("price")) for item in items]
        url_values = ["co link evidence" if item.get("url") else "chua co trong evidence" for item in items]
        rows = [
            header,
            divider,
            row("Nhom/danh muc", category_values),
            row("Gia trong du lieu", price_values),
            row("Nguon/link", url_values),
        ]
        return (
            "Minh so theo cac tieu chi co evidence hien tai:\n"
            + "\n".join(rows)
            + "\nKet luan: neu uu tien gia, hay nghieng ve lua chon co gia thap hon trong evidence; neu uu tien chat lieu/cong nang, can them thong tin tu product detail truoc khi chot."
        )

    def _phase_h_user_price_phrase(self, message: str) -> str:
        text = fold_text(repair_mojibake(message or ""))
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(trieu|tr|nghin|k|vnd|dong)", text)
        if not match:
            return "chua thay muc gia cu the trong cau hoi"
        return f"{match.group(1)} {match.group(2)}"

    def _phase_h_price_reply(self, message: str, evidence: List[Dict[str, Any]]) -> str:
        asked_price = self._phase_h_user_price_phrase(message)
        prices = [item.get("price") for item in evidence if item.get("price") not in (None, "")]
        numeric_prices = [price for price in prices if isinstance(price, (int, float))]
        if numeric_prices:
            ref = f"{self._phase_h_price_text(min(numeric_prices))} - {self._phase_h_price_text(max(numeric_prices))}"
        elif prices:
            ref = ", ".join(self._phase_h_price_text(price) for price in prices[:3])
        else:
            ref = "chua co gia trong evidence"

        if evidence:
            return (
                f"Muc hoi: {asked_price}.\n"
                f"Moc tham chieu: {ref} tu {len(evidence[:3])} mau evidence hien co.\n"
                "Nhan dinh: muc hoi chi nen xem la hop ly neu nam gan moc tham chieu cung nhom va khop cong nang/chat lieu; neu cao hon ro ret thi can co ly do nhu kich thuoc, vat lieu hoac thiet ke tot hon.\n"
                "Ket luan: co the can nhac theo moc evidence tren, nhung chua nen khang dinh gia thi truong neu du lieu con thieu."
            )
        return (
            f"Muc hoi: {asked_price}.\n"
            "Moc tham chieu: chua co product evidence nen khong neu SKU/gia/link cu the.\n"
            "Nhan dinh: can so voi san pham cung loai, kich thuoc, chat lieu va cong nang.\n"
            "Ket luan: chua du co so de noi dat hay re; gui ten/ma san pham hoac link de minh doi chieu theo evidence."
        )

    def _deterministic_reply(
        self,
        message: str,
        memory: Dict[str, Any],
        decision: PlannerDecision,
        evidence: List[Dict[str, Any]],
    ) -> str:
        text = fold_text(repair_mojibake(message or ""))
        if decision.mode == "general_compare":
            if evidence:
                return self._phase_h_compare_reply(evidence)
            return (
                "Khung so sanh nen di theo cac tieu chi: cong nang, kich thuoc, chat lieu, phong cach va gia trong du lieu. "
                "Hien chua co product evidence cu the nen chua nen neu SKU/gia/link; ban gui 2-3 lua chon, minh se lap bang Tieu chi de quyet nhanh hon."
            )
        if decision.mode == "market_price":
            return self._phase_h_price_reply(message, evidence)
        if decision.mode == "general_compare":
            if evidence:
                lines = ["Mình so nhanh theo dữ liệu đang có:"]
                for idx, item in enumerate(evidence[:3], start=1):
                    bits = [str(item.get("name") or f"Lựa chọn {idx}")]
                    if item.get("price") not in (None, ""):
                        bits.append(str(item["price"]))
                    if item.get("category"):
                        bits.append(str(item["category"]))
                    lines.append(f"{idx}. " + " - ".join(bits))
                lines.append("Nếu ưu tiên dùng hằng ngày thì chọn mẫu hợp kích thước và dễ vệ sinh hơn; nếu ưu tiên điểm nhấn thì chọn mẫu nổi bật hơn về kiểu dáng.")
                return "\n".join(lines)
            return (
                "Nếu so theo tư vấn nội thất, mình sẽ đặt tiêu chí dùng thực tế trước: đặt ở phòng nào, ai dùng, kích thước và ngân sách; "
                "sau đó mới chốt kiểu dáng. Bạn gửi mình 2-3 lựa chọn cụ thể, mình sẽ so từng điểm cho dễ quyết."
            )
        if decision.mode == "market_price":
            if evidence:
                prices = [item.get("price") for item in evidence if item.get("price") not in (None, "")]
                price_text = ", ".join(str(p) for p in prices[:3]) or "các mẫu cùng nhóm"
                return (
                    f"Dựa trên các mẫu có dữ liệu giá ({price_text}), mình sẽ xem mức bạn hỏi là hợp lý nếu nó gần nhóm cùng công năng và chất liệu. "
                    "Nếu cao hơn hẳn, cần có lý do như kích thước lớn, vật liệu tốt hơn hoặc thiết kế đặc biệt; còn nếu chỉ giống công năng cơ bản thì nên so thêm 1-2 mẫu cùng loại."
                )
            return (
                "Với câu hỏi giá, mình sẽ đánh giá theo cùng loại sản phẩm, vật liệu, kích thước và công năng trước. "
                "Bạn cho mình tên/mã sản phẩm hoặc mức giá cụ thể, mình sẽ nói mức đó đang hợp lý, hơi cao hay đáng cân nhắc hơn."
            )
        if evidence:
            lines = ["Mình lọc được vài mẫu hợp với nhu cầu bạn vừa nói:"]
            for idx, item in enumerate(evidence[:3], start=1):
                bits = [str(item.get("name") or f"Mẫu {idx}")]
                if item.get("sku"):
                    bits.append(str(item["sku"]))
                if item.get("price") not in (None, ""):
                    bits.append(str(item["price"]))
                lines.append(f"{idx}. " + " - ".join(bits))
            lines.append("Bạn muốn mình so kỹ hơn theo độ êm, kích thước hay chất liệu?")
            return "\n".join(lines)
        if "phong cach" in text or "kieu" in text or memory.get("needs"):
            focus = memory.get("product_focus") or "món đó"
            room = memory.get("room") or "không gian của bạn"
            return (
                f"Với {str(focus).lower()} cho {room}, mình sẽ chia vài hướng dễ chọn: hiện đại gọn, tối giản, Bắc Âu sáng màu, lounge mềm mại hoặc cổ điển nhẹ. "
                "Nếu bạn thích cảm giác mềm mềm thì nên ưu tiên dáng có đệm, tựa vững và chất liệu dễ vệ sinh hơn là kiểu quá mảnh. "
                "Bạn muốn mình đi theo hướng lounge mềm hay tối giản gọn hơn?"
            )
        if fold_text(memory.get("product_focus") or "") == "ghe":
            return (
                "Được, nếu chuyển sang bộ ghế thì mình sẽ ưu tiên chỗ ngồi chính trước, rồi mới tính bàn/kệ phụ để phòng không bị rối. "
                "Với phòng khách, bộ ghế nên vừa kích thước phòng, ngồi thoải mái và chất liệu dễ vệ sinh nếu dùng hằng ngày. "
                "Bạn thích bộ ghế mềm thư giãn hay gọn hiện đại hơn?"
            )
        if memory.get("has_children") or "tre con" in text or "con nho" in text:
            return (
                "Neu phong khach co ca nguoi lon tuoi va tre nho, nen uu tien do chac chan, bo goc, it canh sac va be mat de lau ve sinh. "
                "Ghe nen co tua vung, dem vua phai de dung len ngoi xuong de hon; ban/ke nen thap vua tam va kho neo chac. "
                "Ban muon minh di tiep theo huong cho ngoi, ban ke hay do trang tri an toan?"
            )
        if any(token in text for token in ("nguoi gia", "bo me", "ba me", "ong ba")):
            return (
                "Voi nha co nguoi lon tuoi, minh se uu tien mon dung hang ngay that vung, de dung len ngoi xuong va chat lieu de lau. "
                "O phong khach, ghe co tua chac, ban tra bo goc, ke gon va den anh sang diu se hop hon do chi de trang tri. "
                "Ban muon uu tien cho ngoi hay ban/ke truoc?"
            )
        if "phong khach" in text or memory.get("room") == "phong khach":
            return (
                "Voi phong khach dang trong, nen chia thanh cho ngoi tiep khach, ban/ke de can khong gian, roi den va trang tri de phong am hon. "
                "Neu chua co gi, minh se chon sofa hoac bo ghe vua kich thuoc truoc, sau do moi them ban tra, ke tivi va den cay/den trang tri. "
                "Ban muon uu tien mon dung hang ngay hay mon tao diem nhan truoc?"
            )
        if "nha moi" in text or memory.get("home_context") == "nha moi":
            return (
                "Nha moi mua thi nen bat dau tu cach sinh hoat cua gia dinh, roi chia ngan sach theo phong de cac mon khop nhau. "
                "Thuong nen uu tien phong khach va phong ngu truoc, tiep den ban an/khu bep, luu tru va den/trang tri de nha am hon. "
                "Ban muon bat dau voi phong khach, phong ngu hay khu bep/phong an truoc?"
            )
        return "Minh se di tu nhu cau su dung, phong dat va nguoi dung de chon mon noi that hop hon. Ban dinh uu tien phong nao truoc?"

    def _build_evidence(self, retrieval_hits: List[Any]) -> List[Dict[str, Any]]:
        evidence = []
        for hit in retrieval_hits[:3]:
            meta = getattr(hit, "metadata", {}) if hasattr(hit, "metadata") else {}
            if not isinstance(meta, dict):
                meta = {}
            evidence.append({
                "name": meta.get("product_name") or getattr(hit, "title", ""),
                "sku": meta.get("sku", ""),
                "price": meta.get("price"),
                "category": meta.get("category") or getattr(hit, "category", ""),
                "url": meta.get("source_url") or getattr(hit, "source", ""),
            })
        return evidence

    def _post_check(self, reply: str, has_evidence: bool) -> str:
        cleaned = (reply or "").strip()
        if not has_evidence:
            cleaned = cleaned.replace("minh tim thay", "minh goi y")
            cleaned = cleaned.replace("Mình tìm thấy", "Mình gợi ý")
        if cleaned.count("?") > 1:
            first = cleaned.find("?")
            cleaned = cleaned[:first + 1] + cleaned[first + 1:].replace("?", ".")
        return cleaned
