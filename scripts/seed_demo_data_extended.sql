-- Extended demo data: extra tenant conversations, leads, and purchase requests.
--
-- Run after scripts/seed_demo_data.sql.
-- This script is idempotent for the fixed EXTENDED DEMO ids below: it deletes
-- only rows that belong to this extension, then inserts them again.

BEGIN;

-- Remove rows from a previous run of this extension only.
DELETE FROM purchase_requests
WHERE id BETWEEN 9100005 AND 9100015;

DELETE FROM leads
WHERE id BETWEEN 9000005 AND 9000015;

DELETE FROM messages
WHERE conversation_id IN (
    '30000000-0000-4000-8000-000000000105',
    '30000000-0000-4000-8000-000000000106',
    '30000000-0000-4000-8000-000000000107',
    '30000000-0000-4000-8000-000000000108',
    '30000000-0000-4000-8000-000000000109',
    '30000000-0000-4000-8000-000000000110',
    '30000000-0000-4000-8000-000000000111',
    '30000000-0000-4000-8000-000000000112',
    '30000000-0000-4000-8000-000000000113',
    '30000000-0000-4000-8000-000000000114',
    '30000000-0000-4000-8000-000000000115'
);

DELETE FROM conversations
WHERE id IN (
    '30000000-0000-4000-8000-000000000105',
    '30000000-0000-4000-8000-000000000106',
    '30000000-0000-4000-8000-000000000107',
    '30000000-0000-4000-8000-000000000108',
    '30000000-0000-4000-8000-000000000109',
    '30000000-0000-4000-8000-000000000110',
    '30000000-0000-4000-8000-000000000111',
    '30000000-0000-4000-8000-000000000112',
    '30000000-0000-4000-8000-000000000113',
    '30000000-0000-4000-8000-000000000114',
    '30000000-0000-4000-8000-000000000115'
);

