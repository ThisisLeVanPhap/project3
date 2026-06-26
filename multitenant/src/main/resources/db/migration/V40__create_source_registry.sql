CREATE TABLE IF NOT EXISTS source_registry (
    id UUID PRIMARY KEY,
    source_code VARCHAR(160) NOT NULL UNIQUE,
    source_name VARCHAR(255),
    root_url TEXT,
    sitemap_url TEXT,
    domain VARCHAR(255),
    visibility VARCHAR(32) NOT NULL DEFAULT 'TENANT_BOUND',
    owner_tenant_id UUID NULL REFERENCES tenants(id) ON DELETE SET NULL,
    product_url_patterns JSONB,
    exclude_patterns JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_registry_code
    ON source_registry (source_code);

CREATE INDEX IF NOT EXISTS idx_source_registry_enabled
    ON source_registry (enabled);
