ALTER TABLE tenant_members
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
    ADD COLUMN IF NOT EXISTS status VARCHAR(32);

UPDATE tenant_members
SET display_name = COALESCE(display_name, email),
    status = COALESCE(status, 'ACTIVE')
WHERE display_name IS NULL
   OR status IS NULL;

INSERT INTO tenant_members (id, tenant_id, email, display_name, password_hash, role, status)
SELECT
    gen_random_uuid(),
    t.id,
    'admin@demo.local',
    'Demo Tenant Admin',
    '{noop}admin123',
    'TENANT_ADMIN',
    'ACTIVE'
FROM tenants t
WHERE t.code = 'demo_tenant'
  AND NOT EXISTS (
      SELECT 1
      FROM tenant_members tm
      WHERE tm.tenant_id = t.id
        AND lower(tm.email) = 'admin@demo.local'
  );

INSERT INTO tenant_members (id, tenant_id, email, display_name, password_hash, role, status)
SELECT
    gen_random_uuid(),
    t.id,
    'member@demo.local',
    'Demo Tenant Member',
    '{noop}member123',
    'TENANT_MEMBER',
    'ACTIVE'
FROM tenants t
WHERE t.code = 'demo_tenant'
  AND NOT EXISTS (
      SELECT 1
      FROM tenant_members tm
      WHERE tm.tenant_id = t.id
        AND lower(tm.email) = 'member@demo.local'
  );
