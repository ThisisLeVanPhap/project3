ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS handoff_id VARCHAR(128);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(256);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS product_sku VARCHAR(128);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS product_url VARCHAR(1000);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS price NUMERIC(19, 2);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS quantity INT;

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS email VARCHAR(255);

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_request_tenant_idempotency_key
    ON purchase_requests (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_request_tenant_handoff_id
    ON purchase_requests (tenant_id, handoff_id)
    WHERE handoff_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_purchase_request_tenant_status
    ON purchase_requests (tenant_id, status);
