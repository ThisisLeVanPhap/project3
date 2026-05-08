# REGRESSION CHECKLIST

Hướng dẫn sử dụng:
- Đánh dấu ✅ khi test case pass
- Đánh dấu ❌ khi test case fail
- Ghi chú bug/issue vào phần Notes nếu có

---

## 1. General Chat - Start/Send/Reload

**PRECONDITIONS:**
- Backend server running on port 8080
- Frontend serving correctly
- Database accessible with test data or fresh state
- User has not logged in (guest session)

### Test Case 1.1: Start new general chat conversation
**Steps:**
1. Navigate to `/chat/general/`
2. Observe sidebar state
3. Type "Xin chào" into input field
4. Click Send button or press Enter

**Expected Results:**
- ✅ Page loads without error (200 OK)
- ✅ Sidebar shows empty state "Chưa có cuộc trò chuyện nào" or prior conversations
- ✅ Input field is focused and enabled
- ✅ User message appears immediately in chat with "user" avatar/alignment
- ✅ Typing indicator shows within 2 seconds
- ✅ Assistant response arrives within 30 seconds
- ✅ Assistant response displays with correct formatting
- ✅ New conversation appears in sidebar with auto-generated title
- ✅ Title shows first ~30 characters of first message

**Negative Tests:**
- [ ] Send empty message -> button disabled or no send
- [ ] Very long message (>5000 chars) -> truncated or accepted
- [ ] XSS attempt in message -> sanitized in display

**Edge Cases:**
- [ ] Multiple rapid messages before first response -> queued correctly
- [ ] Concurrent tab sessions -> both work independently

### Test Case 1.2: Send messages in existing conversation
**Steps:**
1. Select an existing conversation from sidebar (if any)
2. Verify all prior messages load
3. Type "Tôi cần mua bàn ăn" and send
4. Wait for response
5. Type "Khoảng bao nhiêu tiền?" and send

**Expected Results:**
- ✅ Selected conversation highlights in sidebar
- ✅ All messages from conversation load with correct timestamps
- ✅ Messages display in chronological order (oldest top)
- ✅ Each send appends to bottom
- ✅ Auto-scroll activates after each new message
- ✅ Input field refocuses after each response
- ✅ Typing indicator shows before each response

**Negative Tests:**
- [ ] Select conversation while another loading -> handles gracefully
- [ ] Network interruption during send -> retry/error handling

**Edge Cases:**
- [ ] Conversation with 100+ messages -> pagination or infinite scroll works
- [ ] Very old conversation -> all messages load correctly

### Test Case 1.3: Reload page preserves conversation
**Steps:**
1. Open general chat, select a conversation
2. Type partial message "Tôi thích phong cách" (do not send)
3. Press F5 to refresh page
4. Observe state after reload

**Expected Results:**
- ✅ Page reloads successfully
- ✅ Same conversation remains selected in sidebar
- ✅ All messages from conversation display
- ✅ Partial draft text remains in input field (if implemented)
- ✅ Typing indicator not stuck showing
- ✅ Scroll position near bottom preserved

**Negative Tests:**
- [ ] Refresh with no conversation selected -> returns to empty state
- [ ] Refresh with invalid conversation ID in URL -> redirects to empty or 404

**Edge Cases:**
- [ ] Refresh during assistant response -> response preserved or reloaded
- [ ] Browser back/forward navigation -> state consistent

---

## 2. Tenant Chat - Start/Send/Reload

**PRECONDITIONS:**
- At least one tenant and chatbot instance exists in DB
- Tenant has uploaded KB documents (for RAG)
- Valid `tenantId` and `chatbotId` parameters available

### Test Case 2.1: Start tenant chat với tenantId
**Steps:**
1. Navigate to `/chat?tenantId=<tenant1>&chatbotId=<bot1>` with valid IDs
2. Observe page load and UI elements
3. Check network tab for API calls
4. Send message "Tôi cần bàn làm việc"

**Expected Results:**
- ✅ Page loads without redirect or error
- ✅ Chat header shows tenant name/branding (if configured)
- ✅ Sidebar shows only conversations belonging to this tenant
- ✅ First message sent successfully
- ✅ Assistant response includes information from tenant's KB (check for product names)
- ✅ API calls include `X-Tenant-ID` header or equivalent
- ✅ New conversation created with correct `tenantId` in DB

