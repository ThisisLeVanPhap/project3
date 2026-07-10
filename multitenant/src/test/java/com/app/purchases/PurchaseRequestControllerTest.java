package com.app.purchases;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.leads.LeadRepository;
import com.app.tenant.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class PurchaseRequestControllerTest {

    @Mock
    private PurchaseRequestService purchaseRequestService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Mock
    private LeadRepository leadRepository;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void listsPurchaseRequestsForCurrentTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest newer = purchaseRequest(101L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "Call before delivery", "NEW", Instant.parse("2026-04-01T10:07:10Z"));
        newer.setAssignedToMemberId(memberId);
        newer.setClaimedAt(Instant.parse("2026-04-01T10:10:10Z"));
        PurchaseRequest older = purchaseRequest(99L, tenantId, "Tran Thi B", "0988111222", "34 Le Loi", "Morning only", "NEW", Instant.parse("2026-03-30T09:00:00Z"));

        when(purchaseRequestService.findRecentByTenant(tenantId))
                .thenReturn(List.of(newer, older));
        when(purchaseRequestService.findMemberDisplayNames(tenantId))
                .thenReturn(Map.of(memberId, "Assigned Owner"));
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(101))
                .andExpect(jsonPath("$[0].customer_name").value("Nguyen Van A"))
                .andExpect(jsonPath("$[0].phone").value("0912345678"))
                .andExpect(jsonPath("$[0].shipping_address").value("12 Nguyen Trai"))
                .andExpect(jsonPath("$[0].status").value("NEW"))
                .andExpect(jsonPath("$[0].assigned_to_member_id").value(memberId.toString()))
                .andExpect(jsonPath("$[0].assigned_to_display_name").value("Assigned Owner"))
                .andExpect(jsonPath("$[0].claimed_at").exists())
                .andExpect(jsonPath("$[0].created_at").exists())
                .andExpect(jsonPath("$[0].notes").value("Call before delivery"))
                .andExpect(jsonPath("$[1].id").value(99))
                .andExpect(jsonPath("$[1].customer_name").value("Tran Thi B"))
                .andExpect(jsonPath("$[1].created_at").exists());

        verify(purchaseRequestService).findRecentByTenant(tenantId);
    }

    @Test
    void filtersPurchaseRequestsByStatusForCurrentTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(42L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "", "NEW", Instant.parse("2026-04-01T10:07:10Z"));

        when(purchaseRequestService.findRecentByTenantAndStatus(tenantId, "NEW"))
                .thenReturn(List.of(purchaseRequest));
        when(purchaseRequestService.findMemberDisplayNames(tenantId))
                .thenReturn(Map.of());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests")
                        .param("status", "NEW")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(42))
                .andExpect(jsonPath("$[0].customer_name").value("Nguyen Van A"))
                .andExpect(jsonPath("$[0].status").value("NEW"))
                .andExpect(jsonPath("$[0].notes").value(""));

        verify(purchaseRequestService).findRecentByTenantAndStatus(tenantId, "NEW");
    }

    @Test
    void storeUiListIncludesNewChatbotPurchaseRequest() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(
                77L,
                tenantId,
                "Chat User",
                "0912345678",
                "",
                "Purchase request draft only",
                "NEW",
                Instant.parse("2026-04-01T10:07:10Z")
        );
        purchaseRequest.setChannel("messenger");
        purchaseRequest.setHandoffId("handoff-chatbot-1");
        purchaseRequest.setIdempotencyKey("idem-chatbot-1");
        purchaseRequest.setProductSku("GHO-607");
        purchaseRequest.setQuantity(1);

        when(purchaseRequestService.findRecentByTenant(tenantId))
                .thenReturn(List.of(purchaseRequest));
        when(purchaseRequestService.findMemberDisplayNames(tenantId))
                .thenReturn(Map.of());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests")
                        .param("tenantId", tenantId)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(77))
                .andExpect(jsonPath("$[0].tenant_id").value(tenantId))
                .andExpect(jsonPath("$[0].conversation_id").exists())
                .andExpect(jsonPath("$[0].channel").value("messenger"))
                .andExpect(jsonPath("$[0].status").value("NEW"))
                .andExpect(jsonPath("$[0].handoff_id").value("handoff-chatbot-1"))
                .andExpect(jsonPath("$[0].product_sku").value("GHO-607"))
                .andExpect(jsonPath("$[0].quantity").value(1));

        verify(purchaseRequestService).findRecentByTenant(tenantId);
    }

    @Test
    void platformAdminViewsPurchaseRequestDetailForSelectedTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(42L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "Call first", "NEW", Instant.parse("2026-04-01T10:07:10Z"));

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(purchaseRequestService.findByTenantAndId(tenantId, 42L)).thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of());

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests/{id}", 42L)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(42))
                .andExpect(jsonPath("$.tenant_id").value(tenantId))
                .andExpect(jsonPath("$.conversation_id").exists())
                .andExpect(jsonPath("$.status").value("NEW"));

        verify(purchaseRequestService).findByTenantAndId(tenantId, 42L);
    }

    @Test
    void tenantAdminViewsOwnPurchaseRequestDetail() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        PurchaseRequest purchaseRequest = purchaseRequest(43L, tenantId, "Tran Thi B", "0988111222", "34 Le Loi", "", "PROCESSING", Instant.parse("2026-04-01T10:07:10Z"));

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(UUID.randomUUID().toString(), AppRole.TENANT_ADMIN, tenantId, "Tenant Admin", "admin@tenant.local")
        );
        when(purchaseRequestService.findByTenantAndId(tenantId, 43L)).thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of());

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests/{id}", 43L)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(43))
                .andExpect(jsonPath("$.status").value("PROCESSING"));
    }

    @Test
    void rejectsTenantFilterForDifferentTenant() throws Exception {
        TenantContext.set("8e0f40c4-83de-4d44-bf0f-5e53769595e0");
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(UUID.randomUUID().toString(), AppRole.TENANT_MEMBER, "8e0f40c4-83de-4d44-bf0f-5e53769595e0", "Tenant Member", "member@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/purchase-requests")
                        .param("tenantId", "tenant-2")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isForbidden());
    }

    @Test
    void updatesPurchaseRequestStatusForCurrentTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(42L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "", "PROCESSING", Instant.parse("2026-04-01T10:07:10Z"));

        when(purchaseRequestService.updateStatus(tenantId, 42L, "PROCESSING"))
                .thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/status", 42L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "status": "PROCESSING"
                                }
                                """)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(42))
                .andExpect(jsonPath("$.customer_name").value("Nguyen Van A"))
                .andExpect(jsonPath("$.status").value("PROCESSING"));

        verify(purchaseRequestService).updateStatus(tenantId, 42L, "PROCESSING");
    }

    @Test
    void rejectsUnsupportedPurchaseRequestStatus() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        TenantContext.set(tenantId);
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(UUID.randomUUID().toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );

        when(purchaseRequestService.updateStatus(tenantId, 42L, "INVALID"))
                .thenThrow(new IllegalArgumentException("Unsupported purchase request status: INVALID"));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/status", 42L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "status": "INVALID"
                                }
                                """)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Unsupported purchase request status: INVALID"));
    }

    @Test
    void allowsTenantMemberOnPurchaseRequestOperationalEndpoint() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(42L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "", "COMPLETED", Instant.parse("2026-04-01T10:07:10Z"));
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );
        when(purchaseRequestService.updateStatus(tenantId, 42L, "COMPLETED"))
                .thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of());

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/status", 42L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "status": "COMPLETED"
                                }
                                """)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"));
    }

    @Test
    void allowsPlatformAdminOnPurchaseRequestOperationalEndpointForSelectedTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(42L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "", "COMPLETED", Instant.parse("2026-04-01T10:07:10Z"));
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER)).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(purchaseRequestService.updateStatus(tenantId, 42L, "COMPLETED"))
                .thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of());

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/status", 42L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "status": "COMPLETED"
                        }
                        """)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"));
    }

    @Test
    void claimsPurchaseRequestForCurrentTenantMember() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID memberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(55L, tenantId, "Nguyen Van A", "0912345678", "12 Nguyen Trai", "", "NEW", Instant.parse("2026-04-01T10:07:10Z"));
        purchaseRequest.setAssignedToMemberId(memberId);
        purchaseRequest.setClaimedAt(Instant.parse("2026-04-01T10:11:10Z"));

        when(principalAccessor.requireTenantOperator()).thenReturn(
                new AppPrincipal(memberId.toString(), AppRole.TENANT_MEMBER, tenantId, "Tenant Member", "member@tenant.local")
        );
        when(purchaseRequestService.claim(tenantId, 55L, memberId)).thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of(memberId, "Claim Owner"));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/claim", 55L)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assigned_to_member_id").value(memberId.toString()))
                .andExpect(jsonPath("$.assigned_to_display_name").value("Claim Owner"))
                .andExpect(jsonPath("$.claimed_at").exists());

        verify(purchaseRequestService).claim(tenantId, 55L, memberId);
    }

    @Test
    void reassignsPurchaseRequestForTenantAdmin() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        UUID adminId = UUID.fromString("7cc1f1e3-f88b-4e79-a43f-b1f4cf8ca5c2");
        UUID targetMemberId = UUID.fromString("8dfe3f11-0b64-4a98-bfd8-24ce59c8d5ab");
        TenantContext.set(tenantId);
        PurchaseRequest purchaseRequest = purchaseRequest(56L, tenantId, "Tran Thi B", "0988111222", "34 Le Loi", "", "PROCESSING", Instant.parse("2026-04-01T10:07:10Z"));
        purchaseRequest.setAssignedToMemberId(targetMemberId);
        purchaseRequest.setClaimedAt(Instant.parse("2026-04-01T10:12:10Z"));

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN)).thenReturn(
                new AppPrincipal(adminId.toString(), AppRole.TENANT_ADMIN, tenantId, "Tenant Admin", "admin@tenant.local")
        );
        when(purchaseRequestService.reassign(tenantId, 56L, targetMemberId)).thenReturn(purchaseRequest);
        when(purchaseRequestService.findMemberDisplayNames(tenantId)).thenReturn(Map.of(targetMemberId, "Reassigned Owner"));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PurchaseRequestController(purchaseRequestService, principalAccessor, leadRepository))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(put("/api/purchase-requests/{id}/assign", 56L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "member_id": "%s"
                                }
                                """.formatted(targetMemberId))
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assigned_to_member_id").value(targetMemberId.toString()))
                .andExpect(jsonPath("$.assigned_to_display_name").value("Reassigned Owner"));

        verify(purchaseRequestService).reassign(tenantId, 56L, targetMemberId);
    }

    private static PurchaseRequest purchaseRequest(
            Long id,
            String tenantId,
            String customerName,
            String phone,
            String shippingAddress,
            String notes,
            String status,
            Instant createdAt
    ) throws Exception {
        PurchaseRequest purchaseRequest = new PurchaseRequest();
        purchaseRequest.setTenantId(tenantId);
        purchaseRequest.setChannel("web");
        purchaseRequest.setConversationId("conv-" + id);
        purchaseRequest.setCustomerName(customerName);
        purchaseRequest.setPhone(phone);
        purchaseRequest.setShippingAddress(shippingAddress);
        purchaseRequest.setNotes(notes);
        purchaseRequest.setStatus(status);

        var idField = PurchaseRequest.class.getDeclaredField("id");
        idField.setAccessible(true);
        idField.set(purchaseRequest, id);

        var field = PurchaseRequest.class.getDeclaredField("createdAt");
        field.setAccessible(true);
        field.set(purchaseRequest, createdAt);
        return purchaseRequest;
    }
}

