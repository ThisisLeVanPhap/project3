create table product_datasets (
    id uuid primary key,
    dataset_id varchar(160) not null,
    source varchar(120),
    source_url varchar(1024),
    version varchar(120),
    path varchar(1024) not null,
    product_count integer,
    rag_chunk_count integer,
    content_hash varchar(128),
    manifest_path varchar(1024),
    created_at timestamp with time zone,
    registered_at timestamp with time zone not null,
    status varchar(32) not null,
    last_assigned_tenant_id uuid,
    last_assigned_at timestamp with time zone,
    constraint uq_product_datasets_dataset_id unique (dataset_id)
);

create index idx_product_datasets_source on product_datasets(source);
create index idx_product_datasets_status on product_datasets(status);
create index idx_product_datasets_registered_at on product_datasets(registered_at);

alter table tenant_kb_versions
    add column source_type varchar(64);

alter table tenant_kb_versions
    add column dataset_id varchar(160);

create index idx_tenant_kb_versions_dataset_id on tenant_kb_versions(dataset_id);
