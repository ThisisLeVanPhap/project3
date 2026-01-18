alter table chatbot_instances
    add column if not exists kb_dir varchar(255);