-- Each purchase request must have a distinct (tenant_id, conversation_id).
INSERT INTO conversations (id, tenant_id, chatbot_id, user_external_id, created_at, status, lead_created, title)
VALUES
    ('30000000-0000-4000-8000-000000000105', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-005', NOW() - INTERVAL '12 hours', 'ACTIVE', TRUE, 'EXT DEMO - Sofa da phong khach'),
    ('30000000-0000-4000-8000-000000000106', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-006', NOW() - INTERVAL '10 hours', 'ACTIVE', TRUE, 'EXT DEMO - Ban an 6 ghe'),
    ('30000000-0000-4000-8000-000000000107', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-007', NOW() - INTERVAL '8 hours', 'ACTIVE', TRUE, 'EXT DEMO - Ke tivi treo tuong'),
    ('30000000-0000-4000-8000-000000000108', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-003', NOW() - INTERVAL '7 hours', 'ACTIVE', TRUE, 'EXT DEMO - Giuong tang tre em'),
    ('30000000-0000-4000-8000-000000000109', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-004', NOW() - INTERVAL '6 hours', 'ACTIVE', TRUE, 'EXT DEMO - Ban lam viec tai nha'),
    ('30000000-0000-4000-8000-000000000110', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-008', NOW() - INTERVAL '5 hours', 'ACTIVE', TRUE, 'EXT DEMO - Ghe an boc da'),
    ('30000000-0000-4000-8000-000000000111', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-005', NOW() - INTERVAL '4 hours', 'ACTIVE', TRUE, 'EXT DEMO - Sofa don doc sach'),
    ('30000000-0000-4000-8000-000000000112', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-009', NOW() - INTERVAL '3 hours', 'ACTIVE', TRUE, 'EXT DEMO - Tu giay thong minh'),
    ('30000000-0000-4000-8000-000000000113', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-006', NOW() - INTERVAL '2 hours', 'ACTIVE', TRUE, 'EXT DEMO - Ban trang diem'),
    ('30000000-0000-4000-8000-000000000114', '10000000-0000-4000-8000-000000000101', '20000000-0000-4000-8000-000000000101', 'demo-caco-web-010', NOW() - INTERVAL '1 hour', 'ACTIVE', TRUE, 'EXT DEMO - Den chum phong khach'),
    ('30000000-0000-4000-8000-000000000115', '10000000-0000-4000-8000-000000000102', '20000000-0000-4000-8000-000000000102', 'demo-moho-web-007', NOW() - INTERVAL '30 minutes', 'ACTIVE', TRUE, 'EXT DEMO - Tham phong khach');

INSERT INTO messages (id, tenant_id, conversation_id, role, content, created_at)
VALUES
    ('31000000-0000-4000-8000-000000000401', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000105', 'user', 'EXT DEMO: Khach hoi sofa da phong khach, ngan sach 20 trieu.', NOW() - INTERVAL '12 hours' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000402', '10000000-0000-4000-8000-000000000101', '30000000-0000-4000-8000-000000000105', 'assistant', 'DEMO/SAMPLE: Bot ghi nhan nhu cau va chuyen nhan vien xu ly.', NOW() - INTERVAL '12 hours' + INTERVAL '2 minutes'),
    ('31000000-0000-4000-8000-000000000403', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000108', 'user', 'EXT DEMO: Khach can giuong tang tre em an toan.', NOW() - INTERVAL '7 hours' + INTERVAL '1 minute'),
    ('31000000-0000-4000-8000-000000000404', '10000000-0000-4000-8000-000000000102', '30000000-0000-4000-8000-000000000108', 'assistant', 'DEMO/SAMPLE: Bot xin thong tin lien he va tao yeu cau mua hang.', NOW() - INTERVAL '7 hours' + INTERVAL '2 minutes');

INSERT INTO leads (id, tenant_id, channel, conversation_id, customer_handle, status, slots_json, transcript, order_info, shipping_status, stage, created_at)
VALUES
    (9000005, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000105', 'demo-caco-web-005', 'NEW', '{"product_type":"sofa","budget_text":"20 trieu","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Sofa da that.', 'NEW', 'HANDOFF', NOW() - INTERVAL '12 hours'),
    (9000006, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000106', 'demo-caco-web-006', 'CONTACTED', '{"product_type":"ban an","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Ban an 6 ghe go oc cho.', 'READY', 'HANDOFF', NOW() - INTERVAL '10 hours'),
    (9000007, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000107', 'demo-caco-web-007', 'CONTACTED', '{"product_type":"ke tivi","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Ke tivi treo tuong.', 'NEW', 'HANDOFF', NOW() - INTERVAL '8 hours'),
    (9000008, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000108', 'demo-moho-web-003', 'NEW', '{"product_type":"giuong","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Giuong tang tre em.', 'NEW', 'HANDOFF', NOW() - INTERVAL '7 hours'),
    (9000009, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000109', 'demo-moho-web-004', 'CONTACTED', '{"product_type":"ban lam viec","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Ban lam viec tai nha.', 'SHIPPED', 'HANDOFF', NOW() - INTERVAL '6 hours'),
    (9000010, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000110', 'demo-caco-web-008', 'NEW', '{"product_type":"ghe an","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Ghe an boc da.', 'NEW', 'HANDOFF', NOW() - INTERVAL '5 hours'),
    (9000011, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000111', 'demo-moho-web-005', 'CONTACTED', '{"product_type":"sofa","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Sofa don doc sach.', 'READY', 'HANDOFF', NOW() - INTERVAL '4 hours'),
    (9000012, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000112', 'demo-caco-web-009', 'CONTACTED', '{"product_type":"tu giay","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Tu giay thong minh.', 'SHIPPED', 'HANDOFF', NOW() - INTERVAL '3 hours'),
    (9000013, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000113', 'demo-moho-web-006', 'NEW', '{"product_type":"ban trang diem","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Ban trang diem co guong den LED.', 'NEW', 'HANDOFF', NOW() - INTERVAL '2 hours'),
    (9000014, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000114', 'demo-caco-web-010', 'NEW', '{"product_type":"den tran","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Den chum phong khach.', 'NEW', 'HANDOFF', NOW() - INTERVAL '1 hour'),
    (9000015, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000115', 'demo-moho-web-007', 'CONTACTED', '{"product_type":"tham trai san","data_note":"DEMO/SAMPLE"}', 'EXT DEMO transcript.', 'DEMO/SAMPLE: Tham long ngan phong khach.', 'READY', 'HANDOFF', NOW() - INTERVAL '30 minutes');

SELECT setval(pg_get_serial_sequence('leads', 'id'), GREATEST((SELECT MAX(id) FROM leads), 9000015), true);

INSERT INTO purchase_requests (
    id, tenant_id, channel, conversation_id, lead_id,
    customer_name, phone, shipping_address, notes, status,
    requested_product_ref, assigned_to_member_id, claimed_at, created_at
)
VALUES
    (9100005, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000105', 9000005, 'Nguyen Van Extended1', '0900000005', '05 Duong Demo, Quan 1, TP.HCM', 'DEMO/SAMPLE: Sofa da that phong khach.', 'NEW', 'DEMO sofa da that', NULL, NULL, NOW() - INTERVAL '12 hours'),
    (9100006, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000106', 9000006, 'Le Thi Extended2', '0900000006', '06 Duong Demo, Quan 3, TP.HCM', 'DEMO/SAMPLE: Ban an 6 ghe go oc cho.', 'CONTACTED', 'DEMO ban an go oc cho', '11000000-0000-4000-8000-000000000102', NOW() - INTERVAL '9 hours', NOW() - INTERVAL '10 hours'),
    (9100007, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000107', 9000007, 'Tran Extended3', '0900000007', '07 Duong Demo, Quan 5, TP.HCM', 'DEMO/SAMPLE: Ke tivi treo tuong hien dai.', 'COMPLETED', 'DEMO ke tivi treo', '11000000-0000-4000-8000-000000000101', NOW() - INTERVAL '7 hours', NOW() - INTERVAL '8 hours'),
    (9100008, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000108', 9000008, 'Pham Extended4', '0900000008', '08 Duong Demo, Quan 7, TP.HCM', 'DEMO/SAMPLE: Giuong tang tre em an toan.', 'NEW', 'DEMO giuong tang tre em', NULL, NULL, NOW() - INTERVAL '7 hours'),
    (9100009, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000109', 9000009, 'Vo Extended5', '0900000009', '09 Duong Demo, Quan 2, TP.HCM', 'DEMO/SAMPLE: Ban lam viec tai nha ergonomic.', 'COMPLETED', 'DEMO ban lam viec', '11000000-0000-4000-8000-000000000202', NOW() - INTERVAL '5 hours', NOW() - INTERVAL '6 hours'),
    (9100010, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000110', 9000010, 'Hoang Extended6', '0900000010', '10 Duong Demo, Quan 4, TP.HCM', 'DEMO/SAMPLE: Ghe an boc da cao cap.', 'NEW', 'DEMO ghe an boc da', NULL, NULL, NOW() - INTERVAL '5 hours'),
    (9100011, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000111', 9000011, 'Dang Extended7', '0900000011', '11 Duong Demo, Quan 9, TP.HCM', 'DEMO/SAMPLE: Sofa don doc sach thu gian.', 'CONTACTED', 'DEMO sofa don', '11000000-0000-4000-8000-000000000201', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '4 hours'),
    (9100012, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000112', 9000012, 'Ngo Extended8', '0900000012', '12 Duong Demo, Quan 6, TP.HCM', 'DEMO/SAMPLE: Tu giay thong minh xoay.', 'COMPLETED', 'DEMO tu giay thong minh', '11000000-0000-4000-8000-000000000102', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '3 hours'),
    (9100013, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000113', 9000013, 'Truong Extended9', '0900000013', '13 Duong Demo, Quan 8, TP.HCM', 'DEMO/SAMPLE: Ban trang diem guong den LED.', 'NEW', 'DEMO ban trang diem', NULL, NULL, NOW() - INTERVAL '2 hours'),
    (9100014, '10000000-0000-4000-8000-000000000101', 'web', '30000000-0000-4000-8000-000000000114', 9000014, 'Mai Extended10', '0900000014', '14 Duong Demo, Quan 10, TP.HCM', 'DEMO/SAMPLE: Den chum pha le phong khach.', 'NEW', 'DEMO den chum pha le', NULL, NULL, NOW() - INTERVAL '1 hour'),
    (9100015, '10000000-0000-4000-8000-000000000102', 'web', '30000000-0000-4000-8000-000000000115', 9000015, 'Bui Extended11', '0900000015', '15 Duong Demo, Quan 11, TP.HCM', 'DEMO/SAMPLE: Tham long ngan phong khach.', 'CONTACTED', 'DEMO tham trai san', '11000000-0000-4000-8000-000000000201', NOW() - INTERVAL '20 minutes', NOW() - INTERVAL '30 minutes');

SELECT setval(pg_get_serial_sequence('purchase_requests', 'id'), GREATEST((SELECT MAX(id) FROM purchase_requests), 9100015), true);

COMMIT;
