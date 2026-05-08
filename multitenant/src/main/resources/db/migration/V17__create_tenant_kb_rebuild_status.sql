create table if not exists tenant_kb_rebuild_status (
    tenant_id uuid primary key,
    last_rebuild_started_at timestamptz,
    last_rebuild_finished_at timestamptz,
    last_rebuild_status varchar(32),
    last_rebuild_message text,
    constraint fk_tenant_kb_rebuild_status_tenant
        foreign key (tenant_id) references tenants(id) on delete cascade
);
