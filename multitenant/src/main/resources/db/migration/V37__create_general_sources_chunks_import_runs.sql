CREATE TABLE IF NOT EXISTS general_sources (
    id UUID PRIMARY KEY,
    source_code VARCHAR(160) NOT NULL,
    source_name VARCHAR(255),
    source_domain VARCHAR(255),
    source_type VARCHAR(64) NOT NULL,
    source_ref VARCHAR(255),
    tenant_id UUID NULL REFERENCES tenants(id) ON DELETE SET NULL,
    dataset_id VARCHAR(160),
    kb_version_id UUID NULL REFERENCES tenant_kb_versions(id) ON DELETE SET NULL,
    artifact_id UUID NULL REFERENCES product_dataset_artifacts(id) ON DELETE SET NULL,
    visibility VARCHAR(32) NOT NULL DEFAULT 'GLOBAL_PUBLIC',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_general_sources_artifact UNIQUE (artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_general_sources_visibility_status
    ON general_sources (visibility, status);

CREATE INDEX IF NOT EXISTS idx_general_sources_dataset
    ON general_sources (dataset_id);

CREATE INDEX IF NOT EXISTS idx_general_sources_artifact
    ON general_sources (artifact_id);

CREATE INDEX IF NOT EXISTS idx_general_sources_source_type_ref
    ON general_sources (source_type, source_ref);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS general_source_id UUID REFERENCES general_sources(id) ON DELETE SET NULL;

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS source_code VARCHAR(160);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS source_domain VARCHAR(255);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS external_product_id VARCHAR(160);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(512);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS product_type VARCHAR(160);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS original_price NUMERIC(14, 2);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS dimensions_text VARCHAR(255);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS quality_score NUMERIC(5, 2);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS extraction_confidence NUMERIC(5, 2);

ALTER TABLE general_products
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE general_products
SET source_code = COALESCE(source_code, dataset_id),
    external_product_id = COALESCE(external_product_id, product_id),
    normalized_name = COALESCE(normalized_name, LOWER(name)),
    product_type = COALESCE(product_type, category),
    dimensions_text = COALESCE(dimensions_text, dimensions)
WHERE source_code IS NULL
   OR external_product_id IS NULL
   OR normalized_name IS NULL
   OR product_type IS NULL
   OR dimensions_text IS NULL;

CREATE INDEX IF NOT EXISTS idx_general_products_general_source
    ON general_products (general_source_id);

CREATE INDEX IF NOT EXISTS idx_general_products_source_code
    ON general_products (source_code);

CREATE INDEX IF NOT EXISTS idx_general_products_source_domain
    ON general_products (source_domain);

CREATE INDEX IF NOT EXISTS idx_general_products_external_product_id
    ON general_products (external_product_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_general_products_source_external_product
    ON general_products (general_source_id, external_product_id)
    WHERE general_source_id IS NOT NULL AND external_product_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_general_products_source_content_hash
    ON general_products (general_source_id, content_hash)
    WHERE general_source_id IS NOT NULL AND external_product_id IS NULL AND content_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS general_product_chunks (
    id UUID PRIMARY KEY,
    general_product_id UUID NOT NULL REFERENCES general_products(id) ON DELETE CASCADE,
    general_source_id UUID NOT NULL REFERENCES general_sources(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    chunk_type VARCHAR(64) NOT NULL DEFAULT 'PRODUCT',
    metadata JSONB,
    content_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_general_product_chunks_product_hash UNIQUE (general_product_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_general_product_chunks_source
    ON general_product_chunks (general_source_id);

CREATE INDEX IF NOT EXISTS idx_general_product_chunks_hash
    ON general_product_chunks (content_hash);

CREATE TABLE IF NOT EXISTS general_import_runs (
    id UUID PRIMARY KEY,
    source_type VARCHAR(64) NOT NULL,
    source_ref VARCHAR(255) NOT NULL,
    general_source_id UUID REFERENCES general_sources(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL,
    products_seen INTEGER NOT NULL DEFAULT 0,
    products_imported INTEGER NOT NULL DEFAULT 0,
    products_updated INTEGER NOT NULL DEFAULT 0,
    chunks_seen INTEGER NOT NULL DEFAULT 0,
    chunks_imported INTEGER NOT NULL DEFAULT 0,
    chunks_updated INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_general_import_runs_source
    ON general_import_runs (general_source_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_general_import_runs_status
    ON general_import_runs (status);