**Negative Tests:**
- [ ] Invalid `tenantId` -> redirect to error or landing page
- [ ] Missing `chatbotId` -> default chatbot or error
- [ ] Tenant exists but has no KB -> still works but no RAG context
- [ ] `tenantId` from URL A, try to access conversation from tenant B -> blocked

**Edge Cases:**
- [ ] Multiple tenantId params -> first one used
- [ ] Tenant chat without tenantId param -> behaves as general or redirects

### Test Case 2.2: Send messages với tenant context
**Steps:**
1. In tenant chat, send: "Các bạn có bàn gỗ sồi không?"
2. Send: "Giá bao nhiêu?"
3. Send: "Có màu gì?"

**Expected Results:**
- ✅ Responses reference specific products from tenant's KB
- ✅ Assistant mentions tenant store information
- ✅ Messages stored with correct `tenantId` and `chatbotInstanceId`
- ✅ If logged in, `userExternalId` set; if guest, guest identifier used
- ✅ Switching to different tenant URL shows different conversations only

**Negative Tests:**
- [ ] Ask about competitor's products -> redirect or neutral response
- [ ] Send message with SQL injection attempt -> sanitized, no error

**Edge Cases:**
- [ ] Tenant with empty KB -> generic responses still work
- [ ] Multiple concurrent sessions same tenant -> isolated conversations

### Test Case 2.3: Reload preserves tenant chat
**Steps:**
1. In tenant chat with URL params, have active conversation
2. Type "Tôi thích bàn gỗ" (partial, unsent)
3. Refresh page (F5)
4. Check URL and UI state

**Expected Results:**
- ✅ URL retains `?tenantId=<value>&chatbotId=<value>`
- ✅ Same conversation selected
- ✅ All messages preserved
- ✅ Partial draft text retained in input
- ✅ Tenant branding/header still visible
- ✅ No redirect to general chat

**Negative Tests:**
- [ ] Remove tenantId from URL manually -> loses context or redirects
- [ ] Tamper with chatbotId -> handles gracefully

**Edge Cases:**
- [ ] Reload during response -> response preserved or continues
- [ ] Bookmark tenant chat URL -> opens correctly on new tab

---

## 3. Rename Conversation

**PRECONDITIONS:**
- At least one conversation exists (in general or tenant chat)
- User has permission to modify that conversation (owner or admin)
- Conversation sidebar is visible

### Test Case 3.1: Rename general conversation
**Steps:**
1. Go to `/chat/general/`
2. Hover over conversation name in sidebar
3. Click the edit icon (pencil) or directly on title
4. Type "Nội thất hiện đại" and press Enter
5. Observe UI update

**Expected Results:**
- ✅ Inline edit field appears with current title selected
- ✅ Can edit text freely
- ✅ Press Enter saves and blurs field
- ✅ Click outside shows confirmation dialog or cancels
- ✅ Title updates immediately in sidebar
- ✅ DB `conversation.title` column updated
- ✅ Other UI elements (header if visible) also update

**Negative Tests:**
- [ ] Click edit, press Esc -> cancels edit, original title remains
- [ ] Enter empty string -> shows validation error or reverts
- [ ] Enter 500 characters -> truncates to 255 or rejects
- [ ] Special chars: `<>'"&` -> sanitized or preserved appropriately
- [ ] Edit another user's conversation -> blocked (permission error)

**Edge Cases:**
- [ ] Rapid double-click edit -> handles gracefully (one edit at a time)
- [ ] Edit while title being auto-updated (from first message) -> no conflict

### Test Case 3.2: Rename tenant conversation
**Steps:**
1. Go to `/chat?tenantId=<tenant1>&chatbotId=<bot1>`
2. Open conversation dropdown
3. Click rename on a conversation
4. Rename to "Khách hàng ABC"
5. Verify DB

**Expected Results:**
- ✅ Rename succeeds
- ✅ Title updates in both general and tenant views
- ✅ DB record shows new title for that tenant's conversation
- ✅ Other tenants cannot see this rename

**Negative Tests:**
- [ ] Rename with tenantId mismatch -> blocked
- [ ] Rename conversation from another tenant -> not visible/blocked

