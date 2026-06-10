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

import java.time.Instant;
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
class TenantKbVersionControllerTest {

    @Mock
    private TenantKbVersionService tenantKbVersionService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanListKbVersions() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");
        when(principalAccessor.requireTenantAdmin()).thenReturn(principal(tenantId));
        when(tenantKbVersionService.listVersionsForTenant(tenantId)).thenReturn(List.of(
                response(versionId, tenantId, "v20260609100000", TenantKbVersionStatus.READY, true)
        ));

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/versions"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(versionId.toString()))
                .andExpect(jsonPath("$[0].tenant_id").value(tenantId.toString()))
                .andExpect(jsonPath("$[0].version_tag").value("v20260609100000"))
                .andExpect(jsonPath("$[0].kb_dir").value("chatbot/kb/demo"))
                .andExpect(jsonPath("$[0].status").value("READY"))
                .andExpect(jsonPath("$[0].artifact_count").value(3))
                .andExpect(jsonPath("$[0].build_message").value("done"))
                .andExpect(jsonPath("$[0].built_at").exists())
                .andExpect(jsonPath("$[0].published_at").exists())
                .andExpect(jsonPath("$[0].created_at").exists())
                .andExpect(jsonPath("$[0].active").value(true))
                .andExpect(jsonPath("$[0].sourceUrlSnapshot").doesNotExist());

        verify(tenantKbVersionService).listVersionsForTenant(tenantId);
    }

    @Test
    void tenantAdminCanPublishReadyVersion() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");
        when(principalAccessor.requireTenantAdmin()).thenReturn(principal(tenantId));
        when(tenantKbVersionService.publishVersion(tenantId, versionId)).thenReturn(
                response(versionId, tenantId, "v20260609100000", TenantKbVersionStatus.READY, true)
        );

        MockMvc mvc = mvc();

        mvc.perform(post("/api/kb/versions/{id}/publish", versionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(versionId.toString()))
                .andExpect(jsonPath("$.active").value(true));

        verify(tenantKbVersionService).publishVersion(tenantId, versionId);
    }

    @Test
    void tenantAdminCanArchiveVersion() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");
        when(principalAccessor.requireTenantAdmin()).thenReturn(principal(tenantId));
        when(tenantKbVersionService.archiveVersion(tenantId, versionId)).thenReturn(
                response(versionId, tenantId, "v20260609100000", TenantKbVersionStatus.ARCHIVED, false)
        );

        MockMvc mvc = mvc();

        mvc.perform(post("/api/kb/versions/{id}/archive", versionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ARCHIVED"))
                .andExpect(jsonPath("$.active").value(false));

        verify(tenantKbVersionService).archiveVersion(tenantId, versionId);
    }

    @Test
    void tenantMemberCannotPublishOrArchiveKbVersions() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireTenantAdmin();
        MockMvc mvc = mvc();
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");

        mvc.perform(post("/api/kb/versions/{id}/publish", versionId))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/kb/versions/{id}/archive", versionId))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new TenantKbVersionController(tenantKbVersionService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private AppPrincipal principal(UUID tenantId) {
        return new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local");
    }

    private TenantKbVersionResponse response(UUID versionId, UUID tenantId, String versionTag, TenantKbVersionStatus status, boolean active) {
        return new TenantKbVersionResponse(
                versionId,
                tenantId,
                versionTag,
                "chatbot/kb/demo",
                null,
                null,
                status,
                3,
                "done",
                Instant.parse("2026-06-09T10:00:00Z"),
                Instant.parse("2026-06-09T10:05:00Z"),
                Instant.parse("2026-06-09T09:55:00Z"),
                active
        );
    }
}
