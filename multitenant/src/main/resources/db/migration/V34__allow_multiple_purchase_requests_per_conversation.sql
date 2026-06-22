ALTER TABLE purchase_requests
    DROP CONSTRAINT IF EXISTS uq_purchase_request_tenant_conversation;

CREATE INDEX IF NOT EXISTS idx_purchase_request_tenant_conversation_created
    ON purchase_requests (tenant_id, conversation_id, created_at DESC);
