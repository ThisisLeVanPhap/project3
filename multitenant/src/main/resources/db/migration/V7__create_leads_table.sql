CREATE TABLE IF NOT EXISTS leads (
                                     id BIGSERIAL PRIMARY KEY,

                                     tenant_id VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,

    customer_handle VARCHAR(256),
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',

    slots_json TEXT,
    transcript TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_leads_tenant_created
    ON leads (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_leads_conversation
    ON leads (conversation_id);
