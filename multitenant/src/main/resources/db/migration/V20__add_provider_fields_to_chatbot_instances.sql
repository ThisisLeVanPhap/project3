-- V20__add_provider_fields_to_chatbot_instances.sql
ALTER TABLE chatbot_instances ADD COLUMN IF NOT EXISTS provider VARCHAR(64) NOT NULL DEFAULT 'local';
ALTER TABLE chatbot_instances ADD COLUMN IF NOT EXISTS api_model VARCHAR(256);
ALTER TABLE chatbot_instances ADD COLUMN IF NOT EXISTS api_key TEXT;
ALTER TABLE chatbot_instances ADD COLUMN IF NOT EXISTS api_base_url VARCHAR(512);
