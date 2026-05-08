import json
from typing import Any, Dict, List


_BEHAVIOR_INSTRUCTIONS = {
    "preference_refinement": (
        "- Ask ONE smart clarifying question.\n"
        "- If enough info is already available, suggest 2-3 product directions.\n"
        "- Focus on refining preferences, use case, or priorities.\n"
        "- If preferences exist, reference 1-2 of them directly."
    ),
    "budget_adjustment": (
        "- Acknowledge the new budget.\n"
        "- Explain the main trade-offs caused by the change.\n"
        "- Adjust recommendations to fit the updated budget.\n"
        "- If preferences exist, reference 1-2 of them directly."
    ),
    "intent_change": (
        "- Acknowledge that the user's intent or recipient changed.\n"
        "- Keep only still-valid preferences such as budget or general style.\n"
        "- Ask 1 follow-up question or suggest a new direction.\n"
        "- If preferences exist, reference 1-2 of them directly."
    ),
    "ambiguity_handling": (
        "- The user is uncertain, hesitant, or inconsistent.\n"
        "- Do NOT force a recommendation too early.\n"
        "- Summarize what is known so far.\n"
        "- Offer 2 compact directions rather than many choices.\n"
        "- Ask one narrowing question.\n"
        "- If preferences exist, reference 1-2 of them directly."
    ),
    "conversation_drift_recovery": (
        "- The user wants to return to an earlier direction.\n"
        "- Summarize the earlier direction briefly using still-valid preferences.\n"
        "- Restore the relevant recommendation path if possible.\n"
        "- Continue naturally without restarting the whole conversation.\n"
        "- Ask at most one short follow-up question."
    ),
    "rejection_handling": (
        "- Acknowledge the rejection.\n"
        "- Infer the likely reason from the message, or ask why if unclear.\n"
        "- Provide better alternatives based on the updated preference signal.\n"
        "- If preferences exist, reference 1-2 of them directly."
    ),
    "shortlist_finalization": (
        "- Give 1-3 options.\n"
        "- Compare them briefly.\n"
        "- Recommend the best fit when possible.\n"
        "- Keep the interaction consultative, not transactional.\n"
        "- Ask at most one natural follow-up question.\n"
        "- If preferences exist, reference 1-2 of them directly.\n"
        "- When shortlist exists, explain why one item fits better than another."
    ),
}


def build_prompt(
    behavior: str,
    state: Dict[str, Any],
    user_message: str,
    retrieved_docs: List[str],
    shortlist: List[Dict[str, str]],
) -> str:
    state_json = json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True)
    retrieved_text = "\n".join(retrieved_docs) if retrieved_docs else "No retrieved context."
    shortlist_text = _format_shortlist(shortlist)
    profile_summary = _build_user_profile_summary(state)
    language_instruction = _build_language_instruction(state.get("language_mode"), user_message)
    behavior_instruction = _BEHAVIOR_INSTRUCTIONS.get(
        behavior,
        _BEHAVIOR_INSTRUCTIONS["preference_refinement"],
    )

    return f"""You are a helpful shopping assistant.

Behavior: {behavior}

Conversation state:
{state_json}

Shortlist:
{shortlist_text}

Retrieved context:
{retrieved_text}

User message:
{user_message}

User profile summary:
{profile_summary}

Instructions:
{behavior_instruction}
{language_instruction}

Rules:
- Be natural and conversational
- Be concise
- Do NOT hallucinate products
- Use context if available
- Prefer using shortlist items
- Do NOT invent products outside shortlist
- Always consider the user profile summary when responding
- Reuse known preferences instead of asking again
- Avoid suggesting options that match rejected attributes
- If the user was unclear earlier, handle uncertainty patiently
- If enough information already exists, do not repeat the same questions
- When the user is unclear, offer 2 compact directions
- When the user changes mind repeatedly, acknowledge the change naturally and keep only still-valid preferences
- Keep answers short and easy to follow
- When recommending, explicitly connect the suggestion to budget, preferences, and use case
- If the user previously rejected something, do NOT suggest similar items again unless unavoidable
- If unavoidable, explain briefly why it is still shown
- When shortlist exists, prefer items matching preferences and mention why item A fits better than item B
- Ask at most ONE question

Response:
"""


def _format_shortlist(shortlist: List[Dict[str, str]]) -> str:
    if not shortlist:
        return "Shortlist: Not available"
    return "\n".join(
        f"- {item.get('title', '')}: {item.get('summary', '')} ({item.get('url', '')})"
        for item in shortlist
    )


def _build_user_profile_summary(state: Dict[str, Any]) -> str:
    lines: List[str] = []

    intent = state.get("intent")
    category = state.get("category")
    budget = _format_budget(state.get("budget"))
    preferences = _top_items(state.get("preferences", []), 3)
    rejected = _top_items(state.get("rejected_attributes", []), 3)

    if intent:
        lines.append(f"- Intent: {intent}")
    if category:
        lines.append(f"- Category: {category}")
    if budget:
        lines.append(f"- Budget: {budget}")
    if preferences:
        lines.append(f"- Key preferences: {', '.join(preferences)}")
    if rejected:
        lines.append(f"- Avoid: {', '.join(rejected)}")

    if not lines:
        return "- No stable profile captured yet."
    return "\n".join(lines)


def _format_budget(budget: Any) -> str:
    if not isinstance(budget, dict):
        return ""
    min_value = budget.get("min")
    max_value = budget.get("max")
    currency = budget.get("currency") or "THB"
    if min_value is None and max_value is None:
        return ""
    if min_value is not None and max_value is not None:
        return f"{min_value}-{max_value} {currency}"
    if max_value is not None:
        return f"up to {max_value} {currency}"
    return f"from {min_value} {currency}"


def _top_items(items: List[Any], limit: int) -> List[str]:
    values: List[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def _build_language_instruction(language_mode: Any, user_message: str) -> str:
    latest = (user_message or "").strip()
    if language_mode == "vi":
        return "- Reply in Vietnamese.\n- Keep tone natural and consultative."
    if language_mode == "mixed":
        dominant = "Vietnamese" if _looks_more_vietnamese(latest) else "English"
        return (
            "- Reply in the same language as the latest user message.\n"
            f"- The latest message is mixed, so prefer {dominant} as the dominant language.\n"
            "- Keep tone natural and consultative."
        )
    return "- Reply in English.\n- Keep tone natural and consultative."


def _looks_more_vietnamese(text: str) -> bool:
    lowered = text.lower()
    vi_markers = ["mình", "muốn", "cái", "cho", "với", "không", "được", "này", "kia"]
    return any(marker in lowered for marker in vi_markers)
