package com.app.admin;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.kb.TenantKbVersionRepository;
import com.app.tenants.Tenant;
import com.app.tenants.TenantProvisioningService;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TenantAdminControllerTest {

    @Mock
    private TenantProvisioningService tenantProvisioningService;

    @Mock
    private TenantKbVersionRepository tenantKbVersionRepository;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void allowsPlatformAdminOnTenantManagementEndpoint() throws Exception {
        Tenant tenant = new Tenant();
        tenant.setId(UUID.randomUUID());
        tenant.setCode("demo");
        tenant.setName("Demo Tenant");
        tenant.setStatus("ACTIVE");
        tenant.setApiKey("abc123");

        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(tenantProvisioningService.list()).thenReturn(List.of(tenant));

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantAdminController(tenantProvisioningService, tenantKbVersionRepository, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/admin/tenants"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].code").value("demo"))
                .andExpect(jsonPath("$[0].apiKey").value("abc123"));
    }

    @Test
    void allowsPlatformAdminToCreateTenantWithPracticalFields() throws Exception {
        Tenant tenant = new Tenant();
        tenant.setId(UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489"));
        tenant.setCode("shop_demo");
        tenant.setName("Shop Demo");
        tenant.setStatus("ACTIVE");
        tenant.setApiKey("demoapikey123456");
        tenant.setKbDir("/opt/app/chatbot/kb/shop-demo");

        TenantProvisioningService.CreateTenantRequest request =
                new TenantProvisioningService.CreateTenantRequest(
                        "shop_demo",
                        "Shop Demo",
                        "demoapikey123456",
                        "/opt/app/chatbot/kb/shop-demo",
                        "ACTIVE"
                );

        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );
        when(tenantProvisioningService.create(request)).thenReturn(tenant);

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantAdminController(tenantProvisioningService, tenantKbVersionRepository, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/admin/tenants")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "code": "shop_demo",
                                  "name": "Shop Demo",
                                  "apiKey": "demoapikey123456",
                                  "kbDir": "/opt/app/chatbot/kb/shop-demo",
                                  "status": "ACTIVE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("daf0378f-53e1-4705-8234-41c74287e489"))
                .andExpect(jsonPath("$.code").value("shop_demo"))
                .andExpect(jsonPath("$.kbDir").value("/opt/app/chatbot/kb/shop-demo"))
                .andExpect(jsonPath("$.apiKey").value("demoapikey123456"));

        verify(tenantProvisioningService).create(request);
    }

    @Test
    void allowsPlatformAdminToDeleteTenant() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requirePlatformAdmin()).thenReturn(
                new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin")
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantAdminController(tenantProvisioningService, tenantKbVersionRepository, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(delete("/api/admin/tenants/{tenantId}", tenantId))
                .andExpect(status().isOk());

        verify(tenantProvisioningService).delete(tenantId);
    }

    @Test
    void deniesTenantAdminOnPlatformTenantManagementEndpoint() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requirePlatformAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantAdminController(tenantProvisioningService, tenantKbVersionRepository, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/admin/tenants"))
                .andExpect(status().isForbidden());
    }
}
