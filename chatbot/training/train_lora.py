from datasets import load_dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, DataCollatorForLanguageModeling, Trainer
)
from peft import LoraConfig, get_peft_model

BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
DATA_TRAIN = "training/data/train.jsonl"
DATA_VAL = "training/data/val.jsonl"
OUT_DIR = "out"

def format_sample(example):
    instruction = example.get("instruction", "").strip()
    inp = example.get("input", "").strip()
    out = example["output"].strip()

    # format thống nhất với server (User/Assistant) để đỡ lệch distribution
    parts = ["### System:\nBạn là trợ lý AI tiếng Việt.\n"]
    if instruction:
        parts.append(f"### User:\n{instruction}\n")
    if inp:
        parts.append(f"### User:\n{inp}\n")
    parts.append("### Assistant:\n")
    return "".join(parts) + out

def main():
    ds = load_dataset("json", data_files={"train": DATA_TRAIN, "val": DATA_VAL})

    tok = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    tok.pad_token = tok.pad_token or tok.eos_token
    tok.padding_side = "right"

    def tokenize(ex):
        text = format_sample(ex)
        return tok(text, truncation=True, max_length=1024)

    ds_tok = ds.map(tokenize, remove_columns=ds["train"].column_names)
    collator = DataCollatorForLanguageModeling(tok, mlm=False)

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL)
    lora_cfg = LoraConfig(
        r=16, lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.config.pad_token_id = tok.pad_token_id

    args = TrainingArguments(
        output_dir=OUT_DIR,
        num_train_epochs=2,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        learning_rate=2e-4,
        fp16=False,
        logging_steps=50,
        evaluation_strategy="steps",  # ✅ đúng tên
        eval_steps=200,
        save_steps=200,
        save_total_limit=2,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds_tok["train"],
        eval_dataset=ds_tok["val"],
        tokenizer=tok,
        data_collator=collator,
    )
    trainer.train()
    model.save_pretrained(f"{OUT_DIR}/lora_adapter")
    tok.save_pretrained(f"{OUT_DIR}/tokenizer")

if __name__ == "__main__":
    main()
