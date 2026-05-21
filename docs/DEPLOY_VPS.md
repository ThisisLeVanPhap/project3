# Deploy VPS Ubuntu với Docker Compose

Hướng dẫn deploy hệ thống chatbot trên VPS Ubuntu sử dụng Claude API làm provider chính.

## 1. Cấu hình VPS khuyến nghị

### Khuyến nghị (production/demo nhẹ)
- **CPU**: 4 vCPU
- **RAM**: 8GB
- **Storage**: 80GB SSD
- **OS**: Ubuntu 22.04 LTS hoặc 24.04 LTS
- **Network**: Public IP hoặc domain đã trỏ về VPS

### Tối thiểu (demo single-user)
- **CPU**: 2 vCPU
- **RAM**: 4GB
- **Storage**: 50GB SSD
- **Lưu ý**: Chỉ phù hợp demo, không chạy fallback local model

## 2. Cài đặt Docker trên Ubuntu

```bash
# Update package
sudo apt update

# Cài dependencies
sudo apt install -y ca-certificates curl gnupg lsb-release

# Thêm Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Thêm Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cài Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify Docker installed
docker --version
docker compose version
```

## 3. Clone repository

```bash
# Clone repo (thay thế bằng URL repo của bạn)
git clone https://github.com/your-org/your-repo.git
cd your-repo

# Hoặc nếu dùng SSH
git clone git@github.com:your-org/your-repo.git
cd your-repo
```

## 4. Tạo file .env từ .env.example

```bash
cp .env.example .env
```

## 5. Cấu hình .env bắt buộc cho VPS

Chỉnh sửa `.env` với các giá trị sau:

```bash
# Postgres (giữ nguyên)
POSTGRES_DB=global_admin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-strong-password>
POSTGRES_PORT=5432

# Ports
APP_PORT=8080
CHATBOT_PORT=8000

# Python LLM (Docker internal)
PYTHON_LLM_BASE_URL=http://chatbot-api:8000

# Model settings (không cần local model)
CHATBOT_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct
CHATBOT_TEST_MODE=0
MARKET_PRICE_PROVIDER=

# Claude API (SYSTEM-LEVEL PROVIDER - BẮT BUỘC)
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_API_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_KEY=<your-anthropic-api-key>

# Token limits
MAX_NEW_TOKENS=256
CLAUDE_MAX_NEW_TOKENS=768
LOCAL_FALLBACK_MAX_TOKENS=128
TEMPERATURE=0.7
TOP_P=0.9
TOP_K=50

# Local fallback (DISABLED cho VPS CPU-only)
FALLBACK_TO_LOCAL_ENABLED=false
LOCAL_FALLBACK_TIMEOUT_SECONDS=45

# Messenger/Telegram
MESSENGER_VERIFY_TOKEN=woodchat_secret
```

**Lưu ý**:
- **KHÔNG commit `.env`** lên git
- `ANTHROPIC_API_KEY` là bắt buộc để hệ thống hoạt động
- `FALLBACK_TO_LOCAL_ENABLED=false` để skip load Qwen model (tiết kiệm RAM/startup time)

## 6. Build và start containers

```bash
docker compose up -d --build
```

Expected startup time: **2-5 phút** (chủ yếu build Docker images, không có model download)

## 7. Kiểm tra deploy thành công

### Kiểm tra containers đang chạy
```bash
docker compose ps
```

Expected output:
```
NAME              STATUS
app-1             Up
chatbot-api-1     Up
postgres-1        Up
```

### Kiểm tra logs chatbot-api (quan trọng)
```bash
docker compose logs chatbot-api --tail=100
```

Expected log (Claude mode - không load Qwen):
```
[warmup] Claude API available, skipping local model warmup (lazy load on provider=local)
```

**KHÔNG thấy** log load Qwen model như:
- `[model_loader] Loading base model: Qwen/...`
- `Downloading model...`

### Kiểm tra logs Spring Boot app
```bash
docker compose logs app --tail=100
```

Expected log:
```
LLM runtimeMode=external_http baseUrl=http://chatbot-api:8000
Started [AppName] in XX.XXX seconds
```

### Test Python health endpoint
```bash
curl http://SERVER_IP:8000/healthz
```

Expected response:
```json
{"status":"ready","ready":true,"cached_pipelines":0,"kb_loaded":true,...}
```

### Test Spring Boot endpoint
```bash
curl http://SERVER_IP:8080/
```

hoặc check price-check page:
```bash
curl http://SERVER_IP:8080/price-check/
```

### Kiểm tra Flyway migrations
```bash
docker compose exec postgres psql -U postgres -d global_admin -c "select version, description, success from flyway_schema_history where success=true order by installed_rank desc limit 10;"
```

Expected: Migration mới nhất (V26) nên có `success=true`

## 8. Database management

### Backup database
```bash
# Backup toàn bộ database volume
docker compose exec postgres pg_dump -U postgres global_admin > backup_$(date +%Y%m%d).sql

# Hoặc backup volume trực tiếp
docker run --rm -v your-project_postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup-$(date +%Y%m%d).tar.gz /data
```

