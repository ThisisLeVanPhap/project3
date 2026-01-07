from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from peft import PeftModel
import torch
import os


def get_pipeline(
    base: str,
    adapter: str = None,
    tokenizer_path: str = None,
    device: int | None = None,
):
    """
    base: tên/path base model, ví dụ: "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    adapter: path đến thư mục LoRA, ví dụ: "out/lora_adapter"
    tokenizer_path:
        - Nếu None:
            + Nếu có adapter -> thử dùng "<adapter>/../tokenizer" (ví dụ "out/tokenizer")
            + Nếu không có -> dùng tokenizer của base model
        - Nếu không None -> cố gắng dùng path đó (thử fast, nếu lỗi -> slow, nếu vẫn lỗi -> fallback base)
    device:
        - None  -> tự chọn: 0 nếu có GPU, -1 nếu chỉ CPU
        - 0,1.. -> GPU cụ thể
        - -1    -> CPU
    """

    # --------- Quyết định tokenizer_path ----------
    if tokenizer_path is None:
        if adapter:
            # adapter = "out/lora_adapter" -> base_out = "out"
            base_out = os.path.dirname(adapter)
            maybe_tok = os.path.join(base_out, "tokenizer")
            if os.path.isdir(maybe_tok):
                tokenizer_path = maybe_tok
            else:
                tokenizer_path = base
        else:
            tokenizer_path = base

    print(f"[model_loader] Want to use tokenizer from: {tokenizer_path}")

    tok = None

    # --------- Thử fast tokenizer ----------
    try:
        print("[model_loader] Trying FAST tokenizer...")
        tok = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=True)
    except Exception as e_fast:
        print(f"[model_loader] FAST tokenizer failed: {e_fast}")
        # --------- Thử slow tokenizer ----------
        try:
            print("[model_loader] Trying SLOW tokenizer...")
            tok = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=False)
        except Exception as e_slow:
            print(f"[model_loader] SLOW tokenizer failed: {e_slow}")
            # --------- Fallback về base model tokenizer ----------
            print(f"[model_loader] Fallback to BASE tokenizer: {base}")
            tok = AutoTokenizer.from_pretrained(base, use_fast=True)

    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # --------- Load base model ----------
    print(f"[model_loader] Loading base model: {base}")
    base_model = AutoModelForCausalLM.from_pretrained(
        base,
        torch_dtype=torch.float32 if not torch.cuda.is_available() else torch.float16,
    )

    # --------- Gắn LoRA nếu có ----------
    if adapter and os.path.isdir(adapter):
        print(f"[model_loader] Applying LoRA from: {adapter}")
        model = PeftModel.from_pretrained(base_model, adapter)
    else:
        print("[model_loader] No valid adapter provided, using base model only.")
        model = base_model

    # --------- Chọn device ----------
    if device is None:
        device = 0 if torch.cuda.is_available() else -1

    print(f"[model_loader] Using device: {device}")
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tok,
        device=device,
    )
    return pipe
