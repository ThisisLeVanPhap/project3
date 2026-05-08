-- Add lead_created flag to conversations table
-- This tracks whether a lead/purchase request has been created for a conversation
-- to prevent duplicate lead creation and enable idempotent behavior

ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS lead_created BOOLEAN NOT NULL DEFAULT FALSE;

-- Index for queries that filter by lead_created status
CREATE INDEX IF NOT EXISTS idx_conversations_lead_created
    ON conversations (tenant_id, lead_created DESC, created_at DESC);
