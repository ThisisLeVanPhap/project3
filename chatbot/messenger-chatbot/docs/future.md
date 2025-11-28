Train LoRA trên GPU (cloud)
⇒ merge + quantize
⇒ chạy inference trên server CPU rẻ (hoặc ngay laptop của bạn).

----
1. 
# activate venv như README của bạn
python training/build_dataset.py

Nó sẽ tạo:

training/data/train.jsonl

training/data/val.jsonl

2. Sau đó chạy fine-tune:

python training/train_lora.py

3. Xong training, start server:

uvicorn app.server:app --host 0.0.0.0 --port 8000

4. Vào Swagger (/docs) hoặc Postman, gửi câu hỏi tiếng Anh về wood product, kiểm tra câu trả lời đã “đúng chủ đề” hơn base model chưa.