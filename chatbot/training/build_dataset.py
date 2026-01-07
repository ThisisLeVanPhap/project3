import csv
import json
from pathlib import Path

# Đổi tên file CSV ở đây cho đúng với file bạn tải về
TRAIN_CSV = Path("training/data/QA-wood-products.csv")   # dataset chính
VAL_CSV   = Path("training/data/Eval_QA_Wood.csv")       # dataset đánh giá

TRAIN_JSONL = Path("training/data/train.jsonl")
VAL_JSONL   = Path("training/data/val.jsonl")

REQUIRED_COLS = ["Instruction", "Question", "Answer"]


def convert_csv_to_jsonl(csv_path: Path, jsonl_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file CSV: {csv_path}")

    print(f"[*] Đang convert {csv_path} -> {jsonl_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f_in, \
         jsonl_path.open("w", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)
        # Kiểm tra đủ cột
        for col in REQUIRED_COLS:
            if col not in reader.fieldnames:
                raise ValueError(
                    f"CSV {csv_path} thiếu cột '{col}'. "
                    f"Các cột hiện có: {reader.fieldnames}"
                )

        count = 0
        for row in reader:
            instruction = (row["Instruction"] or "").strip()
            question = (row["Question"] or "").strip()
            answer = (row["Answer"] or "").strip()

            if not question or not answer:
                # bỏ các dòng bị thiếu dữ liệu
                continue

            record = {
                "instruction": instruction,
                "input": question,
                "output": answer,
            }

            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"[+] Đã ghi {count} dòng vào {jsonl_path}")


def main():
    # Tạo thư mục nếu chưa có
    TRAIN_JSONL.parent.mkdir(parents=True, exist_ok=True)

    convert_csv_to_jsonl(TRAIN_CSV, TRAIN_JSONL)
    convert_csv_to_jsonl(VAL_CSV, VAL_JSONL)
    print("[✓] Hoàn thành convert CSV -> JSONL.")


if __name__ == "__main__":
    main()
