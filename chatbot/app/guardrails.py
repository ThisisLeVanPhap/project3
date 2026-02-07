import re
from typing import Optional, Dict, Any

RX_INVENTORY = re.compile(r"\b(in stock|available|availability|left|remain)\b", re.I)
RX_BARGAIN   = re.compile(r"\b(discount|cheaper|lower price|deal|bargain)\b", re.I)
RX_HUMAN     = re.compile(r"\b(human|agent|staff|representative|call|hotline)\b", re.I)
RX_SIMILAR   = re.compile(r"\b(similar|alternative|close to|like this)\b", re.I)

def rule_reply(user_msg: str) -> Optional[Dict[str, Any]]:
    m = user_msg.strip()

    if RX_HUMAN.search(m):
        return {
            "type": "handoff",
            "reply": (
                "I can connect you with a human staff member for direct assistance. "
                "Please let me know a convenient time or share your contact details."
            )
        }

    if RX_INVENTORY.search(m):
        return {
            "type": "inventory_mock",
            "reply": (
                "I don't have real-time inventory data at the moment. "
                "To be accurate, I can ask a staff member to check availability for you. "
                "Could you share the product name or code?"
            )
        }

    if RX_BARGAIN.search(m):
        return {
            "type": "bargain_policy",
            "reply": (
                "I’m unable to adjust prices directly in chat. "
                "If you have a target budget, I can suggest similar options that fit it better."
            )
        }

    return None


def want_similar(user_msg: str) -> bool:
    return RX_SIMILAR.search(user_msg or "") is not None
