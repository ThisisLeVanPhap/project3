ALTER TABLE leads ADD COLUMN IF NOT EXISTS order_info TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS shipping_status VARCHAR(32) NOT NULL DEFAULT 'NEW';

CREATE TABLE IF NOT EXISTS feedback (
                                        id BIGSERIAL PRIMARY KEY,
                                        tenant_id VARCHAR(64) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    rating INT NOT NULL, -- 1=good, -1=bad
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_feedback_tenant_created
    ON feedback (tenant_id, created_at DESC);
