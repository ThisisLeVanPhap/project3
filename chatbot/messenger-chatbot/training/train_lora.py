from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling, Trainer
from peft import LoraConfig, get_peft_model

BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
DATA_TRAIN = "training/data/train.jsonl"
DATA_VAL = "training/data/val.jsonl"
OUT_DIR = "out"

def format_sample(example):
    prompt = f"### Instruction:\n{example['instruction']}\n### Input:\n{example.get('input','')}\n### Response:\n"
    return prompt + example["output"]

def main():
    ds = load_dataset("json", data_files={"train": DATA_TRAIN, "val": DATA_VAL})

    tok = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"  # an toàn cho causal LM

    def tokenize(ex):
        text = format_sample(ex)
        # KHÔNG gán labels ở đây
        return tok(text, truncation=True, max_length=1024)
        # (padding để collator xử lý, không cần padding=True ở đây)

    ds_tok = ds.map(tokenize, remove_columns=ds["train"].column_names)

    # Collator này sẽ tự:
    # - pad các field (input_ids, attention_mask, ...)
    # - tạo labels = input_ids khi mlm=False
    collator = DataCollatorForLanguageModeling(tok, mlm=False)

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL)
    lora_cfg = LoraConfig(
        r=16, lora_alpha=32,
        target_modules=["q_proj","v_proj","k_proj","o_proj"],
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_cfg)
    model.config.pad_token_id = tok.pad_token_id  # tránh warning

    args = TrainingArguments(
        output_dir=OUT_DIR,
        num_train_epochs=2,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        learning_rate=2e-4,
        fp16=False,
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=200,
        save_steps=200,
        save_total_limit=2,
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