**Edge Cases:**
- [ ] Same title as before -> no change, no error
- [ ] Unicode/emojis in title -> displays correctly

### Test Case 3.3: Title validation edge cases
**Steps:**
1. Attempt rename with various inputs:
   - Empty: ""
   - Whitespace only: "   "
   - 300 chars string
   - SQL: `'; DROP TABLE conversations; --`
   - HTML: `<script>alert(1)</script>`
   - Emojis: "😀😀😀😀😀"

**Expected Results:**
- ✅ Empty/whitespace -> rejected, shows "Title required" or reverts
- ✅ Too long -> truncates to 255 or shows error
- ✅ Malicious input -> stored safely, displayed escaped (no XSS)
- ✅ Emojis -> stored and displayed correctly (UTF-8)

**Negative Tests:**
- [ ] XSS in title -> not executed in browser
- [ ] SQL injection -> parameterized query prevents injection

---

## 4. Delete Conversation

**PRECONDITIONS:**
- At least one conversation exists
- User has permission to delete (owner or admin)
- Understand that deletion may be permanent or soft-delete

### Test Case 4.1: Delete general conversation
**Steps:**
1. Go to `/chat/general/`
2. Hover over conversation in sidebar
3. Click delete icon (X/trash)
4. In confirmation dialog, click "Delete" or "OK"
5. Observe sidebar

**Expected Results:**
- ✅ Confirmation dialog appears with message "Delete conversation?"
- ✅ Dialog has Cancel and Delete buttons
- ✅ Clicking Cancel closes dialog, conversation remains
- ✅ Clicking Delete removes conversation from sidebar immediately
- ✅ Conversation disappears from list
- ✅ If conversation was selected, chat area shows empty state
- ✅ DB record is soft-deleted (`deleted = true`) or hard deleted
- ✅ API returns success status (200/204)

**Negative Tests:**
- [ ] Click delete, then Cancel -> conversation stays
- [ ] Network failure during delete -> error message, data intact
- [ ] Delete already-deleted conversation -> "Not found" response
- [ ] Delete another user's conversation -> 403 Forbidden

**Edge Cases:**
- [ ] Delete while conversation loading -> cancels load, removes from list
- [ ] Delete and immediately undo (if undo feature exists) -> restores
- [ ] Delete with unsent draft -> draft lost (expected)

### Test Case 4.2: Delete tenant conversation
**Steps:**
1. Go to `/chat?tenantId=<tenant1>&chatbotId=<bot1>`
2. Delete a conversation
3. Switch to `/chat?tenantId=<tenant2>&chatbotId=<bot2>`
4. Verify tenant1's conversation not visible

**Expected Results:**
- ✅ Deletion only affects specified tenant's conversation
- ✅ Tenant 2's conversations unaffected
- ✅ API enforces tenant boundary on delete
- ✅ Cross-tenant delete attempt fails

**Negative Tests:**
- [ ] Delete with wrong tenantId in URL -> 404 or 403
- [ ] Delete conversation ID that belongs to other tenant -> blocked

**Edge Cases:**
- [ ] Delete all conversations in tenant -> sidebar empty, no crash
- [ ] Delete while RAG fetching -> cancelled cleanly

### Test Case 4.3: Bulk delete / multiple deletes
**Steps:**
1. Have 3 conversations
2. Delete first conversation
3. Observe second conversation (now first) still accessible
4. Delete second conversation
5. Check third conversation

**Expected Results:**
- ✅ Each delete operates on correct item
- ✅ Index/selection updates correctly after deletion
- ✅ No off-by-one errors in list

**Negative Tests:**
- [ ] Rapid-fire delete clicks -> only first counts or graceful handling

**Edge Cases:**
- [ ] Delete only conversation -> empty state shows properly
- [ ] Delete while sorting/filtering -> state consistent

---

## 5. Auto Title Generation

**PRECONDITIONS:**
- Fresh conversation (no messages yet) or title can be regenerated
- First message will determine title

### Test Case 5.1: Title from first user message
**Steps:**
1. Start new general chat
2. Send first message: "Tôi đang tìm sofa cho phòng khách 30m2, ngân sách khoảng 15 triệu"
3. Observe sidebar title immediately and after 1 second

