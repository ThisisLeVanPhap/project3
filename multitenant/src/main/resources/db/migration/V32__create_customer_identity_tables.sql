create table if not exists unified_customers (
    id uuid primary key,
    tenant_id uuid not null,
    display_name varchar(255),
    normalized_phone varchar(64),
    normalized_email varchar(255),
    created_at timestamptz not null default now(),
    updated_at timestamptz
);

create index if not exists idx_unified_customers_tenant_phone
    on unified_customers (tenant_id, normalized_phone);

create index if not exists idx_unified_customers_tenant_email
    on unified_customers (tenant_id, normalized_email);

create table if not exists customer_identities (
    id uuid primary key,
    tenant_id uuid not null,
    unified_customer_id uuid not null,
    channel varchar(64) not null,
    external_user_id varchar(512) not null,
    display_name varchar(255),
    created_at timestamptz not null default now(),
    last_seen_at timestamptz,
    constraint fk_customer_identities_unified_customer
        foreign key (unified_customer_id) references unified_customers(id) on delete cascade,
    constraint uq_customer_identity_external
        unique (tenant_id, channel, external_user_id)
);

create index if not exists idx_customer_identities_tenant_customer
    on customer_identities (tenant_id, unified_customer_id);
