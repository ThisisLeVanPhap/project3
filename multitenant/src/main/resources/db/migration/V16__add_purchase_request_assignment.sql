ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS assigned_to_member_id UUID;

ALTER TABLE purchase_requests
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP WITH TIME ZONE;
