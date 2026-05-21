-- V26__null_chatbot_api_fields_for_system_claude.sql
-- Phase 2 Round 1: Make Claude system-level provider.
-- Null per-chatbot API config fields that are no longer used.
-- Claude now uses env: ANTHROPIC_API_KEY/CLAUDE_API_KEY, CLAUDE_MODEL, CLAUDE_API_BASE_URL.
--
-- Note: V22__add_lead_created_to_conversations.sql is the original valid V22 migration.
-- TODO (Phase 2 Round 2): Drop columns api_key, api_model, api_base_url from chatbot_instances
-- after compatibility window closes and no legacy config is in use.

UPDATE chatbot_instances
SET api_key = NULL,
    api_model = NULL,
    api_base_url = NULL
WHERE api_key IS NOT NULL
   OR api_model IS NOT NULL
   OR api_base_url IS NOT NULL;