-- Demo UI seed data for screenshots only.
--
-- This script is intentionally NOT a Flyway migration.
-- It is safe to run manually when demo/screenshots need non-empty UI screens.
--
-- Rules:
-- - Do not use this data as experiment/evaluation results.
-- - No real Claude/API key is stored here.
-- - Product/reference catalog is not seeded here.
-- - Re-running is idempotent for the fixed DEMO ids below.

BEGIN;

-- Delete previous rows created by this seed, then insert a clean demo set.
DELETE FROM feedback
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM purchase_requests
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM leads
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM messages
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102',
    '00000000-0000-0000-0000-000000000000'
)
AND (
    conversation_id IN (
        '30000000-0000-4000-8000-000000000101',
        '30000000-0000-4000-8000-000000000102',
        '30000000-0000-4000-8000-000000000103',
        '30000000-0000-4000-8000-000000000104',
        '30000000-0000-4000-8000-000000000201',
        '30000000-0000-4000-8000-000000000202',
        '30000000-0000-4000-8000-000000000301',
        '30000000-0000-4000-8000-000000000302'
    )
);

DELETE FROM conversations
WHERE id IN (
    '30000000-0000-4000-8000-000000000101',
    '30000000-0000-4000-8000-000000000102',
    '30000000-0000-4000-8000-000000000103',
    '30000000-0000-4000-8000-000000000104',
    '30000000-0000-4000-8000-000000000201',
    '30000000-0000-4000-8000-000000000202',
    '30000000-0000-4000-8000-000000000301',
    '30000000-0000-4000-8000-000000000302'
);

DELETE FROM tenant_kb_rebuild_status
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM messenger_page_bindings
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM telegram_bot_bindings
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM tenant_members
WHERE tenant_id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

DELETE FROM chatbot_instances
WHERE id IN (
    '20000000-0000-4000-8000-000000000101',
    '20000000-0000-4000-8000-000000000102',
    '20000000-0000-4000-8000-000000000301',
    '20000000-0000-4000-8000-000000000302'
);

DELETE FROM tenants
WHERE id IN (
    '10000000-0000-4000-8000-000000000101',
    '10000000-0000-4000-8000-000000000102'
);

-- Ensure the public/system tenant exists for general_compare and market_price demo bots.
INSERT INTO tenants (id, code, name, status, api_key, kb_dir)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system_tenant',
    'System General Chat',
    'ACTIVE',
    'system-api-key-placeholder',
    'chatbot/kb/article'
)
ON CONFLICT (id) DO UPDATE
SET code = EXCLUDED.code,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    kb_dir = COALESCE(tenants.kb_dir, EXCLUDED.kb_dir);

-- Demo tenants.
INSERT INTO tenants (id, code, name, status, api_key, kb_dir)
VALUES
    (
        '10000000-0000-4000-8000-000000000101',
        'datn_demo_caco',
        'DEMO - Noi That CaCo Demo',
        'ACTIVE',
        'DEMO_TENANT_TOKEN_CACO_NOT_SECRET',
        'chatbot/kb/demo_caco'
    ),
    (
        '10000000-0000-4000-8000-000000000102',
        'datn_demo_moho',
        'DEMO - MOHO Demo',
        'ACTIVE',
        'DEMO_TENANT_TOKEN_MOHO_NOT_SECRET',
        'chatbot/kb/demo_moho'
    );