### Restore database
```bash
# Restore từ SQL file
cat backup_20260101.sql | docker compose exec -T postgres psql -U postgres -d global_admin

# Restore từ volume backup
docker run --rm -v your-project_postgres-data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup-20260101.tar.gz -C /
```

### Check database size
```bash
docker compose exec postgres psql -U postgres -d global_admin -c "select datname, pg_size_pretty(pg_database_size(datname)) as size from pg_database where datname='global_admin';"
```

## 9. Messenger/Telegram Webhook

### Local development (cần ngrok)
```bash
# Chạy ngrok
ngrok http 8080

# Cập nhật webhook URL với ngrok URL
# Ví dụ: https://abc123.ngrok.io/api/messenger/webhook
```

### VPS deployment (KHÔNG cần ngrok)
VPS có public IP/domain nên không cần ngrok:

```bash
# Messenger webhook URL
http://SERVER_IP:8080/api/messenger/webhook

# Hoặc với domain
https://your-domain.com/api/messenger/webhook

# Telegram webhook URL
http://SERVER_IP:8080/api/telegram/webhook

# Hoặc với domain
https://your-domain.com/api/telegram/webhook
```

**Cấu hình webhook**:
1. Setup Messenger/Telegram trong admin UI
2. Webhook URL trỏ về VPS public IP/domain
3. Verify token: `woodchat_secret` (hoặc custom trong `.env`)

## 10. Domain và HTTPS

### Demo nhanh (HTTP chỉ)
Sử dụng public IP trực tiếp:
```
http://SERVER_IP:8080
```

**Hạn chế**:
- Messenger yêu cầu HTTPS cho production
- Không an toàn cho sensitive data

### HTTPS với domain + Caddy (đơn giản nhất)

1. **Install Caddy**:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

2. **Cấu hình Caddyfile**:
```bash
sudo nano /etc/caddy/Caddyfile
```

```
your-domain.com {
    reverse_proxy localhost:8080
}

your-domain.com:8000 {
    reverse_proxy localhost:8000
}
```

3. **Restart Caddy**:
```bash
sudo systemctl restart caddy
sudo systemctl enable caddy
```

### HTTPS với Nginx + Let's Encrypt

1. **Install Nginx + Certbot**:
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

2. **Cấu hình Nginx server block**:
```bash
sudo nano /etc/nginx/sites-available/chatbot
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **Get SSL certificate**:
```bash
sudo certbot --nginx -d your-domain.com
```

## 11. Update code và redeploy

```bash
# Pull code mới
git pull

# Rebuild và restart containers
docker compose up -d --build

# Check logs
docker compose logs -f
```

## 12. Troubleshooting

### Container không start
```bash
# Check logs chi tiết
docker compose logs chatbot-api
docker compose logs app

# Restart services
docker compose restart chatbot-api app
```

### Database connection error
```bash
# Check postgres health
docker compose exec postgres pg_isready -U postgres

# Check Spring app env vars
docker compose exec app env | grep SPRING_DATASOURCE
```

### Chatbot API timeout
```bash
# Check Claude API connectivity
docker compose exec chatbot-api curl -s https://api.anthropic.com/v1/overview

# Check env vars
docker compose exec chatbot-api env | grep CLAUDE
```

### Out of memory (OOM)
```bash
# Check memory usage
docker stats

# Nếu RAM < 4GB, disable local fallback completely
# FALLBACK_TO_LOCAL_ENABLED=false
```

## 13. Security checklist

- [ ] `.env` KHÔNG được commit lên git
- [ ] `POSTGRES_PASSWORD` là password mạnh
- [ ] `ANTHROPIC_API_KEY` được bảo mật
- [ ] Firewall chỉ mở ports cần thiết (80, 443, 8080 nếu cần)
- [ ] Enable automatic security updates cho Ubuntu
- [ ] Backup database định kỳ

## 14. Ports cần mở

| Port | Protocol | Purpose |
|------|----------|---------|
| 80   | HTTP     | Caddy/Nginx redirect |
| 443  | HTTPS    | Caddy/Nginx (recommended) |
| 8080 | HTTP     | Spring Boot app (optional) |
| 8000 | HTTP     | Python chatbot (internal only) |

**Lưu ý**: Port 8000 và 5432 nên chỉ cho internal network access.

## 15. Quick reference

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Check status
docker compose ps

# View logs
docker compose logs -f

# Restart single service
docker compose restart chatbot-api

# View resource usage
docker stats

# Cleanup unused images
docker image prune -f

# Backup database
docker compose exec postgres pg_dump -U postgres global_admin > backup.sql
```

---

**Tóm tắt**: Hệ thống này được thiết kế để chạy với Claude API làm provider chính, không yêu cầu GPU hoặc load local model trên VPS CPU-only. Startup time nhanh (<5 phút), resource usage thấp (<2GB RAM khi idle).