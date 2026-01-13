-- Bảng ánh xạ Telegram Bot -> (tenant_id, chatbot_id, bot_token)
CREATE TABLE IF NOT EXISTS telegram_bot_bindings (
                                                     id              UUID PRIMARY KEY,
                                                     tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chatbot_id       UUID NOT NULL REFERENCES chatbot_instances(id) ON DELETE CASCADE,

    bot_username     VARCHAR(64),
    bot_token        TEXT NOT NULL,           -- nên mã hoá ở tầng app hoặc DB
    secret_path      VARCHAR(128) NOT NULL,   -- random, dùng làm webhook path
    status           VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (secret_path),
    UNIQUE (tenant_id, chatbot_id)
    );

CREATE INDEX IF NOT EXISTS idx_telegram_bot_bindings_tenant_id
    ON telegram_bot_bindings(tenant_id);

CREATE INDEX IF NOT EXISTS idx_telegram_bot_bindings_chatbot_id
    ON telegram_bot_bindings(chatbot_id);
