-- Add title column to conversations
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR(200);
