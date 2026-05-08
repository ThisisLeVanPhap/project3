# Multi-Tenant Demo Note

Use this note to show that the product is not a single-store chatbot.

## Setup

1. Run the seed script in [demo_multi_tenant_setup.sql](/F:/20251/prj3/multitenant/docs/sql/demo_multi_tenant_setup.sql)
2. Start PostgreSQL, Spring Boot, and the Python chatbot runtime
3. Use these demo tenants:
   - Tenant A: `Demo CaCo`
     - tenant id: `daf0378f-53e1-4705-8234-41c74287e489`
     - api key: `029269d7f5f445f7ac36c196dffa134e`
     - chatbot id: `e08a7b4f-ebfb-4874-a119-b90e95e85fc7`
     - KB: `chatbot/kb/noithatcaco`
   - Tenant B: `Demo Article`
     - tenant id: `58ca3bdb-50b4-4e36-bcf6-fc88dbd2e457`
     - api key: `a4b9d130f0d34f74ac6b54cf8d6d2e11`
     - chatbot id: `5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b`
     - KB: `chatbot/kb/article`

## Recommended comparison query

Use a similar sofa-shopping prompt for both tenants:

```text
I need a sofa for a small living room. What would you recommend?
```

## How to demo

1. Start chat with Tenant A:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"chatbotId\":\"e08a7b4f-ebfb-4874-a119-b90e95e85fc7\"}"
```

2. Send the query with Tenant A:

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 029269d7f5f445f7ac36c196dffa134e" ^
  -d "{\"conversationId\":\"<tenantAConversationId>\",\"message\":\"I need a sofa for a small living room. What would you recommend?\"}"
```

3. Repeat the same flow for Tenant B with the second API key and chatbot id:

```bash
curl -X POST http://localhost:8080/api/chat/start ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: a4b9d130f0d34f74ac6b54cf8d6d2e11" ^
  -d "{\"chatbotId\":\"5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b\"}"
```

```bash
curl -X POST http://localhost:8080/api/chat/send ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: a4b9d130f0d34f74ac6b54cf8d6d2e11" ^
  -d "{\"conversationId\":\"<tenantBConversationId>\",\"message\":\"I need a sofa for a small living room. What would you recommend?\"}"
```

## What difference to point out

- Tenant A should lean toward CaCo-style Vietnamese interior products and project-style guidance from `noithatcaco`
- Tenant B should lean toward Article catalog language, Article model names, and Article-style product or service details from `article`
- The difference is driven by tenant-specific `kb_dir`, not by a separate API

## Concrete cues to watch for

- Tenant A may mention CaCo-specific terms such as `SFG041`, `sofa gỗ sồi`, made-to-order production, showroom/hotline context, or Vietnamese interior-fit consultation
- Tenant B may mention Article-specific names like `Timber`, `Sven`, or `Gabriola`, plus Article-style details such as USD pricing, delivery, or 30-day satisfaction messaging

## Observed demo difference to highlight

- Same product intent, different tenant context
- Tenant A reads like a Vietnam interior/fabrication business
- Tenant B reads like a separate modern e-commerce furniture brand
