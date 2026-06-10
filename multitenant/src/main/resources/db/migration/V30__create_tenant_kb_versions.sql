create table if not exists tenant_kb_versions (
    id uuid primary key,
    tenant_id uuid not null,
    version_tag varchar(64) not null,
    kb_dir varchar(1024) not null,
    source_url_snapshot text,
    artifact_count integer,
    status varchar(32) not null,
    build_message text,
    built_at timestamptz,
    published_at timestamptz,
    created_at timestamptz not null default now(),
    constraint fk_tenant_kb_versions_tenant
        foreign key (tenant_id) references tenants(id) on delete cascade,
    constraint uq_tenant_kb_versions_tenant_version_tag
        unique (tenant_id, version_tag)
);

alter table tenants
    add column if not exists active_kb_version_id uuid;

create index if not exists idx_tenant_kb_versions_tenant_status
    on tenant_kb_versions(tenant_id, status);

create index if not exists idx_tenant_kb_versions_tenant_built_at
    on tenant_kb_versions(tenant_id, built_at);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'fk_tenants_active_kb_version'
    ) then
        alter table tenants
            add constraint fk_tenants_active_kb_version
                foreign key (active_kb_version_id) references tenant_kb_versions(id) on delete set null;
    end if;
end $$;
