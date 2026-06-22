# Final Technical Summary

## 1. Product Dataset Registry

Product dataset registry tracks imported product datasets such as `gotrangtri-20260610`, including source metadata, product counts, artifact paths, and assignment status. This lets admins assign a known dataset to a tenant without rerunning crawler/import work during demo.

## 2. Tenant KB Versioning

Tenant KB versions record generated KB artifacts, build status, active version, and related dataset identifiers. A tenant can have a `READY` KB version and an active KB directory selected for runtime.

## 3. Runtime KB Synchronization

Runtime status compares the tenant active KB version/directory against the chatbot runtime. The expected demo state is active KB/runtime `in_sync`, so product answers are grounded in the selected KB.

## 4. Sales Funnel / Hybrid NLU

The sales funnel uses hybrid NLU: deterministic rules for clear Vietnamese buying, contact, shipping/payment, comparison, and product discovery intents; adapter placeholders for future ML/LLM fallback. Slot filling keeps product category, material, price range, quantity, delivery area, phone/address, selected product, and last shown products across turns. Purchase scoring gates CTA, lead readiness, and handoff readiness so Purchase Requests are not created from browsing-only queries.

## 5. Reset Conversation

Reset Conversation supports deleting conversation messages by conversation id or external user key while keeping business records such as Leads and Purchase Requests. This is intended for repeatable demo/testing without losing CRM evidence.

## 6. CRM Permission Hardening

Lead and Purchase Request flows are tenant-scoped. Admin/tenant endpoints enforce permission boundaries, and tenant users can view, claim, reassign, and update allowed Purchase Requests without crossing tenants.

## 7. Cross-channel Identity Skeleton

The identity skeleton adds `UnifiedCustomer` and `CustomerIdentity`. It links Messenger, Telegram, and web identities by strong identifiers only: normalized phone/email within the same tenant. It does not merge by display name and does not merge across tenants. Full cross-channel conversation context loading is intentionally left for a later phase.

## 8. Test Evidence

Critical tests cover backend contracts, product retrieval/rendering, sales funnel state, handoff safety, reset conversation, CRM permissions, import flow, and customer identity resolution. Release check commands include full `multitenant` Maven tests and targeted chatbot unittest suites.
