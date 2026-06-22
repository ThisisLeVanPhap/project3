create table if not exists product_dataset_artifacts (
    id uuid primary key,
    dataset_record_id uuid not null,
    dataset_id varchar(160) not null,
    build_tag varchar(96) not null,
    artifact_path varchar(1024) not null,
    artifact_count integer,
    quality_status varchar(32),
    status varchar(32) not null,
    build_message text,
    built_at timestamp with time zone,
    created_at timestamp with time zone not null default now(),
    constraint fk_product_dataset_artifacts_dataset
        foreign key (dataset_record_id) references product_datasets(id) on delete cascade,
    constraint uq_product_dataset_artifacts_dataset_build
        unique (dataset_id, build_tag)
);

create index if not exists idx_product_dataset_artifacts_dataset_built_at
    on product_dataset_artifacts(dataset_id, built_at desc);

create index if not exists idx_product_dataset_artifacts_status
    on product_dataset_artifacts(status);

create table if not exists tenant_kb_bindings (
    id uuid primary key,
    tenant_id uuid not null,
    artifact_id uuid,
    dataset_id varchar(160) not null,
    active boolean not null default true,
    update_policy varchar(32) not null,
    active_kb_version_id uuid,
    bound_at timestamp with time zone,
    unbound_at timestamp with time zone,
    created_at timestamp with time zone not null default now(),
    updated_at timestamp with time zone not null default now(),
    constraint fk_tenant_kb_bindings_tenant
        foreign key (tenant_id) references tenants(id) on delete cascade,
    constraint fk_tenant_kb_bindings_artifact
        foreign key (artifact_id) references product_dataset_artifacts(id) on delete set null,
    constraint fk_tenant_kb_bindings_active_version
        foreign key (active_kb_version_id) references tenant_kb_versions(id) on delete set null
);

create index if not exists idx_tenant_kb_bindings_tenant_active
    on tenant_kb_bindings(tenant_id, active);

create index if not exists idx_tenant_kb_bindings_dataset_active
    on tenant_kb_bindings(dataset_id, active);

create index if not exists idx_tenant_kb_bindings_artifact
    on tenant_kb_bindings(artifact_id);
