-- ===============================================
-- V1__init_global_schema.sql
-- Khởi tạo toàn bộ schema cho hệ thống multi-tenant
-- Database: global_admin
-- ===============================================

-- =====================
-- Bảng tenants (quản lý tenant)
-- =====================
CREATE TABLE IF NOT EXISTS tenants (
                                       id          UUID PRIMARY KEY,
                                       code        VARCHAR(64)  UNIQUE NOT NULL,
    name        VARCHAR(255) NOT NULL,
    status      VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
    api_key     VARCHAR(128) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    );

-- =====================
-- Bảng tenant_members (người dùng trong tenant)
-- =====================
CREATE TABLE IF NOT EXISTS tenant_members (
                                              id         UUID PRIMARY KEY,
                                              tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email      VARCHAR(255) NOT NULL,
    role       VARCHAR(32)  NOT NULL,
    UNIQUE (tenant_id, email)
    );

-- =====================
-- Bảng chatbot_instances (mỗi chatbot đại diện một phong cách bán hàng)
-- =====================
CREATE TABLE IF NOT EXISTS chatbot_instances (
                                                 id          UUID PRIMARY KEY,
                                                 tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(128) NOT NULL,
    channel     VARCHAR(32)  NOT NULL, -- web / facebook / zalo / ...
    persona     JSONB NOT NULL DEFAULT '{}'::jsonb, -- mô tả phong cách, tone, v.v.
    status      VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- =====================
-- Bảng conversations (cuộc hội thoại giữa người dùng và chatbot)
-- =====================
CREATE TABLE IF NOT EXISTS conversations (
                                             id              UUID PRIMARY KEY,
                                             tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chatbot_id      UUID NOT NULL REFERENCES chatbot_instances(id) ON DELETE CASCADE,
    user_external_id VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- =====================
-- Bảng messages (tin nhắn trong hội thoại)
-- =====================
CREATE TABLE IF NOT EXISTS messages (
                                        id               UUID PRIMARY KEY,
                                        tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             VARCHAR(16) NOT NULL, -- user / assistant / system
    content          TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

-- =====================
-- Indexes cho hiệu năng (idempotent: chỉ tạo nếu chưa có)
-- =====================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_instances_tenant'
  ) THEN
CREATE INDEX idx_instances_tenant ON chatbot_instances(tenant_id);
END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_conversations_tenant'
  ) THEN
CREATE INDEX idx_conversations_tenant ON conversations(tenant_id);
END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_messages_tenant'
  ) THEN
CREATE INDEX idx_messages_tenant ON messages(tenant_id);
END IF;
END $$;

-- =====================
-- Insert dữ liệu mẫu (tuỳ chọn)
-- =====================
INSERT INTO tenants (id, code, name, status, api_key)
VALUES
    (gen_random_uuid(), 'demo_tenant', 'Demo Tenant', 'ACTIVE', md5(random()::text || clock_timestamp()::text))
    ON CONFLICT (code) DO NOTHING;

-- ===============================================
-- ✅ Hoàn tất migration V1
-- ===============================================
