package com.app.crm;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.tenant.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class CrmCustomerActivityControllerTest {

    @Mock
    private CrmCustomerActivityService activityService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void tenantAdminCanGetCustomerActivity() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();

        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.TENANT_ADMIN));

        CrmCustomerActivityService.CrmCustomerActivityResponse response =
                new CrmCustomerActivityService.CrmCustomerActivityResponse(
                        unifiedCustomerId,
                        tenantId,
                        List.of(new CrmCustomerActivityService.CrmConversationView(
                                UUID.randomUUID(),
                                tenantId,
                                UUID.randomUUID(),
                                "messenger:page:p1:sender:s1",
                                unifiedCustomerId,
                                "ACTIVE",
                                null,
                                Instant.parse("2026-06-15T10:00:00Z")
                        )),
                        List.of(new CrmCustomerActivityService.CrmLeadView(
                                1L,
                                tenantId.toString(),
                                "messenger",
                                UUID.randomUUID().toString(),
                                "s1",
                                "NEW",
                                "HANDOFF",
                                "NEW",
                                Instant.parse("2026-06-15T10:05:00Z")
                        )),
                        List.of(new CrmCustomerActivityService.CrmPurchaseRequestView(
                                100L,
                                tenantId.toString(),
                                "messenger",
                                UUID.randomUUID().toString(),
                                1L,
                                "Nguyễn Văn A",
                                "0987654321",
                                "customer@example.com",
                                "Hà Nội",
                                "NEW",
                                "SOFA-001",
                                Instant.parse("2026-06-15T10:10:00Z"),
                                Instant.parse("2026-06-15T10:10:00Z")
                        ))
                );

        when(activityService.getActivity(tenantId, unifiedCustomerId)).thenReturn(response);

        mvc().perform(get("/api/crm/customers/" + unifiedCustomerId + "/activity"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.unifiedCustomerId").value(unifiedCustomerId.toString()))
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.conversations.length()").value(1))
                .andExpect(jsonPath("$.conversations[0].userExternalId").value("messenger:page:p1:sender:s1"))
                .andExpect(jsonPath("$.leads.length()").value(1))
                .andExpect(jsonPath("$.leads[0].channel").value("messenger"))
                .andExpect(jsonPath("$.purchaseRequests.length()").value(1))
                .andExpect(jsonPath("$.purchaseRequests[0].phone").value("0987654321"));

        verify(activityService).getActivity(tenantId, unifiedCustomerId);
    }

    @Test
    void platformAdminWithTenantContextCanGetCustomerActivity() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID unifiedCustomerId = UUID.randomUUID();

        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(null, AppRole.PLATFORM_ADMIN));
        TenantContext.set(tenantId.toString());

        when(activityService.getActivity(tenantId, unifiedCustomerId))
                .thenReturn(new CrmCustomerActivityService.CrmCustomerActivityResponse(
                        unifiedCustomerId,
                        tenantId,
                        List.of(),
                        List.of(),
                        List.of()
                ));

        mvc().perform(get("/api/crm/customers/" + unifiedCustomerId + "/activity"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.unifiedCustomerId").value(unifiedCustomerId.toString()));

        verify(activityService).getActivity(tenantId, unifiedCustomerId);
    }

    @Test
    void tenantMemberCannotGetCustomerActivity() throws Exception {
        UUID unifiedCustomerId = UUID.randomUUID();

        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);

        mvc().perform(get("/api/crm/customers/" + unifiedCustomerId + "/activity"))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new CrmCustomerActivityController(activityService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private static AppPrincipal principal(UUID tenantId, AppRole role) {
        return new AppPrincipal(
                "admin-1",
                role,
                tenantId == null ? null : tenantId.toString(),
                "Admin",
                "admin@tenant.local"
        );
    }
}
