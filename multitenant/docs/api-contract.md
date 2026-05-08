# API Contract - multitenant <-> chatbot integration

## Purpose
This document defines the actual integration boundary between the Spring Boot multitenant service and the Python chatbot service.

Any field change here is an integration concern.

---

## Source of truth

The live contract is defined by the code paths below:

- Spring outbound DTO/client: `multitenant/src/main/java/com/app/modelserver/dto/ChatRequest.java`, `ChatResponse.java`, `GenerationConfig.java`, and `PythonChatClient.java`
- Python inbound/outbound models: `chatbot/app/server.py`
- Spring callers: web chat in `multitenant/src/main/java/com/app/chat/ChatController.java`, plus messenger and telegram webhook flows

If this document disagrees with those classes, the code wins.

---

## Outbound request from Spring to Python

### Target endpoint
`POST /chat`

### Request payload

```json
{
  "message": "What sofa would fit a small apartment?",
  "history": [
    "I need a sofa for a condo"
  ],
  "gen": {
    "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
    "adapter": "F:/models/lora_style_a",
    "tokenizer_path": "F:/models/tokenizer",
    "system_prompt": "You are a helpful furniture sales assistant.",
    "max_new_tokens": 256,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "stop": ["## Instruction:", "</s>"]
  },
  "conversation_id": "4fe7d6db-0b8d-46b0-8a08-3299550dd517",
  "channel": "web",
  "tenant_id": "tenant-001"
}
```

## Required behavior

- `message` must always be passed
- `history` is sent as a list of prior user messages
- `gen` may be omitted or partially populated; Python fills defaults from environment/runtime config
- `conversation_id`, `channel`, and `tenant_id` are optional in Python schema but are passed by Spring in normal integration flows
- `tenant_id` is used as metadata for KB lookup and logging, not as a transport-level tenant switch by itself

## Current Spring mapping rules

- Web chat calls `/api/chat/send`, stores the assistant response, and returns `reply`, `latencyMs`, `model`, `adapter`, and `llmBaseUrl`
- Messenger and Telegram callers pass the same Python contract but suppress downstream bot output if Python returns a blank `reply`
- Spring sends only user turns in `history`
- When the buyer replies `CONFIRM` during the close-stage handoff flow, Spring creates a minimal purchase request from the lead snapshot/transcript and still keeps the `/api/chat/send` JSON shape unchanged

## Purchase request persistence

- A purchase request is created only on the existing handoff trigger, currently `CONFIRM`
- The saved row is tenant-scoped and linked by `conversation_id`
- Stored business fields are:
  - `customer_name`
  - `phone`
  - `shipping_address`
  - `notes`
  - `status`
  - optional `requested_product_ref`
- Creation is idempotent per `(tenant_id, conversation_id)`; repeated `CONFIRM` updates missing fields instead of inserting another row

## Fields no longer in the real contract

- There is no top-level `query`
- There is no top-level `retrieval_mode`
- There is no top-level `top_k`
- Python does not return `answer`, `citations`, `retrieval_mode`, or `tenant_id` from `/chat`

---

## Expected Python response

```json
{
  "reply": "A compact 2-seater would usually fit a small apartment well.",
  "latency_ms": 842,
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter": "F:/models/lora_style_a"
}
```

## Mapping rules

- `reply` is the primary text surfaced to users
- `latency_ms` maps to Spring response field `latencyMs`
- `model` and `adapter` are passed through for diagnostics
- Blank `reply` is meaningful during handoff flow and should not be treated as deserialization failure
- Retrieval happens behind the Python boundary and is not represented as structured citations in the current response

---

## Error handling rules

- `422` from Python means request validation or shape failure
- `503` from Python means the model server is still loading
- Spring keeps the `/api/chat/send` response shape stable and maps upstream failures into categorized fallback replies instead of changing the controller payload
- Connection refusal, DNS failure, and warmup/startup-unavailable cases are treated as `UNAVAILABLE`
- Slow upstream responses and startup warmup expiry are treated as `TIMEOUT`
- Python `4xx` responses are treated as tenant/request configuration issues and logged as `UPSTREAM_4XX`
- Python `5xx` responses are treated as upstream service failures and logged as `UPSTREAM_5XX`
- Spring logs the tenant id, upstream base URL, failure category, HTTP status when present, and whether the request hit cold start or waited on warmup

## Additional Python endpoints used by Spring

### GET /state

Used by `LeadService` to build a lead snapshot during handoff.

Response shape:

```json
{
  "stage": "discover",
  "slots": {},
  "updated_at": 1711477000.0,
  "last_question": "I need a sofa",
  "last_answer": "What size are you looking for?"
}
```

### POST /feedback

Used to submit correctness feedback.

Request shape:

```json
{
  "conversation_id": "4fe7d6db-0b8d-46b0-8a08-3299550dd517",
  "tenant_id": "tenant-001",
  "channel": "web",
  "question": "Do you have this in leather?",
  "answer": "Yes, this model is available in leather.",
  "is_correct": true,
  "note": ""
}
```

---

## Compatibility rules

- additive fields are preferred
- breaking field renames must be coordinated
- DTO changes must stay synchronized with Python response schema
- the actual request and response classes in code are the contract authority
