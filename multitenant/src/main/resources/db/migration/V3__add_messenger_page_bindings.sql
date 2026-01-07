-- Bảng ánh xạ Fanpage (page_id) -> (tenant_id, chatbot_id, page_access_token)

CREATE TABLE IF NOT EXISTS messenger_page_bindings (
                                                       id               UUID PRIMARY KEY,
                                                       tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    page_id           VARCHAR(64) NOT NULL,
    chatbot_id        UUID NOT NULL REFERENCES chatbot_instances(id) ON DELETE CASCADE,
    page_access_token TEXT NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (page_id),
    UNIQUE (tenant_id, page_id)
    );

CREATE INDEX IF NOT EXISTS idx_messenger_page_bindings_page_id
    ON messenger_page_bindings(page_id);

CREATE INDEX IF NOT EXISTS idx_messenger_page_bindings_tenant_id
    ON messenger_page_bindings(tenant_id);