-- Demo tenant accounts. Password for all demo accounts: demo123
INSERT INTO tenant_members (id, tenant_id, email, display_name, password_hash, role, status)
VALUES
    ('11000000-0000-4000-8000-000000000101', '10000000-0000-4000-8000-000000000101', 'caco.admin@demo.local', 'DEMO CaCo Tenant Admin', '{noop}demo123', 'TENANT_ADMIN', 'ACTIVE'),
    ('11000000-0000-4000-8000-000000000102', '10000000-0000-4000-8000-000000000101', 'caco.member@demo.local', 'DEMO CaCo Tenant Member', '{noop}demo123', 'TENANT_MEMBER', 'ACTIVE'),
    ('11000000-0000-4000-8000-000000000201', '10000000-0000-4000-8000-000000000102', 'moho.admin@demo.local', 'DEMO MOHO Tenant Admin', '{noop}demo123', 'TENANT_ADMIN', 'ACTIVE'),
    ('11000000-0000-4000-8000-000000000202', '10000000-0000-4000-8000-000000000102', 'moho.member@demo.local', 'DEMO MOHO Tenant Member', '{noop}demo123', 'TENANT_MEMBER', 'ACTIVE');

-- Tenant sales chatbots. No real provider secret is stored.
INSERT INTO chatbot_instances (
    id, tenant_id, name, channel, persona, status,
    base_model, adapter_path, tokenizer_path, system_prompt,
    max_new_tokens, temperature, top_p, top_k,
    kb_dir, response_style, mode, provider, api_model, api_key, api_base_url
)
VALUES
    (
        '20000000-0000-4000-8000-000000000101',
        '10000000-0000-4000-8000-000000000101',
        'DEMO CaCo Sales Bot',
        'web',
        '{"tone":"friendly","purpose":"demo tenant_sales UI only","data_note":"DEMO/SAMPLE"}'::jsonb,
        'ACTIVE',
        NULL, NULL, NULL,
        'DEMO chatbot for UI screenshots only. Do not treat seed replies as evaluation evidence.',
        768, 0.7, 0.9, 50,
        'chatbot/kb/demo_caco',
        'natural',
        'tenant_sales',
        'claude',
        NULL, NULL, NULL
    ),
    (
        '20000000-0000-4000-8000-000000000102',
        '10000000-0000-4000-8000-000000000102',
        'DEMO MOHO Sales Bot',
        'web',
        '{"tone":"friendly","purpose":"demo tenant_sales UI only","data_note":"DEMO/SAMPLE"}'::jsonb,
        'ACTIVE',
        NULL, NULL, NULL,
        'DEMO chatbot for UI screenshots only. Do not treat seed replies as evaluation evidence.',
        768, 0.7, 0.9, 50,
        'chatbot/kb/demo_moho',
        'natural',
        'tenant_sales',
        'claude',
        NULL, NULL, NULL
    ),
    (
        '20000000-0000-4000-8000-000000000301',
        '00000000-0000-0000-0000-000000000000',
        'DEMO General Compare Bot',
        'web',
        '{"tone":"neutral","purpose":"demo general_compare UI only","data_note":"DEMO/SAMPLE"}'::jsonb,
        'ACTIVE',
        NULL, NULL, NULL,
        'DEMO public comparison chatbot. Uses configured Claude provider from environment only.',
        768, 0.7, 0.9, 50,
        'chatbot/kb/article',
        'structured',
        'general_compare',
        'claude',
        NULL, NULL, NULL
    ),
    (
        '20000000-0000-4000-8000-000000000302',
        '00000000-0000-0000-0000-000000000000',
        'DEMO Market Price Bot',
        'web',
        '{"tone":"careful","purpose":"demo market_price UI only","data_note":"DEMO/SAMPLE"}'::jsonb,
        'ACTIVE',
        NULL, NULL, NULL,
        'DEMO market price chatbot. Uses public/reference data only and does not create purchase requests.',
        768, 0.7, 0.9, 50,
        'chatbot/kb/article',
        'structured',
        'market_price',
        'claude',
        NULL, NULL, NULL
    );

