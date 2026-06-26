CREATE TABLE IF NOT EXISTS general_products (
    id UUID PRIMARY KEY,
    dataset_record_id UUID NOT NULL REFERENCES product_datasets(id) ON DELETE CASCADE,
    artifact_id UUID REFERENCES product_dataset_artifacts(id) ON DELETE SET NULL,
    dataset_id VARCHAR(160) NOT NULL,
    artifact_build_tag VARCHAR(96),
    source VARCHAR(120),
    source_url TEXT,
    product_id VARCHAR(160),
    sku VARCHAR(160),
    name VARCHAR(512),
    category VARCHAR(160),
    brand VARCHAR(160),
    material VARCHAR(255),
    dimensions VARCHAR(255),
    price NUMERIC(14, 2),
    currency VARCHAR(16),
    product_url TEXT,
    image_url TEXT,
    description TEXT,
    visibility VARCHAR(32) NOT NULL DEFAULT 'GLOBAL_PUBLIC',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    content_hash VARCHAR(128),
    raw JSONB,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_general_products_visibility_status
    ON general_products (visibility, status);

CREATE INDEX IF NOT EXISTS idx_general_products_dataset
    ON general_products (dataset_id);

CREATE INDEX IF NOT EXISTS idx_general_products_artifact
    ON general_products (artifact_id);

CREATE INDEX IF NOT EXISTS idx_general_products_category
    ON general_products (category);

CREATE INDEX IF NOT EXISTS idx_general_products_product_id
    ON general_products (product_id);

CREATE INDEX IF NOT EXISTS idx_general_products_name_lower
    ON general_products (LOWER(name));

CREATE UNIQUE INDEX IF NOT EXISTS uq_general_products_artifact_product_id
    ON general_products (artifact_id, product_id)
    WHERE product_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_general_products_artifact_content_hash
    ON general_products (artifact_id, content_hash)
    WHERE product_id IS NULL AND content_hash IS NOT NULL;
