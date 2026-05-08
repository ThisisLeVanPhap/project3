# Demo Presentation Script

Use this script when presenting the product live from buyer chat to admin processing.

## 1. Start prerequisites

- Start PostgreSQL with the `global_admin` database
- Start the Spring Boot service at `http://localhost:8080`
- Ensure the Python chatbot runtime is available
- If needed, prepare demo tenants with [demo_multi_tenant_setup.sql](/F:/20251/prj3/multitenant/docs/sql/demo_multi_tenant_setup.sql)

## 2. Present Tenant A end-to-end

Use Tenant A first:

- Tenant A name: `Demo CaCo`
- API key: `029269d7f5f445f7ac36c196dffa134e`
- chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`

Start chat:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

Save the returned `conversationId`, then send these exact buyer messages:

1. `Xin chao, toi muon mua sofa cho phong khach nho.`
2. `Ten toi la Nguyen Van A, so dien thoai la 0912345678.`
3. `Dia chi nhan hang cua toi la 123 Nguyen Trai, Ha Noi.`
4. `CONFIRM`

Send each turn with:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"<message>\"}"
```

Expected outcome to say out loud:

- the bot gives buying guidance
- `CONFIRM` creates the purchase request
- the confirmation reply clearly summarizes captured customer details

## 3. Open admin UI

Open `http://localhost:8080/admin` right after `CONFIRM`.

In the config area:

- set `X-API-Key` to Tenant A
- open the `Purchase Requests` tab
- keep filter as `All`
- click `Load purchase requests`

Expected outcome:

- the newest row matches `Nguyen Van A`
- the request starts at `NEW`

## 4. Show status progression

In the same Purchase Requests table:

1. change the row from `NEW` to `CONTACTED`
2. wait for `Saved`
3. change it again from `CONTACTED` to `COMPLETED`

Expected outcome:

- the status badge updates in place
- the row shows the lifecycle from new request to finished processing

## 5. Switch tenant for multi-tenant proof

Now switch to Tenant B:

- Tenant B name: `Demo Article`
- API key: `a4b9d130f0d34f74ac6b54cf8d6d2e11`
- chatbot id: `5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b`

Use this comparison query:

`I need a sofa for a small living room. What would you recommend?`

Start a new chat for Tenant B:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: a4b9d130f0d34f74ac6b54cf8d6d2e11" ^
  -d "{\"chatbotId\":\"5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b\"}"
```

Then send the same sofa query:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: a4b9d130f0d34f74ac6b54cf8d6d2e11" ^
  -d "{\"conversationId\":\"<tenantBConversationId>\",\"message\":\"I need a sofa for a small living room. What would you recommend?\"}"
```

Expected visible difference:

- Tenant A should feel like a Vietnamese CaCo interior/fabrication consultant
- Tenant B should feel like a separate Article-style modern furniture brand
- mention examples such as CaCo product/project cues versus Article names like `Timber`, `Sven`, or `Gabriola`

## 6. Close the demo

Final points to highlight:

- same product flow, same APIs
- tenant-scoped chat behavior
- tenant-scoped purchase requests
- admin can process requests without leaving the current product
