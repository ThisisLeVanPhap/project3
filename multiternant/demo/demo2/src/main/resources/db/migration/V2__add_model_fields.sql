alter table chatbot_instances
    add column if not exists base_model varchar(255),
    add column if not exists adapter_path varchar(255),
    add column if not exists tokenizer_path varchar(255),
    add column if not exists system_prompt text,
    add column if not exists max_new_tokens int,
    add column if not exists temperature double precision,
    add column if not exists top_p double precision,
    add column if not exists top_k int;
