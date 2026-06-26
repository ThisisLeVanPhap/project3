CREATE TABLE IF NOT EXISTS crawl_materialize_jobs (
    id UUID PRIMARY KEY,
    source_code VARCHAR(160) NOT NULL,
    source_name VARCHAR(255),
    root_url TEXT,
    sitemap_url TEXT,
    product_urls JSONB,
    dataset_id VARCHAR(160),
    dataset_path TEXT,
    max_urls INTEGER NOT NULL DEFAULT 100,
    product_only BOOLEAN NOT NULL DEFAULT TRUE,
    run_quality_audit BOOLEAN NOT NULL DEFAULT TRUE,
    run_taxonomy_normalize BOOLEAN NOT NULL DEFAULT FALSE,
    register_dataset BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    product_count INTEGER NOT NULL DEFAULT 0,
    rag_chunk_count INTEGER NOT NULL DEFAULT 0,
    quality_status VARCHAR(32),
    error_message TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crawl_materialize_jobs_status
    ON crawl_materialize_jobs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_crawl_materialize_jobs_source
    ON crawl_materialize_jobs (source_code, created_at DESC);
