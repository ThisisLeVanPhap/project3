# Chatbot (FastAPI + LoRA)


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
```
## 2) fine-tune xong mô hình LoRA
python training/train_lora.py

## 3) server FastAPI (chatbot):
uvicorn app.server:app --host 0.0.0.0 --port 8000

## 4) thử API bằng Swagger UI
http://localhost:8000/docs

# Backend:

## 🚀 Cài đặt & Chạy Backend

### 1️⃣ Yêu cầu hệ thống
- **Java 21**
- **Maven 3.9+**
- **PostgreSQL 14+** hoặc Docker
- Git (tuỳ chọn)

---

## 2️⃣ Chuẩn bị Database

### 👉 Cách 1 — PostgreSQL local
```bash
createdb global_admin
```

## CHyaj bằng maven:
```bash
mvn spring-boot:run
```

## Tài liệu API

Swagger UI: http://localhost:8080/swagger-ui

OpenAPI JSON: http://localhost:8080/v3/api-docs

OpenAPI YAML: http://localhost:8080/v3/api-docs.yaml

## Test bằng curl:

1. Tạo tenant:
```
curl -X POST http://localhost:8080/api/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"code":"demo","name":"Demo Tenant"}'
```

2. Tạo chatbot:
```
curl -X POST http://localhost:8080/api/chatbots \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bot Demo","channel":"web","personaJson":"{\"tone\":\"ấm áp\"}"}'
```

3. Bắt đầu cuộc hội thoại
```
curl -X POST http://localhost:8080/api/chat/start \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"chatbotId":"<CHATBOT_ID>"}'
```

4. Gửi tin nhắn
```
curl -X POST http://localhost:8080/api/chat/send \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"conversationId":"<CONV_ID>","message":"Xin tư vấn sản phẩm"}'
```