package com.app.auth;

import com.app.common.ApiExceptionHandler;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TenantMemberSelfAdminControllerTest {

    @Mock
    private TenantMemberManagementService tenantMemberManagementService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanCreateMemberOnlyForOwnTenant() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        AppPrincipal principal = new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local");
        TenantMemberManagementService.CreateTenantMemberRequest request =
                new TenantMemberManagementService.CreateTenantMemberRequest(
                        "staff@tenant.local",
                        "Staff User",
                        "TENANT_MEMBER",
                        "ACTIVE",
                        "staff123"
                );
        TenantMemberManagementService.TenantMemberResponse response =
                new TenantMemberManagementService.TenantMemberResponse(
                        UUID.randomUUID(),
                        tenantId,
                        "staff@tenant.local",
                        "Staff User",
                        "TENANT_MEMBER",
                        "ACTIVE"
                );

        when(principalAccessor.requireTenantAdmin()).thenReturn(principal);
        when(tenantMemberManagementService.create(tenantId, request)).thenReturn(response);

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberSelfAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/tenant-members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "staff@tenant.local",
                                  "displayName": "Staff User",
                                  "role": "TENANT_MEMBER",
                                  "status": "ACTIVE",
                                  "password": "staff123"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.role").value("TENANT_MEMBER"));

        verify(tenantMemberManagementService).create(tenantId, request);
    }

    @Test
    void tenantAdminCanListOwnTenantMembers() throws Exception {
        UUID tenantId = UUID.randomUUID();
        AppPrincipal principal = new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local");
        when(principalAccessor.requireTenantAdmin()).thenReturn(principal);
        when(tenantMemberManagementService.listByTenant(tenantId)).thenReturn(List.of(
                new TenantMemberManagementService.TenantMemberResponse(
                        UUID.randomUUID(),
                        tenantId,
                        "staff@tenant.local",
                        "Staff User",
                        "TENANT_MEMBER",
                        "ACTIVE"
                )
        ));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberSelfAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/tenant-members"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].email").value("staff@tenant.local"));
    }

    @Test
    void tenantMemberCannotUseTenantAdminMemberEndpoint() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireTenantAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberSelfAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/tenant-members"))
                .andExpect(status().isForbidden());
    }
}
