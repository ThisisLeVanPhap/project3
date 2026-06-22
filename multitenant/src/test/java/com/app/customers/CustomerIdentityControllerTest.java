package com.app.customers;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
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
class CustomerIdentityControllerTest {

    @Mock
    private CustomerIdentityQueryService queryService;
    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @AfterEach
    void tearDown() {
        com.app.tenant.TenantContext.clear();
    }

    @Test
    void tenantAdminCanListCustomers() throws Exception {
        UUID tenantId = UUID.randomUUID();
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.TENANT_ADMIN));
        when(queryService.listCustomers(tenantId)).thenReturn(List.of(
                new CustomerIdentityQueryService.CustomerIdentityCustomerView(
                        UUID.fromString("11111111-1111-4111-8111-111111111111"),
                        tenantId,
                        "An",
                        "0987654321",
                        "an@example.com",
                        Instant.parse("2026-06-15T10:00:00Z"),
                        Instant.parse("2026-06-15T10:05:00Z")
                )
        ));

        mvc().perform(get("/api/customer-identities/customers"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].unifiedCustomerId").value("11111111-1111-4111-8111-111111111111"))
                .andExpect(jsonPath("$[0].tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$[0].normalizedPhone").value("0987654321"))
                .andExpect(jsonPath("$[0].normalizedEmail").value("an@example.com"));

        verify(queryService).listCustomers(tenantId);
    }

    @Test
    void detailReturnsIdentitiesForTenantScopedCustomer() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID customerId = UUID.randomUUID();
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.PLATFORM_ADMIN));
        com.app.tenant.TenantContext.set(tenantId.toString());
        when(queryService.getCustomerDetail(tenantId, customerId)).thenReturn(
                new CustomerIdentityQueryService.CustomerIdentityCustomerDetailView(
                        customerId,
                        tenantId,
                        "An",
                        "0987654321",
                        null,
                        Instant.parse("2026-06-15T10:00:00Z"),
                        Instant.parse("2026-06-15T10:05:00Z"),
                        List.of(
                                new CustomerIdentityQueryService.CustomerIdentityIdentityView(
                                        UUID.randomUUID(),
                                        customerId,
                                        "messenger",
                                        "page:p1:sender:s1",
                                        "An",
                                        Instant.parse("2026-06-15T10:00:00Z"),
                                        Instant.parse("2026-06-15T10:05:00Z")
                                ),
                                new CustomerIdentityQueryService.CustomerIdentityIdentityView(
                                        UUID.randomUUID(),
                                        customerId,
                                        "telegram",
                                        "chat:42",
                                        "An Telegram",
                                        Instant.parse("2026-06-15T10:01:00Z"),
                                        Instant.parse("2026-06-15T10:06:00Z")
                                )
                        )
                )
        );

        mvc().perform(get("/api/customer-identities/customers/" + customerId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.unifiedCustomerId").value(customerId.toString()))
                .andExpect(jsonPath("$.identities.length()").value(2))
                .andExpect(jsonPath("$.identities[0].channel").value("messenger"));
    }

    @Test
    void tenantMemberCannotQueryCustomerIdentities() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);

        mvc().perform(get("/api/customer-identities/customers"))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new CustomerIdentityController(queryService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private static AppPrincipal principal(UUID tenantId, AppRole role) {
        return new AppPrincipal("admin-1", role, role == AppRole.PLATFORM_ADMIN ? null : tenantId.toString(), "Admin", "admin@tenant.local");
    }
}
