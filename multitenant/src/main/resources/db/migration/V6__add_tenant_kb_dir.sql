alter table tenants
    add column if not exists kb_dir varchar(255);
