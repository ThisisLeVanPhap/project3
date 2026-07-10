package com.app.purchases;

import com.app.auth.TenantMember;
import com.app.auth.TenantMemberRepository;
import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.customers.CustomerIdentityService;
import com.app.leads.Lead;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PurchaseRequestServiceTest {

    @Mock
    private PurchaseRequestRepository purchaseRequestRepo;

    @Mock
    private TenantMemberRepository tenantMemberRepository;

    @Mock
    private CustomerIdentityService customerIdentityService;

    @Mock
    private ConversationRepository conversationRepository;

    @InjectMocks
    private PurchaseRequestService purchaseRequestService;

    @Test
    void createsPurchaseRequestFromLeadTranscript() {
        Lead lead = Lead.createNew("tenant-1", "web", "conv-1", "web-user", "{}", "");
        lead.setTranscript("""
                user: Tên: Nguyễn Văn An
                user: Số điện thoại: 0912 345 678
                user: Địa chỉ: 12 Nguyễn Trãi, Quận 1, TP.HCM
                user: Ghi chú: Giao giờ hành chính
                user: Sản phẩm muốn mua: https://store.example.vn/sofa-x
                """);

        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq("tenant-1"), eq("conv-1"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest saved = purchaseRequestService.findOrCreateFromLead(lead);

        assertEquals("tenant-1", saved.getTenantId());
        assertEquals("conv-1", saved.getConversationId());
        assertEquals("Nguyễn Văn An", saved.getCustomerName());
        assertEquals("0912345678", saved.getPhone());
        assertEquals("12 Nguyễn Trãi, Quận 1, TP.HCM", saved.getShippingAddress());
        assertEquals("Giao giờ hành chính", saved.getNotes());
        assertEquals("https://store.example.vn/sofa-x", saved.getRequestedProductRef());
        assertEquals("NEW", saved.getStatus());
    }

    @Test
    void updatesExistingPurchaseRequestOnlyWhenBusinessFieldsAreMissing() {
        Lead lead = Lead.createNew("tenant-1", "web", "conv-2", "web-user", "{\"phone\":\"0988 111 222\"}", "");
        lead.setTranscript("""
                user: Tên: Trần Thị Bình
                user: Địa chỉ: 88 Lê Lợi, Đà Nẵng
                """);

        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("tenant-1");
        existing.setChannel("web");
        existing.setConversationId("conv-2");
        existing.setCustomerName("");
        existing.setPhone("");
        existing.setShippingAddress("");
        existing.setNotes("");
        existing.setRequestedProductRef("");

        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq("tenant-1"), eq("conv-2"), any(List.class)))
                .thenReturn(Optional.of(existing));
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest result = purchaseRequestService.findOrCreateFromLead(lead);

        ArgumentCaptor<PurchaseRequest> captor = ArgumentCaptor.forClass(PurchaseRequest.class);
        verify(purchaseRequestRepo).save(captor.capture());
        PurchaseRequest updated = captor.getValue();

        assertSame(existing, result);
        assertEquals("Trần Thị Bình", updated.getCustomerName());
        assertEquals("0988111222", updated.getPhone());
        assertEquals("88 Lê Lợi, Đà Nẵng", updated.getShippingAddress());
    }

    @Test
    void extractsAsciiVietnameseBuyerDetailsWithoutConversationFallback() {
        Lead lead = Lead.createNew("tenant-1", "web", "conv-3", "", "{}", "");
        lead.setTranscript("""
                user: Vay toi muon tao yeu cau mua hang. Ten toi la Nguyen Van A, so dien thoai la 0912345678.
                user: Dia chi nhan hang cua toi la 123 Nguyen Trai, Ha Noi. Hay xac nhan lai yeu cau mua hang giup toi.
                assistant: De tiep tuc, hay tra loi CONFIRM.
                user: CONFIRM
                """);

        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq("tenant-1"), eq("conv-3"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest saved = purchaseRequestService.findOrCreateFromLead(lead);

        assertEquals("Nguyen Van A", saved.getCustomerName());
        assertEquals("0912345678", saved.getPhone());
        assertEquals("123 Nguyen Trai, Ha Noi", saved.getShippingAddress());
        assertEquals("", saved.getRequestedProductRef());
    }

    @Test
    void createsDraftPurchaseRequestWhenBuyerDetailsAreMissing() {
        Lead lead = Lead.createNew("tenant-1", "web", "conv-4", "messenger-user-1", "{}", "");
        lead.setTranscript("""
                user: Toi muon mua cai ban sofa nay
                assistant: Ban cho minh xin thong tin de cua hang xu ly tiep nhe
                """);

        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq("tenant-1"), eq("conv-4"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest saved = purchaseRequestService.findOrCreateFromLead(lead);

        assertEquals("", saved.getCustomerName());
        assertEquals("", saved.getPhone());
        assertEquals("", saved.getShippingAddress());
        assertEquals("NEW", saved.getStatus());
        verify(purchaseRequestRepo).save(any(PurchaseRequest.class));
    }

    @Test
    void doesNotExtractBuyerDetailsFromAssistantSummaryOrProductText() {
        Lead lead = Lead.createNew("tenant-1", "messenger", "conv-4b", "sender-1", "{}", "");
        lead.setTranscript("""
                user: Den tha tran trang tri kieu dang dep GHO-239 mau A hay day, toi muon mua
                assistant: Minh da tao yeu cau mua hang nhap:
                assistant: - San pham: Den tha tran trang tri kieu dang dep va gia re GHO-239
                assistant: - So luong: 1
                assistant: - Gia tham khao theo du lieu hien co: 700000.0
                assistant: - Lien he: phap@gmail.com
                assistant: - Khu vuc/dia chi: Chua co
                assistant: Luu y: Day chua phai don hang da chot.
                user: 098877833
                assistant: Ban xac nhan gui yeu cau nay cho cua hang khong?
                user: BUY_CONFIRM
                """);

        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq("tenant-1"), eq("conv-4b"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest saved = purchaseRequestService.findOrCreateFromLead(lead);

        assertEquals("", saved.getCustomerName());
        assertEquals("098877833", saved.getPhone());
        assertEquals("", saved.getShippingAddress());
        assertEquals("phap@gmail.com", saved.getEmail());
        assertEquals("Den tha tran trang tri kieu dang dep va gia re GHO-239", saved.getRequestedProductRef());
        assertEquals("GHO-239", saved.getProductSku());
        assertEquals(0, new BigDecimal("700000.0").compareTo(saved.getPrice()));
        assertEquals(1, saved.getQuantity());
        assertEquals("NEW", saved.getStatus());
    }

    @Test
    void updatesPurchaseRequestStatusWithinTenant() {
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("tenant-1");
        existing.setChannel("web");
        existing.setConversationId("conv-5");
        existing.setStatus("NEW");

        when(purchaseRequestRepo.findByIdAndTenantId(7L, "tenant-1"))
                .thenReturn(Optional.of(existing));
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest updated = purchaseRequestService.updateStatus("tenant-1", 7L, "completed");

        assertSame(existing, updated);
        assertEquals("COMPLETED", updated.getStatus());
        verify(purchaseRequestRepo).save(existing);
    }

    @Test
    void rejectsProcessingWhenBuyerDetailsAreMissing() {
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("tenant-1");
        existing.setChannel("web");
        existing.setConversationId("conv-5");
        existing.setCustomerName("Nguyen Van A");
        existing.setPhone("");
        existing.setShippingAddress("");
        existing.setStatus("NEW");

        when(purchaseRequestRepo.findByIdAndTenantId(7L, "tenant-1"))
                .thenReturn(Optional.of(existing));

        var ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> purchaseRequestService.updateStatus("tenant-1", 7L, "PROCESSING")
        );

        assertEquals(400, ex.getStatusCode().value());
        assertTrue(ex.getReason().contains("customer name, phone, and shipping address"));
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void movesToProcessingWhenBuyerDetailsAreComplete() {
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("tenant-1");
        existing.setChannel("web");
        existing.setConversationId("conv-5");
        existing.setCustomerName("Nguyen Van A");
        existing.setPhone("0912345678");
        existing.setShippingAddress("12 Nguyen Trai");
        existing.setStatus("NEW");

        when(purchaseRequestRepo.findByIdAndTenantId(7L, "tenant-1"))
                .thenReturn(Optional.of(existing));
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequest updated = purchaseRequestService.updateStatus("tenant-1", 7L, "PROCESSING");

        assertSame(existing, updated);
        assertEquals("PROCESSING", updated.getStatus());
        verify(purchaseRequestRepo).save(existing);
    }

    @Test
    void rejectsUnsupportedStatusUpdate() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> purchaseRequestService.updateStatus("tenant-1", 7L, "invalid")
        );

        assertTrue(ex.getMessage().contains("Unsupported purchase request status"));
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void rejectsStatusUpdateForMissingTenantScopedPurchaseRequest() {
        when(purchaseRequestRepo.findByIdAndTenantId(7L, "tenant-1"))
                .thenReturn(Optional.empty());

        var ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> purchaseRequestService.updateStatus("tenant-1", 7L, "PROCESSING")
        );

        assertEquals(404, ex.getStatusCode().value());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void claimsUnassignedPurchaseRequestForTenantMember() {
        UUID memberId = UUID.randomUUID();
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("8e0f40c4-83de-4d44-bf0f-5e53769595e0");
        existing.setChannel("web");
        existing.setConversationId("conv-6");
        existing.setStatus("NEW");

        TenantMember member = new TenantMember();
        member.setId(memberId);
        member.setTenantId(UUID.fromString(existing.getTenantId()));
        member.setEmail("owner@tenant.local");
        member.setDisplayName("Owner");
        member.setRole("TENANT_MEMBER");
        member.setStatus("ACTIVE");

        when(purchaseRequestRepo.findByIdAndTenantId(11L, existing.getTenantId()))
                .thenReturn(Optional.of(existing));
        when(tenantMemberRepository.findByIdAndTenantId(memberId, UUID.fromString(existing.getTenantId())))
                .thenReturn(Optional.of(member));
        when(purchaseRequestRepo.save(existing)).thenReturn(existing);

        PurchaseRequest claimed = purchaseRequestService.claim(existing.getTenantId(), 11L, memberId);

        assertSame(existing, claimed);
        assertEquals(memberId, claimed.getAssignedToMemberId());
        assertTrue(claimed.getClaimedAt() != null);
        verify(purchaseRequestRepo).save(existing);
    }

    @Test
    void rejectsClaimWhenPurchaseRequestAlreadyAssigned() {
        UUID currentOwnerId = UUID.randomUUID();
        UUID nextOwnerId = UUID.randomUUID();
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("8e0f40c4-83de-4d44-bf0f-5e53769595e0");
        existing.setChannel("web");
        existing.setConversationId("conv-7");
        existing.setAssignedToMemberId(currentOwnerId);
        existing.setClaimedAt(Instant.parse("2026-04-06T08:00:00Z"));

        TenantMember member = new TenantMember();
        member.setId(nextOwnerId);
        member.setTenantId(UUID.fromString(existing.getTenantId()));
        member.setEmail("second@tenant.local");
        member.setRole("TENANT_MEMBER");
        member.setStatus("ACTIVE");

        when(purchaseRequestRepo.findByIdAndTenantId(12L, existing.getTenantId()))
                .thenReturn(Optional.of(existing));
        when(tenantMemberRepository.findByIdAndTenantId(nextOwnerId, UUID.fromString(existing.getTenantId())))
                .thenReturn(Optional.of(member));

        var ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> purchaseRequestService.claim(existing.getTenantId(), 12L, nextOwnerId)
        );

        assertEquals(409, ex.getStatusCode().value());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void reassignsPurchaseRequestWithinTenant() {
        UUID memberId = UUID.randomUUID();
        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId("8e0f40c4-83de-4d44-bf0f-5e53769595e0");
        existing.setChannel("web");
        existing.setConversationId("conv-8");
        existing.setClaimedAt(Instant.parse("2026-04-06T08:00:00Z"));

        TenantMember member = new TenantMember();
        member.setId(memberId);
        member.setTenantId(UUID.fromString(existing.getTenantId()));
        member.setEmail("admin-target@tenant.local");
        member.setDisplayName("Admin Target");
        member.setRole("TENANT_MEMBER");
        member.setStatus("ACTIVE");

        when(purchaseRequestRepo.findByIdAndTenantId(13L, existing.getTenantId()))
                .thenReturn(Optional.of(existing));
        when(tenantMemberRepository.findByIdAndTenantId(memberId, UUID.fromString(existing.getTenantId())))
                .thenReturn(Optional.of(member));
        when(purchaseRequestRepo.save(existing)).thenReturn(existing);

        PurchaseRequest reassigned = purchaseRequestService.reassign(existing.getTenantId(), 13L, memberId);

        assertSame(existing, reassigned);
        assertEquals(memberId, reassigned.getAssignedToMemberId());
        assertEquals(Instant.parse("2026-04-06T08:00:00Z"), reassigned.getClaimedAt());
        verify(purchaseRequestRepo).save(existing);
    }

    @Test
    void resolvesTenantMemberDisplayNamesForAssignmentViews() {
        UUID tenantId = UUID.randomUUID();
        TenantMember named = new TenantMember();
        named.setId(UUID.randomUUID());
        named.setTenantId(tenantId);
        named.setDisplayName("Alice");
        named.setEmail("alice@tenant.local");

        TenantMember fallback = new TenantMember();
        fallback.setId(UUID.randomUUID());
        fallback.setTenantId(tenantId);
        fallback.setDisplayName(" ");
        fallback.setEmail("fallback@tenant.local");

        when(tenantMemberRepository.findAllByTenantIdOrderByEmailAsc(tenantId))
                .thenReturn(java.util.List.of(named, fallback));

        Map<UUID, String> displayNames = purchaseRequestService.findMemberDisplayNames(tenantId.toString());

        assertEquals("Alice", displayNames.get(named.getId()));
        assertEquals("fallback@tenant.local", displayNames.get(fallback.getId()));
    }

    @Test
    void createsPurchaseRequestFromChatbotHandoff() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-1",
                "idem-1",
                "conv-1",
                "0912 345 678"
        );

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-1"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, "handoff-1"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq(tenantId), eq("conv-1"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequestService.ChatbotCreateResult result =
                purchaseRequestService.createFromChatbotHandoff(request);

        assertTrue(result.created());
        PurchaseRequest saved = result.purchaseRequest();
        assertEquals(tenantId, saved.getTenantId());
        assertEquals("web", saved.getChannel());
        assertEquals("conv-1", saved.getConversationId());
        assertEquals("handoff-1", saved.getHandoffId());
        assertEquals("idem-1", saved.getIdempotencyKey());
        assertEquals("0912345678", saved.getPhone());
        assertEquals("a@example.com", saved.getEmail());
        assertEquals("GHO-607", saved.getProductSku());
        assertEquals("https://store.example/products/gho-607", saved.getProductUrl());
        assertEquals(0, new BigDecimal("700000").compareTo(saved.getPrice()));
        assertEquals(1, saved.getQuantity());
        assertEquals("NEW", saved.getStatus());
        assertEquals("Rem cuon tranh cao cap GHO-607", saved.getRequestedProductRef());
        assertEquals(null, saved.getAssignedToMemberId());
    }

    @Test
    void chatbotHandoffRejectsDuplicateOpenPurchaseRequestForConversation() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-open",
                "idem-open",
                "conv-open",
                "0912 345 678"
        );
        PurchaseRequest open = new PurchaseRequest();
        open.setTenantId(tenantId);
        open.setChannel("web");
        open.setConversationId("conv-open");
        open.setStatus("NEW");

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-open"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, "handoff-open"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(
                eq(tenantId),
                eq("conv-open"),
                any(List.class)
        )).thenReturn(Optional.of(open));

        var ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> purchaseRequestService.createFromChatbotHandoff(request)
        );

        assertEquals(409, ex.getStatusCode().value());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void chatbotHandoffCreatesNewWhenOnlyFinalOrResetDiscardedRequestsExist() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-after-reset",
                "idem-after-reset",
                "conv-after-reset",
                "0912 345 678"
        );

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-after-reset"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, "handoff-after-reset"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(
                eq(tenantId),
                eq("conv-after-reset"),
                any(List.class)
        )).thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequestService.ChatbotCreateResult result =
                purchaseRequestService.createFromChatbotHandoff(request);

        assertTrue(result.created());
        assertEquals("conv-after-reset", result.purchaseRequest().getConversationId());
        assertEquals("NEW", result.purchaseRequest().getStatus());
    }

    @Test
    void chatbotHandoffLinksCustomerIdentityWhenConversationExternalIdExists() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        String conversationId = UUID.randomUUID().toString();
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-identity",
                "idem-identity",
                conversationId,
                "+84 912 345 678"
        );
        Conversation conversation = new Conversation();
        conversation.setId(UUID.fromString(conversationId));
        conversation.setTenantId(UUID.fromString(tenantId));
        conversation.setUserExternalId("messenger:page:page-1:sender:sender-1");

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-identity"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, "handoff-identity"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq(tenantId), eq(conversationId), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(conversationRepository.findById(UUID.fromString(conversationId)))
                .thenReturn(Optional.of(conversation));

        purchaseRequestService.createFromChatbotHandoff(request);

        verify(customerIdentityService).resolveOrCreateIdentity(
                UUID.fromString(tenantId),
                "web",
                "messenger:page:page-1:sender:sender-1",
                "Nguyen Van A",
                "84912345678",
                "a@example.com"
        );
    }

    @Test
    void returnsExistingPurchaseRequestForDuplicateIdempotencyKey() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-1",
                "idem-1",
                "conv-1",
                "0912345678"
        );

        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId(tenantId);
        existing.setChannel("web");
        existing.setConversationId("conv-1");
        existing.setHandoffId("handoff-1");
        existing.setIdempotencyKey("idem-1");
        existing.setPhone("0912345678");
        existing.setEmail("a@example.com");
        existing.setRequestedProductRef("Rem cuon tranh cao cap GHO-607");
        existing.setProductSku("GHO-607");
        existing.setProductUrl("https://store.example/products/gho-607");
        existing.setPrice(new BigDecimal("700000.00"));
        existing.setQuantity(1);
        existing.setStatus("NEW");

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-1"))
                .thenReturn(Optional.of(existing));

        PurchaseRequestService.ChatbotCreateResult result =
                purchaseRequestService.createFromChatbotHandoff(request);

        assertFalse(result.created());
        assertSame(existing, result.purchaseRequest());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void allowsSameIdempotencyKeyForDifferentTenant() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-tenant-1",
                "shared-idem",
                "conv-tenant-1",
                "0912345678"
        );

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "shared-idem"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, "handoff-tenant-1"))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(eq(tenantId), eq("conv-tenant-1"), any(List.class)))
                .thenReturn(Optional.empty());
        when(purchaseRequestRepo.save(any(PurchaseRequest.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PurchaseRequestService.ChatbotCreateResult result =
                purchaseRequestService.createFromChatbotHandoff(request);

        assertTrue(result.created());
        verify(purchaseRequestRepo).findByTenantIdAndIdempotencyKey(tenantId, "shared-idem");
    }

    @Test
    void rejectsChatbotHandoffMissingTenantId() {
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                "",
                "handoff-1",
                "idem-1",
                "conv-1",
                "0912345678"
        );

        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> purchaseRequestService.createFromChatbotHandoff(request)
        );

        assertEquals("tenant_id is required", ex.getMessage());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void rejectsChatbotHandoffMissingPhone() {
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                "8e0f40c4-83de-4d44-bf0f-5e53769595e0",
                "handoff-1",
                "idem-1",
                "conv-1",
                ""
        );

        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> purchaseRequestService.createFromChatbotHandoff(request)
        );

        assertEquals("phone is required", ex.getMessage());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void rejectsChatbotHandoffInvalidPhone() {
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                "8e0f40c4-83de-4d44-bf0f-5e53769595e0",
                "handoff-1",
                "idem-1",
                "conv-1",
                "12345"
        );

        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> purchaseRequestService.createFromChatbotHandoff(request)
        );

        assertEquals("Invalid phone", ex.getMessage());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    @Test
    void rejectsConflictingDuplicateIdempotencyPayload() {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        ChatbotPurchaseRequestCreateRequest request = chatbotRequest(
                tenantId,
                "handoff-1",
                "idem-1",
                "conv-1",
                "0912345678"
        );

        PurchaseRequest existing = new PurchaseRequest();
        existing.setTenantId(tenantId);
        existing.setChannel("web");
        existing.setConversationId("conv-1");
        existing.setHandoffId("handoff-1");
        existing.setIdempotencyKey("idem-1");
        existing.setPhone("0988111222");
        existing.setRequestedProductRef("Rem cuon tranh cao cap GHO-607");
        existing.setStatus("NEW");

        when(purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, "idem-1"))
                .thenReturn(Optional.of(existing));

        var ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> purchaseRequestService.createFromChatbotHandoff(request)
        );

        assertEquals(409, ex.getStatusCode().value());
        verify(purchaseRequestRepo, never()).save(any(PurchaseRequest.class));
    }

    private static ChatbotPurchaseRequestCreateRequest chatbotRequest(
            String tenantId,
            String handoffId,
            String idempotencyKey,
            String conversationId,
            String phone
    ) {
        return new ChatbotPurchaseRequestCreateRequest(
                handoffId,
                idempotencyKey,
                tenantId,
                conversationId,
                "web",
                "Nguyen Van A",
                phone,
                "a@example.com",
                "12 Nguyen Trai",
                "Call before delivery",
                "Rem cuon tranh cao cap GHO-607",
                "GHO-607",
                "https://store.example/products/gho-607",
                new BigDecimal("700000"),
                1
        );
    }
}
