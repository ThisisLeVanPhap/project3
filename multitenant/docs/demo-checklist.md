# Purchase Request Demo Checklist

Use this checklist for a short end-to-end demo from buyer chat to admin processing.

## Start required services

- Start PostgreSQL and ensure the `global_admin` database is available
- Start the Spring Boot multitenant service at `http://localhost:8080`
- Ensure the Python chatbot runtime is available for the demo tenant
- Reuse a working tenant and chatbot, for example:
  - API key: `029269d7f5f445f7ac36c196dffa134e`
  - tenant id: `daf0378f-53e1-4705-8234-41c74287e489`
  - chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`

## Buyer chat flow

1. Start a conversation:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

2. Save the returned `conversationId`, then send this example conversation:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Xin chao, toi muon mua sofa cho phong khach nho.\"}"
```

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Ten toi la Nguyen Van A, so dien thoai la 0912345678.\"}"
```

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Dia chi nhan hang cua toi la 123 Nguyen Trai, Ha Noi.\"}"
```

3. Trigger the handoff by sending `CONFIRM`:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"CONFIRM\"}"
```

Expected result:

- the reply confirms the purchase request was created
- the reply mentions the buyer and shipping address when available
- staff handoff messaging is returned in the normal `/api/chat/send` response

## Verify in admin UI

1. Open `http://localhost:8080/admin`
2. In the existing admin config area, apply the demo tenant using `X-API-Key` or `X-Tenant-Id`
3. Open the `Purchase Requests` tab
4. Keep the status filter as `All` and click `Load purchase requests`
5. Verify the newest row matches the buyer details from chat and starts with status `NEW`

Optional API check:

```bash
curl http://localhost:8080/api/purchase-requests ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

## Update status in admin UI

1. In the `Purchase Requests` table, change the row from `NEW` to `CONTACTED`
2. Wait for the inline `Saved` feedback
3. Change the same row from `CONTACTED` to `COMPLETED`
4. Verify the status cell updates in place after each change

Optional API shape for the same action:

```bash
curl -X PUT http://localhost:8080/api/purchase-requests/<id>/status ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"status\":\"CONTACTED\"}"
```

## Demo success criteria

- buyer reaches the `CONFIRM` step in chat
- a purchase request is created for the current tenant
- admin can load the request in `/admin`
- admin can move the request `NEW -> CONTACTED -> COMPLETED`
