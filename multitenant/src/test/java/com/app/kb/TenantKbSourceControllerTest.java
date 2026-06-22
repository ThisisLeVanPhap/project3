package com.app.kb;

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
class TenantKbSourceControllerTest {

    @AfterEach
    void clearTenantContext() {
        TenantContext.clear();
    }

    @Mock
    private TenantKbSourceService tenantKbSourceService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanListOwnKbSourceUrls() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN)).thenReturn(
                new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local")
        );
        when(tenantKbSourceService.list(tenantId)).thenReturn(
                new TenantKbSourceService.SourceUrlsResponse(tenantId, List.of("https://example.com/help"))
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbSourceController(tenantKbSourceService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/kb/source-urls"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.urls[0]").value("https://example.com/help"));
    }

    @Test
    void tenantAdminCanAddOwnKbSourceUrl() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantKbSourceService.SourceUrlRequest request = new TenantKbSourceService.SourceUrlRequest("https://example.com/faq");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN)).thenReturn(
                new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local")
        );
        when(tenantKbSourceService.add(tenantId, request)).thenReturn(
                new TenantKbSourceService.SourceUrlsResponse(tenantId, List.of("https://example.com/faq"))
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbSourceController(tenantKbSourceService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/kb/source-urls")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "url": "https://example.com/faq"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.urls[0]").value("https://example.com/faq"));

        verify(tenantKbSourceService).add(tenantId, request);
    }

    @Test
    void tenantAdminCanRemoveOwnKbSourceUrl() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantKbSourceService.SourceUrlRequest request = new TenantKbSourceService.SourceUrlRequest("https://example.com/faq");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN)).thenReturn(
                new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local")
        );
        when(tenantKbSourceService.remove(tenantId, request)).thenReturn(
                new TenantKbSourceService.SourceUrlsResponse(tenantId, List.of())
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbSourceController(tenantKbSourceService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(delete("/api/kb/source-urls")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "url": "https://example.com/faq"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.urls").isArray())
                .andExpect(jsonPath("$.urls").isEmpty());

        verify(tenantKbSourceService).remove(tenantId, request);
    }

    @Test
    void platformAdminWithTenantContextCanListKbSourceUrls() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        TenantContext.set(tenantId.toString());
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN)).thenReturn(
                new AppPrincipal("admin-1", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin@platform.local")
        );
        when(tenantKbSourceService.list(tenantId)).thenReturn(
                new TenantKbSourceService.SourceUrlsResponse(tenantId, List.of("https://example.com/help"))
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbSourceController(tenantKbSourceService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/kb/source-urls"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.urls[0]").value("https://example.com/help"));
    }

    @Test
    void tenantMemberCannotManageKbSourceUrls() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbSourceController(tenantKbSourceService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(get("/api/kb/source-urls"))
                .andExpect(status().isForbidden());
    }
}
