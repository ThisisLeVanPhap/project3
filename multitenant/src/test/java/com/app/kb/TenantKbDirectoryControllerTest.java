package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TenantKbDirectoryControllerTest {

    @Mock
    private TenantKbDirectoryResolver tenantKbDirectoryResolver;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanResolveOwnActiveDirectory() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.TENANT_ADMIN));
        when(tenantKbDirectoryResolver.resolve(tenantId)).thenReturn(
                new ResolvedTenantKbDirectory(
                        tenantId,
                        "chatbot/kb/demo/versions/v20260609120000",
                        TenantKbDirectorySource.ACTIVE_VERSION,
                        versionId,
                        "v20260609120000",
                        null
                )
        );

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/active-directory"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenant_id").value(tenantId.toString()))
                .andExpect(jsonPath("$.kb_dir").value("chatbot/kb/demo/versions/v20260609120000"))
                .andExpect(jsonPath("$.source").value("ACTIVE_VERSION"))
                .andExpect(jsonPath("$.version_id").value(versionId.toString()))
                .andExpect(jsonPath("$.version_tag").value("v20260609120000"))
                .andExpect(jsonPath("$.fallback_reason").doesNotExist());

        verify(tenantKbDirectoryResolver).resolve(tenantId);
    }

    @Test
    void platformAdminWithTenantContextCanResolveActiveDirectory() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.PLATFORM_ADMIN));
        when(tenantKbDirectoryResolver.resolve(tenantId)).thenReturn(
                new ResolvedTenantKbDirectory(
                        tenantId,
                        "chatbot/kb/demo",
                        TenantKbDirectorySource.LEGACY_TENANT_KB_DIR,
                        null,
                        null,
                        "ACTIVE_VERSION_NOT_FOUND"
                )
        );

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/active-directory"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenant_id").value(tenantId.toString()))
                .andExpect(jsonPath("$.source").value("LEGACY_TENANT_KB_DIR"))
                .andExpect(jsonPath("$.fallback_reason").value("ACTIVE_VERSION_NOT_FOUND"));
    }

    @Test
    void tenantMemberCannotResolveActiveDirectory() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);
        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/active-directory"))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new TenantKbDirectoryController(tenantKbDirectoryResolver, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private AppPrincipal principal(UUID tenantId, AppRole role) {
        return new AppPrincipal("admin-1", role, tenantId.toString(), "Admin", "admin@tenant.local");
    }
}
