# Testing Rules - multitenant service

## General rule
Every integration-related change must be validated at the service boundary it affects.

## What to test

When changing chatbot integration:
- tenant_id is propagated correctly
- request DTO is built correctly
- response mapping is correct
- timeout and upstream failure are handled cleanly

When changing controller logic:
- request validation
- service invocation
- returned payload shape

When changing service logic:
- happy path
- upstream error path
- missing tenant / missing KB path where applicable

## Test style
- prefer focused service/controller tests
- avoid broad end-to-end tests for small changes
- mock upstream chatbot service when testing Java-side mapping

## Minimum validation before finishing a task
1. changed path compiles
2. happy path works
3. one failure path works
4. tenant propagation is verified for chatbot-related changes

## Product demo checklist

Use this short flow when demoing the Vietnamese furniture buyer journey as a product.

### Manual prerequisites

- Start PostgreSQL and ensure the `global_admin` database is available
- Start the Spring Boot multitenant service on `http://localhost:8080`
- Ensure the Python chatbot runtime can be started by Spring for the demo tenant
- Reuse a working tenant/chatbot setup, for example:
  - demo tenant API key: `029269d7f5f445f7ac36c196dffa134e`
  - demo tenant id: `daf0378f-53e1-4705-8234-41c74287e489`
  - demo web chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`

### 1. Start a fresh buyer conversation

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

Expected result:

```json
{
  "conversationId": "..."
}
```

### 2. Ask for sofa advice

Replace `<conversationId>` with the value from step 1.

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Xin chao, toi muon mua sofa cho phong khach nho.\"}"
```

Expected result:

- response keys remain `reply`, `latencyMs`, `model`, `adapter`, `llmBaseUrl`
- chatbot replies in Vietnamese with sofa advice

### 3. Provide buyer details

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

Expected result:

- buyer name, phone, and shipping address are present in the conversation before confirmation

### 4. Confirm the purchase request

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"CONFIRM\"}"
```

Expected result:

- chatbot returns a Vietnamese confirmation message
- the message confirms the purchase request was created
- the message includes buyer name and shipping address when available
- the message says staff will contact the buyer soon

### 5. Show the saved purchase request

```bash
curl http://localhost:8080/api/purchase-requests ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

Optional status filter:

```bash
curl "http://localhost:8080/api/purchase-requests?status=NEW" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

Expected result:

- newest records appear first
- the latest row contains `customer_name`, `phone`, `shipping_address`, `notes`, `status`, and `created_at`
- the saved record matches the buyer details from the chat flow

### Optional demo script runner

If you want a fuller scripted conversation instead of manual curls, use:

```bash
python chatbot/tools/run_vietnamese_buyer_script.py --base-url http://localhost:8080 --api-key 029269d7f5f445f7ac36c196dffa134e
```

## Shared sample payloads

Use the sample values below for consistent manual testing across chat and purchase-request verification.

### Demo/example seed values

- example API key: `029269d7f5f445f7ac36c196dffa134e`
- example tenant id: `daf0378f-53e1-4705-8234-41c74287e489`
- example chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`
- replace `<conversationId>` with the real value returned by `POST /api/chat/start`

### 1. Valid chat start request

```json
{
  "chatbotId": "e08a7b4f-ebfb-4874-a119-b90e95e85fc7"
}
```

Example:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

### 2. Valid chat send request

```json
{
  "conversationId": "<conversationId>",
  "message": "Xin chao, toi muon mua sofa cho phong khach nho."
}
```

Example:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"Xin chao, toi muon mua sofa cho phong khach nho.\"}"
```

### 3. Invalid chat request

Missing required `message`:

```json
{
  "conversationId": "<conversationId>"
}
```

Example:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\"}"
```

### 4. Purchase-request creation flow payloads

Buyer info turn:

```json
{
  "conversationId": "<conversationId>",
  "message": "Ten toi la Nguyen Van A, so dien thoai la 0912345678."
}
```

Shipping address turn:

```json
{
  "conversationId": "<conversationId>",
  "message": "Dia chi nhan hang cua toi la 123 Nguyen Trai, Ha Noi."
}
```

Confirm turn:

```json
{
  "conversationId": "<conversationId>",
  "message": "CONFIRM"
}
```

Examples:

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

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<conversationId>\",\"message\":\"CONFIRM\"}"
```

### 5. Purchase-request verification request

No filter:

```bash
curl http://localhost:8080/api/purchase-requests ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

Expected response shape:

```json
[
  {
    "customer_name": "Nguyen Van A",
    "phone": "0912345678",
    "shipping_address": "123 Nguyen Trai, Ha Noi",
    "notes": "",
    "status": "NEW",
    "created_at": "2026-04-01T10:07:10.656866Z"
  }
]
```

### 6. Purchase-request verification with status filter

