# Messenger conversation continuity

Incoming Messenger messages are mapped to a stable sender identity using the tenant's inbound page id plus the Messenger sender id from the webhook payload.

The stored key format is:

`messenger:page:{pageId}:sender:{senderId}`

Conversation reuse rule:

- look up the latest `ACTIVE` conversation for the same tenant and stored Messenger sender key
- if one exists, reuse that conversation id
- if none exists, create a new conversation using the tenant's current Messenger binding chatbot

Operational notes:

- tenant isolation is enforced by the conversation lookup query, so the same Messenger sender id can exist under multiple tenants without sharing a conversation
- once a conversation already exists, later inbound messages continue using that conversation's `chatbotId`; this preserves the current multi-turn buyer flow even if the tenant later repoints the Messenger binding to a different chatbot
- closed or non-active conversations are not reused by this rule

Example:

- first inbound Messenger message from page `123` sender `999` creates conversation `X`
- second inbound Messenger message from page `123` sender `999` resolves the same sender key and reuses conversation `X`
