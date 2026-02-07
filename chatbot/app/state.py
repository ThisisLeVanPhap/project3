import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

TTL_SEC = 60 * 30  # 30 minutes

@dataclass
class ConvState:
    updated_at: float = field(default_factory=lambda: time.time())
    stage: str = "discover"  # discover | propose | compare | close | handoff
    slots: Dict[str, Any] = field(default_factory=dict)
    last_question: Optional[str] = None
    last_answer: Optional[str] = None

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
