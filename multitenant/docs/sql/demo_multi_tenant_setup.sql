-- Demo setup for showing tenant-specific KB behavior.
-- Run this against the `global_admin` database after Flyway migrations.

-- Tenant A: Vietnamese CaCo furniture consultant
INSERT INTO tenants (id, code, name, status, api_key, kb_dir)
VALUES (
    'daf0378f-53e1-4705-8234-41c74287e489',
    'demo_caco',
    'Demo CaCo',
    'ACTIVE',
    '029269d7f5f445f7ac36c196dffa134e',
    'F:/20251/prj3/chatbot/kb/noithatcaco'
)
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    api_key = EXCLUDED.api_key,
    kb_dir = EXCLUDED.kb_dir;

-- Tenant B: Article-style modern furniture consultant
INSERT INTO tenants (id, code, name, status, api_key, kb_dir)
VALUES (
    '58ca3bdb-50b4-4e36-bcf6-fc88dbd2e457',
    'demo_article',
    'Demo Article',
    'ACTIVE',
    'a4b9d130f0d34f74ac6b54cf8d6d2e11',
    'F:/20251/prj3/chatbot/kb/article'
)
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    api_key = EXCLUDED.api_key,
    kb_dir = EXCLUDED.kb_dir;

INSERT INTO chatbot_instances (id, tenant_id, name, channel, persona, status, response_style)
VALUES (
    'e08a7b4f-ebfb-4874-a119-b90e95e85fc7',
    'daf0378f-53e1-4705-8234-41c74287e489',
    'CaCo Web Demo Bot',
    'web',
    '{"tone":"tu van noi that viet nam","focus":"sofa go, noi that thi cong theo yeu cau"}'::jsonb,
    'ACTIVE',
    'natural'
)
ON CONFLICT (id) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    name = EXCLUDED.name,
    channel = EXCLUDED.channel,
    persona = EXCLUDED.persona,
    status = EXCLUDED.status,
    response_style = EXCLUDED.response_style;

INSERT INTO chatbot_instances (id, tenant_id, name, channel, persona, status, response_style)
VALUES (
    '5fd0f6f4-c0b8-4e4e-9d7b-4b65f4c3998b',
    '58ca3bdb-50b4-4e36-bcf6-fc88dbd2e457',
    'Article Web Demo Bot',
    'web',
    '{"tone":"modern direct-to-consumer furniture advisor","focus":"Article catalog, delivery, returns"}'::jsonb,
    'ACTIVE',
    'balanced'
)
ON CONFLICT (id) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    name = EXCLUDED.name,
    channel = EXCLUDED.channel,
    persona = EXCLUDED.persona,
    status = EXCLUDED.status,
    response_style = EXCLUDED.response_style;