**Expected Results:**
- ✅ Title captures essence: first ~30-50 characters OR intelligently truncated at word boundary
- ✅ Title shows within 1 second of sending first message
- ✅ Truncation adds "..." if cut mid-sentence
- ✅ Special characters preserved appropriately
- ✅ No raw HTML/script in title

**Negative Tests:**
- [ ] First message empty -> title "New conversation" or timestamp-based
- [ ] First message only whitespace -> fallback title

**Edge Cases:**
- [ ] First message 500 chars -> intelligently truncated (not mid-word if possible)
- [ ] First message all emojis -> shows as emojis or "New conversation"

### Test Case 5.2: Title truncation for long messages
**Steps:**
1. Start new conversation
2. Send message with 200+ characters: paste long paragraph
3. Check title in sidebar

**Expected Results:**
- ✅ Title truncated to reasonable length (e.g., 50 chars)
- ✅ Ends with "..." if truncated
- ✅ Cut at reasonable boundary (space, punctuation), not mid-word if avoidable
- ✅ Hover shows full message as tooltip (if implemented)

**Negative Tests:**
- [ ] No truncation -> sidebar layout breaks
- [ ] Truncate at exactly N chars, mid-char for multibyte -> displays correctly

**Edge Cases:**
- [ ] CJK characters (no spaces) -> truncate at character count
- [ ] Title exactly at limit -> no "..." needed

### Test Case 5.3: Fallback title for empty/invalid message
**Steps:**
1. Start new conversation
2. Send: "   " (5 spaces)
3. Observe title
4. Send: "😀😀😀😀😀😀😀😀"
5. Observe title

**Expected Results:**
- ✅ Whitespace-only -> fallback "Cuộc trò chuyện mới" or timestamp
- ✅ Emoji-only -> either shows emojis (if safe) or fallback
- ✅ Fallback title distinguishes from normal titles
- ✅ Never shows blank title

**Negative Tests:**
- [ ] Fallback not implemented -> blank or null causes UI error

**Edge Cases:**
- [ ] Title regeneration after rename -> does NOT overwrite manual title
- [ ] Title from system message (not user) -> fallback used

---

## 6. Lead Capture Flow

### Test Case 6.1: Tenant chat - lead creation
- [ ] Vào tenant chat
- [ ] Tư vấn đến stage close, user thể hiện mua hàng
- [ ] Assistant hỏi thông tin liên hệ
- [ ] User cung cấp: tên, phone, email
- [ ] Backend tạo `Lead` record
- [ ] Backend tạo `PurchaseRequest`
- [ ] Conversation đánh dấu `leadCreated = true`
- [ ] UI có thể hiển thị thông báo "Lead captured"

### Test Case 6.2: Lead validation
- [ ] Nhập phone không hợp lệ -> validation fail
- [ ] Nhập email không hợp lệ -> validation fail
- [ ] Nhập đủ thông tin -> tạo lead thành công

### Test Case 6.3: Lead data persistence
- [ ] Kiểm tra DB: Lead có đầy đủ fields
- [ ] Lead.tenantId đúng
- [ ] Lead.chatbotInstanceId đúng
- [ ] Lead.conversationId đúng

---

## 7. Duplicate Lead Prevention

### Test Case 7.1: Prevent duplicate lead trong cùng conversation
- [ ] Trong cùng conversation, hoàn tất lead capture lần 1
- [ ] Thử capture lại (tiếp tục chat và qualify lần 2)
- [ ] Hệ thống KHÔNG tạo lead mới
- [ ] Có thông báo "Lead đã được tạo" hoặc tương tự

### Test Case 7.2: Prevent duplicate lead qua phone/email
- [ ] Tạo lead với phone "0901234567"
- [ ] Với conversation khác (cùng tenant), nhập cùng phone
- [ ] Hệ thống phát hiện duplicate
- [ ] Từ chối tạo lead mới, hoặc merge vào lead cũ

### Test Case 7.3: Duplicate check cross-tenant
- [ ] Tenant A có lead với phone X
- [ ] Tenant B dùng cùng phone X
- [ ] Tenant B VẪN có thể tạo lead (không bị block bởi tenant khác)

---

## 8. Off-Topic Redirect

