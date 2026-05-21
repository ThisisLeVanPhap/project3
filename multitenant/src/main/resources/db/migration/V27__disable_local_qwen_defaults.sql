-- Disable local Qwen defaults for VPS/API-provider deployments.
-- Local model usage is now an explicit opt-in via LOCAL_MODEL_ENABLED=true.

ALTER TABLE chatbot_instances
    ALTER COLUMN provider SET DEFAULT 'claude';

UPDATE chatbot_instances
SET provider = 'claude'
WHERE lower(coalesce(provider, '')) = 'local';

UPDATE chatbot_instances
SET base_model = NULL
WHERE lower(coalesce(base_model, '')) = 'qwen/qwen2.5-1.5b-instruct';
