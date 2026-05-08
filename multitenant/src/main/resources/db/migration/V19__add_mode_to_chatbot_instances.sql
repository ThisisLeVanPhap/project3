-- V19__add_mode_to_chatbot_instances.sql
ALTER TABLE chatbot_instances ADD COLUMN mode VARCHAR(64);

-- Set default for existing rows
UPDATE chatbot_instances SET mode = 'tenant_sales' WHERE mode IS NULL;

-- Make default for future inserts (PostgreSQL syntax)
ALTER TABLE chatbot_instances ALTER COLUMN mode SET DEFAULT 'tenant_sales';
