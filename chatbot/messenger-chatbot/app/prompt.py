def build_prompt(message: str, history: list[str]):
    system_hint = (
        "Bạn là trợ lý AI tiếng Việt. "
        "Hãy trả lời ngắn gọn, mạch lạc (3–5 câu), không lặp ý."
    )
    convo = f"### System:\n{system_hint}\n"
    for turn in history[-3:]:
        convo += f"### Instruction:\n{turn}\n### Response:\n...\n"
    return f"{convo}### Instruction:\n{message}\n### Response:\n"