### Test Case 8.1: General chat - off-topic detection
- [ ] Bắt đầu conversation về nội thất
- [ ] Chuyển sang chủ đề không liên quan (ví dụ: "Thời tiết hôm nay thế nào?")
- [ ] Assistant redirect về chủ đề interior
- [ ] Assistant trả lời: "Tôi là trợ lý nội thất, tôi có thể giúp gì về..."

### Test Case 8.2: Tenant chat - off-topic detection
- [ ] Trong tenant chat (ví dụ: furniture store)
- [ ] Hỏi về chủ trình du lịch
- [ ] Assistant redirect về furniture/products của tenant

### Test Case 8.3: Repeated off-topic
- [ ] Off-topic nhiều lần
- [ ] Assistant vẫn giữ redirect, không bực mình
- [ ] Vẫn offer help trong scope

---

## 9. Preference Memory/Change

### Test Case 9.1: Preference memory - general chat
- [ ] Chat: "Tôi thích phong cách modern"
- [ ] Assistant ghi nhớ: "Bạn thích modern"
- [ ] Sau đó: "Tôi cần gợi ý sofa"
- [ ] Assistant đề xuất sofa modern
- [ ] Reference đến preference đã lưu

### Test Case 9.2: Preference change
- [ ] Trước: "Tôi thích màu trắng"
- [ ] Sau: "Thay đổi ý tôi, tôi thích màu nâu"
- [ ] Assistant update preference
- [ ] Gợi ý sau đó dựa trên màu nâu

### Test Case 9.3: Preference persistence
- [ ] Set preference trong conversation
- [ ] Reload trang
- [ ] Preference vẫn được giữ (nếu conversation state persistence hoạt động)
- [ ] Assistant vẫn refer đến preference cũ

### Test Case 9.4: Context window - preferences from earlier
- [ ] Chat dài, preference đặt ở message 3
- [ ] Message 15: assistant vẫn nhớ preference

---

## 10. Local Provider vs Claude Provider

### Test Case 10.1: Switch provider config
- [ ] Vào admin/config (hoặc backend config endpoint)
- [ ] Change `chat.provider` từ `claude` sang `local`
- [ ] Save config
- [ ] Restart chat (hoặc refresh nếu runtime reload)

### Test Case 10.2: Local provider response
- [ ] Gửi tin nhắn với local provider
- [ ] Response nhận được (có thể chậm hơn)
- [ ] Metadata hiển thị: model name local, latency cao hơn
- [ ] Quality có thể thấp hơn nhưng usable

### Test Case 10.3: Claude provider response
- [ ] Switch sang `claude`
- [ ] Gửi tin nhắn
- [ ] Response nhanh hơn, chất lượng tốt hơn
- [ ] Metadata hiển thị: Claude model

### Test Case 10.4: Provider failure fallback
- [ ] Set local provider, stop local LLM service (nếu có thể)
- [ ] Gửi tin nhắn
- [ ] Fallback sang Claude (nếu implement) hoặc error message rõ ràng
- [ ] UI hiển thị error đúng cách

---

## Cross-Feature Scenarios

### Test Case C.1: Tenant chat full flow
1. Vào `/chat?tenantId=<tenant1>&chatbotId=<bot1>`
2. Gửi tin nhắn tư vấn
3. RAG trả lời đúng KB
4. Chuyển sang lead capture
5. Nhập thông tin lead
6. Kiểm tra Lead và PurchaseRequest tạo trong DB
7. Rename conversation
8. Reload -> giữ state
9. Delete conversation

### Test Case C.2: General chat với preference + off-topic + reload
1. Start general chat
2. Set preference: "Tôi thích phong cách Scandinavian"
3. Off-topic: "Hôm nay trời mưa"
4. Redirect về interior
5. Ask for suggestion -> đề xuất Scandinavian
6. Reload -> preference còn?

### Test Case C.3: Multi-tenant isolation
1. Tenant A chat, tạo lead
2. Tenant B chat, cùng phone
3. Tenant B vẫn tạo lead được (không conflict)
4. Conversation của tenant A không hiển thị với tenant B

---

## Notes / Issues Found

| Test Case | Status | Issue Description |
|-----------|--------|-------------------|
|           |        |                   |
|           |        |                   |
|           |        |                   |

---

## Test Environment

- Browser: _______________
- Date: _______________
- Tester: _______________
- Backend version: _______________
- Frontend version: _______________
- AI service: [ ] Local [ ] Claude
