alter table tenant_kb_rebuild_status
    add column if not exists rebuild_history_json text;
