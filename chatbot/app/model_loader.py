# app/model_loader.py
# Lazy imports inside get_pipeline() — torch/transformers are only loaded
# when local AI provider is actually used, not at module import time.


def get_pipeline(
    base: str,
    adapter: str = None,
    tokenizer_path: str = None,
    device: int | None = None,
):
    """
    base: tên/path base model, ví dụ HuggingFace model id hoặc path snapshot local
    adapter: deprecated; ignored by runtime
    tokenizer_path: path tokenizer (nếu None thì tự suy ra như cũ)
    device:
        - None  -> tự chọn: 0 nếu có GPU, -1 nếu chỉ CPU
        - 0,1.. -> GPU cụ thể
        - -1    -> CPU
    """
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch

    # --------- Quyết định tokenizer_path ----------
    if tokenizer_path is None:
        tokenizer_path = base

    print(f"[model_loader] Want to use tokenizer from: {tokenizer_path}")

    # --------- Load tokenizer (fast -> slow -> fallback) ----------
    tok = None
    try:
        print("[model_loader] Trying FAST tokenizer...")
        tok = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=True)
    except Exception as e_fast:
        print(f"[model_loader] FAST tokenizer failed: {e_fast}")
        try:
            print("[model_loader] Trying SLOW tokenizer...")
            tok = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=False)
        except Exception as e_slow:
            print(f"[model_loader] SLOW tokenizer failed: {e_slow}")
            print(f"[model_loader] Fallback to BASE tokenizer: {base}")
            tok = AutoTokenizer.from_pretrained(base, use_fast=True)

    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # --------- Chọn device ----------
    if device is None:
        device = 0 if torch.cuda.is_available() else -1

    print(f"[model_loader] Using device: {device}")

    # --------- Load base model ----------
    print(f"[model_loader] Loading base model: {base}")

    use_gpu = (device is not None and device >= 0 and torch.cuda.is_available())
    dtype = torch.float16 if use_gpu else torch.float32

    base_model = AutoModelForCausalLM.from_pretrained(
        base,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )

    if use_gpu:
        base_model = base_model.to("cuda")

    # Adapter support is intentionally disabled; local fallback uses the base model.
    if adapter:
        print("[model_loader] Adapter path was provided but is ignored; using base model only.")
    model = base_model

    # --------- Pipeline ----------
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tok,
        device=device,  # -1 CPU
    )
    return pipe
