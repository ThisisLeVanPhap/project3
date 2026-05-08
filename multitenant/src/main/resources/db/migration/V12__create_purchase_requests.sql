CREATE TABLE IF NOT EXISTS purchase_requests (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    lead_id BIGINT,
    customer_name VARCHAR(255) NOT NULL DEFAULT '',
    phone VARCHAR(64) NOT NULL DEFAULT '',
    shipping_address VARCHAR(2000) NOT NULL DEFAULT '',
    notes VARCHAR(4000) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    requested_product_ref VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_purchase_request_tenant_conversation UNIQUE (tenant_id, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_purchase_request_tenant_created
    ON purchase_requests (tenant_id, created_at DESC);
