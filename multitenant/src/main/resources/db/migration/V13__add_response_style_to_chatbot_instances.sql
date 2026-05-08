alter table chatbot_instances
    add column if not exists response_style varchar(32);
