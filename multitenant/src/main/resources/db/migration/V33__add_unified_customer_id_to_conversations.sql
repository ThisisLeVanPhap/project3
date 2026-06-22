-- Add unified_customer_id to conversations table for cross-channel identity resolution
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS unified_customer_id UUID;

-- Add foreign key constraint to unified_customers table
ALTER TABLE conversations
ADD CONSTRAINT fk_conversations_unified_customer
FOREIGN KEY (unified_customer_id)
REFERENCES unified_customers(id)
ON DELETE SET NULL;

-- Add index for efficient queries by unified customer
CREATE INDEX IF NOT EXISTS idx_conversations_tenant_unified_customer
ON conversations (tenant_id, unified_customer_id);