```bash
curl "http://localhost:8080/api/purchase-requests?status=NEW" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

Expected response shape:

- same JSON object fields as the unfiltered request
- newest matching records first

### 7. Purchase-request status progression

```bash
curl -X POST "http://localhost:8080/api/purchase-requests/1/status?status=CONTACTED" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e"
```

Expected response shape:

```json
{
  "customer_name": "Nguyen Van A",
  "phone": "0912345678",
  "shipping_address": "123 Nguyen Trai, Ha Noi",
  "notes": "",
  "status": "CONTACTED",
  "created_at": "2026-04-01T10:07:10.656866Z"
}
```

Expected result:

- allowed statuses are `NEW`, `CONTACTED`, and `COMPLETED`
- the update stays tenant-scoped
- `GET /api/purchase-requests` keeps the same response shape and shows the updated status

## Manual verification for chatbot timeout handling

Use one of the flows below after changing Spring-to-chatbot integration:

1. Web chat curl flow
- Start the multitenant service
- Create or reuse a conversation id
- Call `POST /api/chat/send` with the same payload shape as before
- Verify the JSON keys remain `reply`, `latencyMs`, `model`, `adapter`, and `llmBaseUrl`
- Default local-LLM response timeout budget is `120000ms` (about 2 minutes per turn) unless `LLM_RESPONSE_TIMEOUT_MS` overrides it
- Stop the Python chatbot or point the tenant to an unused port and verify the reply becomes the unavailable fallback while logs show `category=UNAVAILABLE`
- Make the Python `/chat` handler sleep longer than `python.llm.response-timeout-ms` and verify the reply becomes the timeout fallback while logs show `category=TIMEOUT`
- Force the Python service to return `500` and verify the reply becomes the upstream error fallback while logs show `category=UPSTREAM_5XX`
- Force the Python service to return `422` or equivalent missing-KB tenant validation failure and verify the reply becomes the tenant-configuration fallback while logs show `category=UPSTREAM_4XX`

2. Buyer script runner
- Run the existing Vietnamese buyer script against the same tenant/chatbot
- Watch Spring logs for `tenant=...`, `baseUrl=...`, `coldStart=...`, and `warmupWaited=...`
- Send two first-turn requests concurrently for the same tenant and verify only one LLM startup is spawned while the other request waits for the same warmup path

## Manual verification for purchase request persistence

1. Vietnamese buyer flow
- Start the multitenant service and ensure Flyway applies the `purchase_requests` migration
- Run the existing Vietnamese buyer scenario until the chatbot asks for `CONFIRM`
- Provide customer name, phone number, and shipping address in chat, then send `CONFIRM`
- Verify `/api/chat/send` still returns the same JSON keys, and the reply switches to the staff handoff message
- Check the database for a new row in `purchase_requests` keyed by tenant and conversation
- Verify the stored fields are populated as available: `customer_name`, `phone`, `shipping_address`, `notes`, `status`, and optional `requested_product_ref`

2. Quick SQL checks
- `select tenant_id, conversation_id, customer_name, phone, shipping_address, status from purchase_requests order by created_at desc;`
- Confirm only one purchase request exists per `(tenant_id, conversation_id)` even if `CONFIRM` is sent twice

## Manual verification for purchase request listing API

1. Curl flow
- Start the multitenant service
- Call `GET /api/purchase-requests` with `X-Tenant-Id` or `X-API-Key`
- Verify the JSON array contains only `customer_name`, `phone`, `shipping_address`, `notes`, `status`, and `created_at`
- Optionally call `GET /api/purchase-requests?tenantId=<same-tenant-id>` and verify the result matches the header-scoped request
- Call `GET /api/purchase-requests?tenantId=<different-tenant-id>` and verify the API returns `403`

2. Quick SQL comparison
- `select tenant_id, customer_name, phone, shipping_address, notes, status, created_at from purchase_requests where tenant_id = '<tenant-id>' order by created_at desc limit 200;`
- Compare the API rows and field values against the SQL result for the same tenant

## Manual verification for purchase request status updates

1. Curl flow
- Start the multitenant service
- Create or reuse a purchase request for the tenant
- Call `POST /api/purchase-requests/{id}/status?status=CONTACTED` with `X-Tenant-Id` or `X-API-Key`
- Verify the response body keeps the existing purchase-request fields and now returns `status = CONTACTED`
- Call `GET /api/purchase-requests` and verify the same row now appears with the updated status
- Optionally repeat with `status=COMPLETED`
- Call the status endpoint with an unsupported value and verify the API returns `400`

2. Quick SQL comparison
- `select id, tenant_id, customer_name, status, created_at from purchase_requests where tenant_id = '<tenant-id>' order by created_at desc limit 20;`
- Compare the updated `status` value against the API response for the same purchase request

## Manual verification for purchase request internal read view

1. Browser flow
- Start the multitenant service
- Open `http://localhost:8080/tenant/purchase-requests?tid=<tenant-id>&name=<tenant-name>`
- Verify the page loads rows newest-first for that tenant only
- Change the status filter to `NEW`, `CONTACTED`, or `COMPLETED` and verify the table matches `GET /api/purchase-requests?status=...`
- Use the `Open JSON API` link and verify it opens the same data shape as the existing API

2. Tenant safety check
- Open the browser dev tools network tab and confirm requests are sent to `GET /api/purchase-requests`
- Confirm the request includes `X-Tenant-Id`
- Remove the stored tenant session and verify the page stops loading data until a tenant id is provided again
