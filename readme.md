# Project Setup (Demo End-to-End)

This project is a multi-tenant sales-assistant chatbot system:
- **Spring Boot** (multi-tenant backend + Messenger/Telegram webhooks)
- **Python FastAPI** model server spawned automatically by Spring per tenant
- **RAG KB** built by scraping store websites and chunking into `kb/<shop>/chunks.jsonl`

> You do NOT need to run `uvicorn` manually. Spring will spawn the Python model server automatically when a message arrives.

---

## 1) Install Python runtime dependencies (chatbot/)

From repo root and install runtime dependencies (NO training dependencies required):
```bash
cd chatbot
pip install -r requirements.txt
```

## 2) Build KB (Scrape + Build Index)
Article
```bash
python tools/scrape_site.py article kb/article/raw_urls.txt kb/article/docs.jsonl
python tools/build_kb.py kb/article/docs.jsonl kb/article/chunks.jsonl kb/article/index.json
```

Castlery

```bash
python tools/scrape_site.py castlery kb/castlery/raw_urls.txt kb/castlery/docs.jsonl
python tools/build_kb.py kb/castlery/docs.jsonl kb/castlery/chunks.jsonl kb/castlery/index.json
```
Result:

kb/<shop>/chunks.jsonl

kb/<shop>/index.json

## 3) Run Spring Boot (IntelliJ) + set ENV
Open multitenant/ in IntelliJ, import Maven, then run ApiApplication.java.

### 3.1) Required environment variables (Run Configuration)
Set these in IntelliJ: Run → Edit Configurations → Environment variables

```env
# Use the Python that has installed chatbot/requirements.txt
PYTHON_BIN=<ABSOLUTE_PATH_TO>\chatbot\.venv\Scripts\python.exe

# Folder path to the "chatbot" directory (where app/server.py exists)
MODEL_SERVER_DIR=<ABSOLUTE_PATH_TO>\chatbot

# (Optional) Messenger verify token (must match what you set in Meta webhook settings)
MESSENGER_VERIFY_TOKEN=woodchat_secret
```
Notes:

+ PYTHON_BIN must be the same Python where you installed chatbot/requirements.txt.

+ MODEL_SERVER_DIR must point to the chatbot/ folder (contains app/server.py).

## 4) Database + Tenant/Chatbot + Messenger/Telegram bindings
### 4.1 Create database
Create a PostgreSQL database named ```global_admin``` and update ```multitenant/src/main/resources/application.yml``` (or application.properties) to match your local DB credentials.

Spring Boot will run Flyway migrations automatically on startup.

### 4.2 Create a tenant (get API key)
Call the admin API to create tenant (example):
```bash
POST /api/admin/tenants
```

```json
{ "code": "demo", "name": "Demo Tenant" }
```
Response returns:

+ tenantId

+ apiKey

### 4.3 Set tenant KB directory
In DB table tenants, set kb_dir for that tenant, e.g.:

For Article: .../chatbot/kb/article

For Castlery: .../chatbot/kb/castlery

(Each tenant points to exactly one KB folder.)

4.4 Create chatbot instance
Call:
```
POST /api/chatbots
```
Payload example:

```json
{
  "name": "Article Sales Bot",
  "channel": "messenger",
  "personaJson": "{\"tone\":\"friendly\"}"
}
```
Then update the created chatbot_instances record (DB) for:

+ base_model (optional; default is TinyLlama if not set)

+ adapter_path (optional)

+ tokenizer_path (optional)

+ system_prompt (recommended: English system prompt)

+ generation params (optional)

4.5 Bind Messenger or Telegram for demo
Messenger

Create binding:
```
POST /api/messenger/bindings
```
```json
{
  "pageId": "<YOUR_PAGE_ID>",
  "chatbotId": "<CHATBOT_UUID>",
  "pageAccessToken": "<PAGE_ACCESS_TOKEN>"
}
```
Configure Meta webhook URL to your ngrok URL:
```
https://<ngrok-domain>/webhook/messenger
```
Verify token must match ```MESSENGER_VERIFY_TOKEN```.

Telegram

Create binding:
```
POST /api/telegram/bindings
```

```json
{
  "chatbotId": "<CHATBOT_UUID>",
  "botToken": "<TELEGRAM_BOT_TOKEN>"
}
```
Use the returned secretPath to set Telegram webhook to:

```https://<ngrok-domain>/webhook/telegram/<secretPath>```

5) Send a message to test (end-to-end)
Send a message to your Facebook page (Messenger) OR to your Telegram bot.

Spring receives the webhook, loads the right tenant + chatbot config,
then spawns the Python model server (if not running yet) and replies.

Recommended quick tests:

“What is your return policy?”

“What delivery options do you offer?”

“Do you have a student discount?” (should fallback: "I couldn't find that in this store's data.")