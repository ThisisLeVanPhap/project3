package com.app.admin;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.auth.TenantMemberManagementService;
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
class TenantMemberAdminControllerTest {

    @Mock
    private TenantMemberManagementService tenantMemberManagementService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void platformAdminCanCreateTenantMemberForAnyTenant() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantMemberManagementService.CreateTenantMemberRequest request =
                new TenantMemberManagementService.CreateTenantMemberRequest(
                        "owner@shop-demo.local",
                        "Owner",
                        "TENANT_ADMIN",
                        "ACTIVE",
                        "secret123"
                );
        TenantMemberManagementService.TenantMemberResponse response =
                new TenantMemberManagementService.TenantMemberResponse(
                        UUID.fromString("7d38d32d-c1ca-4752-b5b0-7827b4893eaf"),
                        tenantId,
                        "owner@shop-demo.local",
                        "Owner",
                        "TENANT_ADMIN",
                        "ACTIVE"
                );

        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(tenantMemberManagementService.create(tenantId, request)).thenReturn(response);

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/admin/tenant-members")
                        .param("tenantId", tenantId.toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "owner@shop-demo.local",
                                  "displayName": "Owner",
                                  "role": "TENANT_ADMIN",
                                  "status": "ACTIVE",
                                  "password": "secret123"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.email").value("owner@shop-demo.local"))
                .andExpect(jsonPath("$.role").value("TENANT_ADMIN"));

        verify(tenantMemberManagementService).create(tenantId, request);
    }

    @Test
    void platformAdminCanListTenantMembersForSelectedTenant() throws Exception {
        UUID tenantId = UUID.randomUUID();
        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(tenantMemberManagementService.listByTenant(tenantId)).thenReturn(List.of(
                new TenantMemberManagementService.TenantMemberResponse(
                        UUID.randomUUID(),
                        tenantId,
                        "member@tenant.local",
                        "Member User",
                        "TENANT_MEMBER",
                        "ACTIVE"
                )
        ));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/admin/tenant-members").param("tenantId", tenantId.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].email").value("member@tenant.local"));
    }

    @Test
    void tenantAdminCannotUsePlatformTenantMemberEndpoint() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requirePlatformAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantMemberAdminController(tenantMemberManagementService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/admin/tenant-members").param("tenantId", UUID.randomUUID().toString()))
                .andExpect(status().isForbidden());
    }
}
