from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Lightweight Chatbot Demo")


@dataclass
class ConversationState:
    intent: Optional[str] = None
    category: Optional[str] = None
    budget: Optional[int] = None
    preferences: List[str] = field(default_factory=list)
    rejected: List[str] = field(default_factory=list)
    last_behavior: Optional[str] = None
    turns: List[str] = field(default_factory=list)


STATE_STORE: Dict[str, ConversationState] = {}


PRODUCTS = [
    {"name": "Compact Sofa A", "price": 3000000, "tags": ["sofa", "compact", "budget", "small-space"]},
    {"name": "Luxury Sofa B", "price": 10000000, "tags": ["sofa", "premium", "large", "stylish"]},
    {"name": "Minimal Desk C", "price": 2500000, "tags": ["desk", "minimal", "compact", "work"]},
    {"name": "Ergo Chair D", "price": 4200000, "tags": ["chair", "work", "comfort", "mid-range"]},
    {"name": "Compact Shelf E", "price": 1800000, "tags": ["shelf", "storage", "compact", "budget"]},
    {"name": "Premium Lamp F", "price": 2200000, "tags": ["lamp", "premium", "work", "lighting"]},
]


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    response: str


def get_state(conversation_id: str) -> ConversationState:
    if conversation_id not in STATE_STORE:
        STATE_STORE[conversation_id] = ConversationState()
    return STATE_STORE[conversation_id]


def detect_signals(message: str) -> Dict[str, bool]:
    lowered = (message or "").lower()
    return {
        "ambiguity": any(token in lowered for token in [
            "not sure", "maybe", "whatever", "khong biet", "không biết", "chua ro", "chưa rõ"
        ]),
        "intent_change": any(token in lowered for token in [
            "actually", "instead", "doi sang", "đổi sang", "hay thoi", "hay thôi"
        ]),
        "rejection": any(token in lowered for token in [
            "don't like", "not this", "too expensive", "khong thich", "không thích", "khong muon", "không muốn"
        ]),
        "refinement": any(token in lowered for token in [
            "prefer", "compact", "premium", "budget", "work", "small", "gọn", "rẻ", "sang"
        ]),
    }


def select_behavior(signals: Dict[str, bool]) -> str:
    if signals["intent_change"]:
        return "intent_change"
    if signals["ambiguity"]:
        return "ambiguity_handling"
    if signals["rejection"]:
        return "rejection_handling"
    if signals["refinement"]:
        return "preference_refinement"
    return "general_consultation"


def update_state(state: ConversationState, message: str, behavior: str) -> None:
    lowered = (message or "").lower()
    state.last_behavior = behavior
    state.turns.append(message)

    budget_match = re.search(r"(\d{1,2})\s*(tr|triệu|million)?", lowered)
    if budget_match:
        value = int(budget_match.group(1))
        if budget_match.group(2) in {"tr", "triệu", "million"}:
            state.budget = value * 1000000

    category_keywords = ["sofa", "desk", "chair", "lamp", "shelf", "ghế", "bàn", "kệ", "đèn"]
    for keyword in category_keywords:
        if keyword in lowered:
            state.category = _normalize_category(keyword)
            break

    preference_keywords = [
        "compact", "budget", "premium", "minimal", "work", "comfort", "storage",
        "small-space", "gọn", "rẻ", "tối giản", "thoải mái"
    ]
    for keyword in preference_keywords:
        if keyword in lowered and keyword not in state.preferences:
            state.preferences.append(keyword)

    if behavior == "rejection_handling":
        rejected_value = extract_rejection(message)
        if rejected_value and rejected_value not in state.rejected:
            state.rejected.append(rejected_value)

    if behavior == "intent_change":
        # Minimal reset: keep budget, clear category-specific direction.
        state.category = None


def build_shortlist(state: ConversationState, message: str) -> List[Dict[str, Any]]:
    lowered = (message or "").lower()
    scored: List[tuple[int, Dict[str, Any]]] = []

    for product in PRODUCTS:
        score = 0
        text = " ".join([product["name"].lower(), " ".join(product["tags"]).lower()])

        if state.category and state.category in text:
            score += 4

        for preference in state.preferences:
            if preference.lower() in text:
                score += 2

        for token in lowered.split():
            if token in text:
                score += 1

        if state.budget is not None:
            if product["price"] <= state.budget:
                score += 2
            else:
                score -= 2

        for rejected in state.rejected:
            if rejected.lower() in text:
                score -= 3

        scored.append((score, product))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:3] if item[0] > -3]


