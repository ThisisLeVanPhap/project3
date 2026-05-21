CREATE TABLE IF NOT EXISTS tenant_onboarding_requests (
    id UUID PRIMARY KEY,
    store_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(64) NOT NULL,
    website_url VARCHAR(512),
    note TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    admin_note TEXT,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    owner_member_id UUID REFERENCES tenant_members(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provisioned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tenant_onboarding_status_created
    ON tenant_onboarding_requests(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tenant_onboarding_email
    ON tenant_onboarding_requests(email);