-- Conversations.
INSERT INTO conversations (id, tenant_id, chatbot_id, user_external_id, created_at, status, lead_created, title)
VALUES
    ('30000000-0000-4000-8000-000000000101', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-001', NOW() - INTERVAL '6 days', 'ACTIVE', TRUE, 'DEMO - Khách hỏi sofa phòng khách nhỏ'),
    ('30000000-0000-4000-8000-000000000102', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-002', NOW() - INTERVAL '4 days', 'ACTIVE', TRUE, 'DEMO - Tư vấn bàn ăn gỗ'),
    ('30000000-0000-4000-8000-000000000103', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-003', NOW() - INTERVAL '2 days', 'ACTIVE', FALSE, 'DEMO - Hỏi chính sách giao hàng'),
    ('30000000-0000-4000-8000-000000000104', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-004', NOW() - INTERVAL '1 day', 'ACTIVE', TRUE, 'DEMO - Yêu cầu mua giường'),
    ('30000000-0000-4000-8000-000000000201', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-001', NOW() - INTERVAL '5 days', 'ACTIVE', TRUE, 'DEMO - Khách hỏi tủ quần áo'),
    ('30000000-0000-4000-8000-000000000202', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-002', NOW() - INTERVAL '3 days', 'ACTIVE', FALSE, 'DEMO - Tư vấn sofa tối giản'),
    ('30000000-0000-4000-8000-000000000301', '00000000-0000-0000-0000-000000000000', '20000000-0000-4000-8000-000000000301', 'demo-general-001', NOW() - INTERVAL '2 days', 'ACTIVE', FALSE, 'DEMO - So sánh sofa theo chất liệu'),
    ('30000000-0000-4000-8000-000000000302', '00000000-0000-0000-0000-000000000000', '20000000-0000-4000-8000-000000000302', 'demo-price-001', NOW() - INTERVAL '1 day', 'ACTIVE', FALSE, 'DEMO - Tham chiếu giá sofa');

-- Messages. These are sample UI messages, not chatbot evaluation output.
INSERT INTO messages (id, tenant_id, conversation_id, role, content, created_at)
VALUES
    ('31000000-0000-4000-8000-000000000101', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000101', 'user', 'DEMO: Tôi cần sofa gọn cho phòng khách nhỏ, ngân sách khoảng 15 triệu.', NOW() - INTERVAL '6 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000102', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000101', 'assistant', 'DEMO/SAMPLE: Mình đã ghi nhận nhu cầu sofa gọn cho phòng khách nhỏ. Bạn ưu tiên chất liệu gỗ, vải hay da?', NOW() - INTERVAL '6 days' + INTERVAL '2 minutes'),
    ('31000000-0000-4000-8000-000000000103', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000101', 'user', 'DEMO: Tên tôi là Nguyễn Văn Demo, số 0900000001, địa chỉ 01 Đường Demo, Quận 1.', NOW() - INTERVAL '6 days' + INTERVAL '3 minutes'),
    ('31000000-0000-4000-8000-000000000104', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000101', 'assistant', 'DEMO/SAMPLE: Mình đã ghi nhận yêu cầu mua hàng. Nhân viên cửa hàng sẽ liên hệ lại để xác nhận chi tiết.', NOW() - INTERVAL '6 days' + INTERVAL '4 minutes'),

    ('31000000-0000-4000-8000-000000000111', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000102', 'user', 'DEMO: Tôi muốn xem bàn ăn gỗ cho 4 người.', NOW() - INTERVAL '4 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000112', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000102', 'assistant', 'DEMO/SAMPLE: Bạn muốn phong cách hiện đại hay tối giản? Mình sẽ ghi nhận để nhân viên tư vấn mẫu phù hợp.', NOW() - INTERVAL '4 days' + INTERVAL '2 minutes'),

    ('31000000-0000-4000-8000-000000000121', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000103', 'user', 'DEMO: Cửa hàng có hỗ trợ giao hàng nội thành không?', NOW() - INTERVAL '2 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000122', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000103', 'assistant', 'DEMO/SAMPLE: Mình sẽ kiểm tra theo thông tin trong kho tri thức của cửa hàng; nếu thiếu dữ liệu, nhân viên sẽ xác nhận lại.', NOW() - INTERVAL '2 days' + INTERVAL '2 minutes'),

    ('31000000-0000-4000-8000-000000000131', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000104', 'user', 'DEMO: Tôi cần mua giường 1m6, tên Trần Demo, số 0900000004, địa chỉ 04 Đường Demo.', NOW() - INTERVAL '1 day' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000132', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000104', 'assistant', 'DEMO/SAMPLE: Mình đã ghi nhận yêu cầu mua giường demo và chuyển nhân viên xử lý.', NOW() - INTERVAL '1 day' + INTERVAL '2 minutes'),

    ('31000000-0000-4000-8000-000000000201', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000201', 'user', 'DEMO: Tôi muốn mua tủ quần áo cho phòng ngủ nhỏ.', NOW() - INTERVAL '5 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000202', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000201', 'assistant', 'DEMO/SAMPLE: Mình đã ghi nhận nhu cầu tủ quần áo cho phòng ngủ nhỏ. Bạn cho mình xin tên và số điện thoại demo nhé.', NOW() - INTERVAL '5 days' + INTERVAL '2 minutes'),
    ('31000000-0000-4000-8000-000000000211', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000202', 'user', 'DEMO: Tôi thích sofa tối giản màu be.', NOW() - INTERVAL '3 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000212', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000202', 'assistant', 'DEMO/SAMPLE: Mình đã ghi nhận phong cách tối giản và màu be. Bạn có ngân sách dự kiến không?', NOW() - INTERVAL '3 days' + INTERVAL '2 minutes'),

    ('31000000-0000-4000-8000-000000000301', '00000000-0000-0000-0000-000000000000', '30000000-0000-4000-8000-000000000301', 'user', 'DEMO: So sánh sofa gỗ và sofa vải theo chất liệu, phong cách và mục đích dùng.', NOW() - INTERVAL '2 days' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000302', '00000000-0000-0000-0000-000000000000', '30000000-0000-4000-8000-000000000301', 'assistant', 'DEMO/SAMPLE: Nguồn dữ liệu dùng cho minh họa giao diện. Các thông tin thiếu cần ghi rõ chưa có dữ liệu, không tạo yêu cầu mua hàng.', NOW() - INTERVAL '2 days' + INTERVAL '2 minutes'),
    ('31000000-0000-4000-8000-000000000311', '00000000-0000-0000-0000-000000000000', '30000000-0000-4000-8000-000000000302', 'user', 'DEMO: Sofa 14 triệu có cao bất thường không?', NOW() - INTERVAL '1 day' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000312', '00000000-0000-0000-0000-000000000000', '30000000-0000-4000-8000-000000000302', 'assistant', 'DEMO/SAMPLE: Đây chỉ là hội thoại minh họa UI; cần dùng dữ liệu tham chiếu thật khi đánh giá giá thị trường.', NOW() - INTERVAL '1 day' + INTERVAL '2 minutes');

-- Leads paired with purchase requests for tenant UI.
INSERT INTO leads (id, tenant_id, channel, conversation_id, customer_handle, status, slots_json, transcript, order_info, shipping_status, stage, created_at)
VALUES
    (9000001, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000101', 'demo-caco-web-001', 'CONTACTED', '{"product_type":"sofa","budget_text":"15 triệu","data_note":"DEMO/SAMPLE"}', 'DEMO transcript for screenshot only.', 'DEMO ghi chú: Khách muốn sofa gọn.', 'NEW', 'HANDOFF', NOW() - INTERVAL '6 days'),
    (9000002, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000102', 'demo-caco-web-002', 'CONTACTED', '{"product_type":"bàn ăn","data_note":"DEMO/SAMPLE"}', 'DEMO transcript for screenshot only.', 'DEMO ghi chú: Cần bàn ăn 4 người.', 'READY', 'HANDOFF', NOW() - INTERVAL '4 days'),
    (9000003, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000104', 'demo-caco-web-004', 'CONTACTED', '{"product_type":"giường","data_note":"DEMO/SAMPLE"}', 'DEMO transcript for screenshot only.', 'DEMO ghi chú: Giường 1m6.', 'NEW', 'HANDOFF', NOW() - INTERVAL '1 day'),
    (9000004, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000201', 'demo-moho-web-001', 'CONTACTED', '{"product_type":"tủ quần áo","data_note":"DEMO/SAMPLE"}', 'DEMO transcript for screenshot only.', 'DEMO ghi chú: Tủ cho phòng ngủ nhỏ.', 'SHIPPED', 'HANDOFF', NOW() - INTERVAL '5 days');

SELECT setval(pg_get_serial_sequence('leads', 'id'), GREATEST((SELECT MAX(id) FROM leads), 9000004), true);

INSERT INTO purchase_requests (
    id, tenant_id, channel, conversation_id, lead_id,
    customer_name, phone, shipping_address, notes, status,
    requested_product_ref, assigned_to_member_id, claimed_at, created_at
)
VALUES
    (9100001, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000101', 9000001, 'Nguyễn Văn Demo', '0900000001', '01 Đường Demo, Phường Minh Họa, Quận 1, TP.HCM', 'DEMO/SAMPLE: Sofa gọn cho phòng khách nhỏ.', 'NEW', 'DEMO sofa phòng khách nhỏ', NULL, NULL, NOW() - INTERVAL '6 days'),
    (9100002, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000102', 9000002, 'Lê Thị Demo', '0900000002', '02 Đường Demo, Phường Minh Họa, Quận 3, TP.HCM', 'DEMO/SAMPLE: Bàn ăn gỗ cho 4 người.', 'CONTACTED', 'DEMO bàn ăn gỗ', '11000000-0000-4000-8000-000000000102', NOW() - INTERVAL '3 days', NOW() - INTERVAL '4 days'),
    (9100003, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000104', 9000003, 'Trần Demo', '0900000004', '04 Đường Demo, Phường Minh Họa, Quận 5, TP.HCM', 'DEMO/SAMPLE: Giường 1m6, cần nhân viên xác nhận lại.', 'COMPLETED', 'DEMO giường 1m6', '11000000-0000-4000-8000-000000000101', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
    (9100004, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000201', 9000004, 'Phạm Demo', '0900000003', '03 Đường Demo, Phường Minh Họa, Quận 7, TP.HCM', 'DEMO/SAMPLE: Tủ quần áo cho phòng ngủ nhỏ.', 'CONTACTED', 'DEMO tủ quần áo', '11000000-0000-4000-8000-000000000202', NOW() - INTERVAL '4 days', NOW() - INTERVAL '5 days');

SELECT setval(pg_get_serial_sequence('purchase_requests', 'id'), GREATEST((SELECT MAX(id) FROM purchase_requests), 9100004), true);

-- KB rebuild status for tenant ops UI. This is demonstration metadata only.
INSERT INTO tenant_kb_rebuild_status (
    tenant_id,
    last_rebuild_started_at,
    last_rebuild_finished_at,
    last_rebuild_status,
    last_rebuild_message,
    rebuild_history_json
)
VALUES
    (
        '10000000-0000-4000-8000-000000000101',
        NOW() - INTERVAL '7 days',
        NOW() - INTERVAL '7 days' + INTERVAL '2 minutes',
        'SUCCESS',
        'DEMO/SAMPLE: Rebuild status minh họa UI, không phải kết quả thực nghiệm.',
        '[{"startedAt":"DEMO","finishedAt":"DEMO","status":"SUCCESS","message":"DEMO/SAMPLE rebuild history for UI screenshot only"}]'
    ),
    (
        '10000000-0000-4000-8000-000000000102',
        NOW() - INTERVAL '6 days',
        NOW() - INTERVAL '6 days' + INTERVAL '3 minutes',
        'SUCCESS',
        'DEMO/SAMPLE: Rebuild status minh họa UI, không phải kết quả thực nghiệm.',
        '[{"startedAt":"DEMO","finishedAt":"DEMO","status":"SUCCESS","message":"DEMO/SAMPLE rebuild history for UI screenshot only"}]'
    );

COMMIT;
