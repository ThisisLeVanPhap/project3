# Final Demo Checklist

## A. Start Services

- Start Postgres/local DB with the expected demo database.
- Start Spring Boot from `multitenant`.
- Start or verify the chatbot runtime if the chat demo calls the Python service.
- Confirm the active tenant and chatbot instance are available.

## B. Product Dataset / KB Demo

- Login at `/admin`.
- Select the demo tenant.
- Open Product Datasets.
- View dataset `gotrangtri-20260610`.
- Assign the dataset to the tenant if it is not already assigned.
- Open KB Versions and confirm the assigned version is `READY` and active.
- Check Active KB Directory for the tenant.
- Check Runtime Status and confirm it is `in_sync`.

## C. Chat Demo

- Ask: `San pham nao bang go cong nghiep?`
- Ask: `Co ban tra nao khong?`
- Ask a purchase-intent message with phone, for example: `Toi muon mua mau nay, so dien thoai 0987654321`.
- Confirm that product answers use KB data and the handoff/purchase request flow does not create an order too early.

## D. Reset Conversation Demo

- Open Operations -> Reset Conversation.
- Reset by `conversationId` or by external user key.
- Confirm conversation messages are deleted.
- Confirm Lead and Purchase Request records are not deleted.

## E. CRM Demo

- Open Purchase Requests.
- Open a purchase request detail page.
- Claim the request.
- Update request status.
- Open Leads detail/update status when applicable.
- Verify tenant-scoped permissions prevent cross-tenant access.

## F. Identity Skeleton Demo

- Explain that Messenger and Telegram identities can link to the same unified customer when a shared phone/email is present.
- Explain that same display name alone does not merge customers.
- Explain that cross-tenant identities never merge.
- Clarify that full cross-channel runtime context switching is not included in this phase.