def build_prompt(state: ConversationState, behavior: str, shortlist: List[Dict[str, Any]], message: str) -> str:
    return (
        f"Behavior={behavior}\n"
        f"Intent={state.intent}\n"
        f"Category={state.category}\n"
        f"Budget={state.budget}\n"
        f"Preferences={state.preferences}\n"
        f"Rejected={state.rejected}\n"
        f"Shortlist={[item['name'] for item in shortlist]}\n"
        f"User={message}"
    )


def generate_response(
    state: ConversationState,
    behavior: str,
    shortlist: List[Dict[str, Any]],
    message: str,
) -> str:
    if behavior == "ambiguity_handling":
        return _respond_ambiguity(state, shortlist)
    if behavior == "intent_change":
        return _respond_intent_change(state, shortlist)
    if behavior == "rejection_handling":
        return _respond_rejection(state, shortlist)
    if behavior == "preference_refinement":
        return _respond_refinement(state, shortlist)
    return _respond_general(state, shortlist)


def _respond_ambiguity(state: ConversationState, shortlist: List[Dict[str, Any]]) -> str:
    directions = shortlist[:2]
    if not directions:
        return "I only know a little so far. Would you like something more compact or more premium?"
    names = ", ".join(item["name"] for item in directions)
    return (
        f"So far I know your budget is {format_price(state.budget)} and your preferences lean toward "
        f"{', '.join(state.preferences[:2]) or 'a simple direction'}. "
        f"Two easy directions are {names}. Do you want the more compact one or the more value-focused one?"
    )


def _respond_intent_change(state: ConversationState, shortlist: List[Dict[str, Any]]) -> str:
    names = ", ".join(item["name"] for item in shortlist[:2]) or "a few new options"
    return (
        f"Got it, I’ll adjust the direction while keeping useful context like your budget of {format_price(state.budget)}. "
        f"Right now the best new direction is {names}. What matters more now: compact size or comfort?"
    )


def _respond_rejection(state: ConversationState, shortlist: List[Dict[str, Any]]) -> str:
    if not shortlist:
        return "Understood, I’ll avoid that direction. Do you want something more compact or more budget-friendly instead?"
    best = shortlist[0]
    return (
        f"Understood, I’ll avoid what you rejected. A better fit now is {best['name']} at {format_price(best['price'])} "
        f"because it matches {', '.join(best['tags'][:2])}. Do you want me to compare it with one alternative?"
    )


def _respond_refinement(state: ConversationState, shortlist: List[Dict[str, Any]]) -> str:
    if not shortlist:
        return "I’ve narrowed things a bit. Based on your preferences, should I focus more on compact options or premium-looking ones?"
    names = ", ".join(
        f"{item['name']} ({format_price(item['price'])})" for item in shortlist[:3]
    )
    return (
        f"Based on your preferences for {', '.join(state.preferences[:3]) or 'your current needs'}, "
        f"the top shortlist is {names}. The strongest match right now is {shortlist[0]['name']}. "
        f"Do you want a narrower shortlist?"
    )


def _respond_general(state: ConversationState, shortlist: List[Dict[str, Any]]) -> str:
    if not shortlist:
        return "I can help with that. Tell me your budget and whether you want something compact, premium, or practical."
    return (
        f"A good starting shortlist is {', '.join(item['name'] for item in shortlist[:3])}. "
        f"Which matters more to you now: budget, compact size, or comfort?"
    )


def _normalize_category(keyword: str) -> str:
    mapping = {
        "ghế": "chair",
        "bàn": "desk",
        "kệ": "shelf",
        "đèn": "lamp",
    }
    return mapping.get(keyword, keyword)


def extract_rejection(message: str) -> str:
    lowered = (message or "").lower()
    if "too expensive" in lowered:
        return "premium"
    if "không thích" in lowered or "khong thich" in lowered:
        return "rejected"
    if "not this" in lowered:
        return "rejected"
    return "rejected"


def format_price(value: Optional[int]) -> str:
    if value is None:
        return "unknown budget"
    return f"{value:,} VND"


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    state = get_state(req.conversation_id)
    signals = detect_signals(req.message)
    behavior = select_behavior(signals)
    update_state(state, req.message, behavior)
    shortlist = build_shortlist(state, req.message)
    _ = build_prompt(state, behavior, shortlist, req.message)
    response = generate_response(state, behavior, shortlist, req.message)
    return ChatResponse(response=response)


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Run POST /chat to use the demo chatbot."}
