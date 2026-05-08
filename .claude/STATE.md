# PROJECT STATE — Multi-tenant RAG Chatbot Product

## 1. Current Product Status

The system is now a working product prototype, not just a backend demo.

It includes:

* Multi-tenant Spring Boot backend
* FastAPI AI service
* RAG-based chatbot
* Local LLM + Claude API provider switch
* Tenant sales chatbot
* General AI Interior Advisor
* Web chat UI
* Conversation persistence
* Conversation sidebar
* Rename/delete conversation
* Auto-generated conversation title
* Conversation preview
* Typing indicator
* Model/latency metadata
* Lead / purchase request conversion flow

The project is currently at a strong product prototype stage.

---

## 2. Main Product Surfaces

### A. General AI Interior Advisor

Path:

`/chat/general/`

Purpose:

* General consumer interior shopping consultation
* Not tied to a specific tenant
* Focuses on:

  * room type
  * room size
  * budget
  * style
  * color
  * material
  * product suggestion

Current capabilities:

* Guided consultation
* Preference memory
* Preference change handling
* Topic change handling
* Off-topic redirect
* Soft close/disengagement
* Conversation list
* Rename/delete conversation
* Auto title
* Typing indicator

---

### B. Tenant Sales Chatbot

Path:

`/chat?tenantId=...&chatbotId=...`

Purpose:

* Store-specific sales assistant
* Uses tenant-specific KB
* Supports lead / purchase flow

Current capabilities:

* Multi-tenant isolation
* Tenant-specific chatbot configuration
* RAG over tenant KB
* Conversation persistence
* Conversation ownership via `userExternalId`
* Rename/delete conversation
* Auto title
* Purchase trigger
* Lead creation
* PurchaseRequest creation
* Duplicate lead prevention
* Phone / buyer data validation

---

### C. Landing Page

Path:

`/`

Purpose:

* Shows two product entry points:

  * General AI Interior Advisor
  * Tenant-specific store chatbot

This makes the product structure understandable to users and reviewers.

---

## 3. AI Behavior Layer

The AI layer is considered complete for the current scope.

Implemented:

* Intent detection
* Stage-based conversation control
* Context-aware confirm detection
* Slot extraction
* Preference memory
* Preference change tracking
* Topic change reset
* Off-topic handling
* Disengagement handling
* Natural response prompt guidelines
* RAG grounding
* Guardrails for unsafe/unverified business claims

Important design principle:

The LLM does not control the business flow directly.
The system controls the flow through rules, stages, slots, and validation.
The LLM is used mainly for natural language generation.

---

## 4. Conversation UX Layer

Implemented:

* Sidebar conversation list
* Active conversation highlight
* Empty state
* Rename conversation
* Delete conversation
* Auto title from first user message
* Last message preview
* Typing indicator
* Auto-scroll
* Input focus after reply
* Model and latency metadata

Recent fixes:

* Removed duplicated ChatController endpoints
* Added DB migration for conversation title
* Fixed ChatResponse constructor mismatch
* Fixed PythonChatFallbacks constructor mismatch
* Maven compile passed after cleanup

---

## 5. Business Flow

Tenant sales flow:

User chat
→ AI consultation
→ close stage + confirm intent
→ Java backend creates Lead
→ PurchaseRequestService extracts structured buyer data
→ PurchaseRequest is created
→ Conversation marked as leadCreated
→ duplicate creation prevented

General consumer flow:

User chat
→ general consultation
→ phone / purchase interest detected
→ PurchaseRequest can be created under system tenant

Current business value:

The chatbot does not only answer questions.
It can convert a conversation into a business record.

---

## 6. Data / Persistence

Main persisted data:

* Conversations
* Messages
* Leads
* PurchaseRequests
* ChatbotInstance config
* Tenant data
* Provider config

Conversation title support:

* `Conversation.title`
* Migration: `V23__add_title_to_conversations.sql`

---

## 7. What Is Done

Done:

* Core backend
* AI service
* RAG
* Local/Claude provider switch
* General advisor
* Tenant sales chatbot
* Conversation memory
* Conversation UX
* Lead/purchase flow
* Landing page
* Basic product polish
* Compile cleanup

---

## 8. Known Limitations

Still not fully production-level:

* General chat guest isolation is still lightweight
* No full end-user account system
* No multi-device sync
* In-memory Python conversation state can be lost on restart
* Slot extraction is regex/rule-based, not semantic extraction
* Title generation is still simple heuristic / first-message based
* Tenant chat entry from landing page is not yet a clean customer-facing tenant selector
* Admin/product management UI is still basic
* No analytics dashboard
* No formal test suite for all flows yet

---

## 9. Current Priority

Do NOT keep changing AI logic unless a real bug appears.

Next improvements should focus on:

1. Product clarity
2. Testability
3. Admin/demo readiness
4. Documentation
5. Stability

---

## 10. Recommended Next Work

Priority order:

1. Add a simple test checklist / regression checklist
2. Improve smart conversation title generation
3. Improve tenant entry flow from landing page
4. Add a small admin view for purchase requests / leads
5. Add project documentation explaining architecture and flows
6. Add seed/demo data for reliable presentation
7. Add basic automated tests for critical backend flows

---

## 11. Resume Instruction

When starting a new Claude session:

Read this file first.

Assume:

* AI layer is complete
* conversation UX is mostly complete
* product structure is complete
* do not rewrite core flow

Continue by improving product readiness, testing, documentation, and small UX polish only.
