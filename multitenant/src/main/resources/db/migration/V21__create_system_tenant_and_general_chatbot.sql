-- ===============================================
-- V21__create_system_tenant_and_general_chatbot.sql
-- Thêm system tenant và general consumer chatbot
-- ===============================================

-- Thêm system tenant (dùng cho general chat)
INSERT INTO tenants (id, code, name, status, api_key)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system_tenant',
    'System General Chat',
    'ACTIVE',
    'system-api-key-placeholder'
) ON CONFLICT (id) DO NOTHING;

-- Thêm general consumer chatbot cho system tenant
INSERT INTO chatbot_instances (id, tenant_id, name, channel, persona, status, base_model, mode, provider)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    '00000000-0000-0000-0000-000000000000',
    'General Consumer Assistant',
    'web',
    '{"tone": "friendly", "purpose": "general_consumer"}'::jsonb,
    'ACTIVE',
    'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
    'general_consumer',
    'local'
) ON CONFLICT (id) DO NOTHING;

-- ===============================================
-- ✅ Hoàn tất migration V21
-- ===============================================
