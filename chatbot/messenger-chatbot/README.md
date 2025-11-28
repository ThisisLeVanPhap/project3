# Messenger Chatbot (FastAPI + LoRA)


## 0) Requirements
- Python 3.11, Git
- (Optional) GPU + PyTorch


## 1) Setup
```bash
git clone <this repo>
cd messenger-chatbot
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env

## 2) fine-tune xong mô hình LoRA
python training/train_lora.py

## 3) server FastAPI (chatbot):
uvicorn app.server:app --host 0.0.0.0 --port 8000

## 4) thử API bằng Swagger UI
http://localhost:8000/docs