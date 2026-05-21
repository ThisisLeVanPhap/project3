-- Move the public/general chatbot away from the old TinyLlama demo default.
-- Keep provider/API settings intact; this only updates the stale local demo model.
UPDATE chatbot_instances
SET mode = 'general_compare',
    base_model = 'Qwen/Qwen2.5-1.5B-Instruct'
WHERE id = '11111111-1111-1111-1111-111111111111'
  AND provider = 'local'
  AND lower(coalesce(base_model, '')) = 'tinyllama/tinyllama-1.1b-chat-v1.0';
