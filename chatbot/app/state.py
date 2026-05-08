import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

TTL_SEC = 60 * 30  # 30 minutes

@dataclass
class ConversationState:
    intent: Optional[str] = None
    recipient: Optional[str] = None
    category: Optional[str] = None
    language_mode: Optional[str] = None
    ambiguity_count: int = 0
    last_stable_intent: Optional[str] = None
    budget: Dict[str, Any] = field(
        default_factory=lambda: {"min": None, "max": None, "currency": "THB"}
    )
    preferences: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    inactive_preferences: List[str] = field(default_factory=list)
    rejected_options: List[str] = field(default_factory=list)
    rejected_attributes: List[str] = field(default_factory=list)
    shortlisted_options: List[str] = field(default_factory=list)
    selected_option: Optional[str] = None
    last_behavior: Optional[str] = None
    # --- Consultation-specific attributes ---
    room_type: Optional[str] = None          # living room, bedroom, dining room, apartment, etc.
    room_size_sqm: Optional[float] = None   # approximate size in square meters
    budget_range: Optional[str] = None      # low / medium / high or specific range
    style_preference: Optional[str] = None  # modern, minimal, classic, etc.
    product_type: Optional[str] = None      # sofa, bed, table, wardrobe, etc.

@dataclass
class ConvState:
    updated_at: float = field(default_factory=lambda: time.time())
    stage: str = "discover"  # discover | propose | compare | close | handoff
    slots: Dict[str, Any] = field(default_factory=dict)
    last_question: Optional[str] = None
    last_answer: Optional[str] = None
    conversation_state: ConversationState = field(default_factory=ConversationState)

_STORE: Dict[str, ConvState] = {}

def get_state(conversation_id: Optional[str]) -> ConvState:
    cid = conversation_id or "default"
    now = time.time()
    st = _STORE.get(cid)
    if st and (now - st.updated_at) < TTL_SEC:
        return st
    st = ConvState()
    _STORE[cid] = st
    return st

def reset_state(conversation_id: str):
    if conversation_id in _STORE:
        del _STORE[conversation_id]

def save_turn(conversation_id: Optional[str], q: str, a: str):
    st = get_state(conversation_id)
    st.updated_at = time.time()
    st.last_question = q
    st.last_answer = a

def set_stage(conversation_id: Optional[str], stage: str):
    st = get_state(conversation_id)
    st.updated_at = time.time()
    st.stage = stage
