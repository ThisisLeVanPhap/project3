import re
from typing import Dict, Any, Tuple

RX_BUDGET = re.compile(r"\b(\$|usd)\s*([0-9]{2,5})\b|under\s*\$?\s*([0-9]{2,5})\b", re.I)
RX_SMALL  = re.compile(r"\b(small|tiny|compact|studio|apartment)\b", re.I)
RX_PETS   = re.compile(r"\b(pet|dog|cat)\b", re.I)
RX_KIDS   = re.compile(r"\b(kid|child|toddler|baby)\b", re.I)
RX_STYLE  = re.compile(r"\b(modern|minimal|classic|scandinavian|boho|industrial)\b", re.I)

def extract_slots(text: str) -> Dict[str, Any]:
    t = text or ""
    slots: Dict[str, Any] = {}

    m = RX_BUDGET.search(t)
    if m:
        num = m.group(2) or m.group(3)
        if num:
            slots["budget_usd"] = int(num)

    if RX_SMALL.search(t): slots["space"] = "small"
    if RX_PETS.search(t):  slots["pets"] = True
    if RX_KIDS.search(t):  slots["kids"] = True

    m2 = RX_STYLE.search(t)
    if m2:
        slots["style"] = m2.group(1).lower()

    return slots

def next_stage(current: str, slots: Dict[str, Any], user_text: str) -> str:
    # Minimal flow logic
    if re.search(r"\b(talk to|human|agent|staff)\b", user_text, re.I):
        return "handoff"
    if current == "discover":
        # once we have at least 1-2 signals, move to propose
        if len(slots) >= 1:
            return "propose"
    if current == "propose":
        if re.search(r"\b(compare|difference|vs)\b", user_text, re.I):
            return "compare"
        if re.search(r"\b(buy|order|checkout|purchase)\b", user_text, re.I):
            return "close"
    return current

def build_sales_prefix(stage: str, slots: Dict[str, Any]) -> str:
    # This is injected into system prompt to force continuity.
    parts = []
    if slots.get("space") == "small": parts.append("Customer has a small space.")
    if slots.get("pets"): parts.append("Customer has pets.")
    if slots.get("kids"): parts.append("Customer has kids.")
    if "budget_usd" in slots: parts.append(f"Customer budget is about ${slots['budget_usd']}.")
    if "style" in slots: parts.append(f"Customer prefers {slots['style']} style.")

    context = " ".join(parts) if parts else "No specific preferences captured yet."

    stage_instr = {
        "discover": "Goal: ask 2-3 clarifying questions to understand needs, then offer 1 gentle suggestion.",
        "propose":  "Goal: propose 1-2 suitable options based on captured preferences, then ask 1 follow-up question.",
        "compare":  "Goal: compare options using only provided KB context; if missing, ask for product links/names.",
        "close":    "Goal: confirm key preferences and ask for next step (contact details or connect to staff). Do not claim you can place orders.",
        "handoff":  "Goal: politely offer to connect the customer with a human staff member.",
    }[stage]

    return (
        f"[Sales Flow]\n"
        f"Stage: {stage}\n"
        f"Known customer context: {context}\n"
        f"{stage_instr}\n\n"
        "HARD RULES:\n"
        "- Do NOT mention a specific product name unless the user explicitly provided it.\n"
        "- Do NOT invent prices, delivery times, refunds, or return windows. Use placeholders only: <DELIVERY_TIME>, <RETURN_POLICY>, <PRICE_RANGE>.\n"
        "- If store data is missing, apologize and offer staff handoff.\n"
    )
