package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.modelserver.LlmInstanceManager;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TenantKbRuntimeStatusControllerTest {

    @Mock
    private LlmInstanceManager llmInstanceManager;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanViewOwnRuntimeKbStatus() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID versionId = UUID.fromString("4fb9b56e-283b-4f74-a48d-677d2a826681");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.TENANT_ADMIN));
        when(llmInstanceManager.getRuntimeKbStatus(tenantId)).thenReturn(
                new LlmInstanceManager.RuntimeKbStatusSnapshot(
                        tenantId,
                        new LlmInstanceManager.RuntimeKbDesiredSnapshot(
                                "chatbot/kb/demo/versions/v20260609120000",
                                "ACTIVE_VERSION",
                                versionId,
                                "v20260609120000",
                                null
                        ),
                        new LlmInstanceManager.RuntimeKbRunningSnapshot(
                                LlmInstanceManager.OBSERVABILITY_JAVA_SPAWNED,
                                "chatbot/kb/demo/versions/v20260609120000",
                                "ACTIVE_VERSION",
                                versionId,
                                "v20260609120000",
                                Instant.parse("2026-06-09T12:00:00Z"),
                                true,
                                1234L,
                                null
                        ),
                        true
                )
        );

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/runtime-status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenant_id").value(tenantId.toString()))
                .andExpect(jsonPath("$.desired.kb_dir").value("chatbot/kb/demo/versions/v20260609120000"))
                .andExpect(jsonPath("$.desired.source").value("ACTIVE_VERSION"))
                .andExpect(jsonPath("$.desired.version_id").value(versionId.toString()))
                .andExpect(jsonPath("$.desired.version_tag").value("v20260609120000"))
                .andExpect(jsonPath("$.desired.fallback_reason").doesNotExist())
                .andExpect(jsonPath("$.running.mode").value("JAVA_SPAWNED"))
                .andExpect(jsonPath("$.running.kb_dir").value("chatbot/kb/demo/versions/v20260609120000"))
                .andExpect(jsonPath("$.running.source").value("ACTIVE_VERSION"))
                .andExpect(jsonPath("$.running.version_id").value(versionId.toString()))
                .andExpect(jsonPath("$.running.version_tag").value("v20260609120000"))
                .andExpect(jsonPath("$.running.started_at").value("2026-06-09T12:00:00Z"))
                .andExpect(jsonPath("$.running.process_alive").value(true))
                .andExpect(jsonPath("$.running.pid").value(1234))
                .andExpect(jsonPath("$.running.note").doesNotExist())
                .andExpect(jsonPath("$.in_sync").value(true));

        verify(llmInstanceManager).getRuntimeKbStatus(tenantId);
    }

    @Test
    void platformAdminWithTenantContextCanViewRuntimeKbStatus() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.PLATFORM_ADMIN));
        when(llmInstanceManager.getRuntimeKbStatus(tenantId)).thenReturn(
                new LlmInstanceManager.RuntimeKbStatusSnapshot(
                        tenantId,
                        new LlmInstanceManager.RuntimeKbDesiredSnapshot(
                                "chatbot/kb/demo",
                                "LEGACY_TENANT_KB_DIR",
                                null,
                                null,
                                null
                        ),
                        null,
                        false
                )
        );

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/runtime-status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tenant_id").value(tenantId.toString()))
                .andExpect(jsonPath("$.desired.kb_dir").value("chatbot/kb/demo"))
                .andExpect(jsonPath("$.desired.source").value("LEGACY_TENANT_KB_DIR"))
                .andExpect(jsonPath("$.running").doesNotExist())
                .andExpect(jsonPath("$.in_sync").value(false));
    }

    @Test
    void externalModeResponseDoesNotClaimActualKbDir() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN))
                .thenReturn(principal(tenantId, AppRole.TENANT_ADMIN));
        when(llmInstanceManager.getRuntimeKbStatus(tenantId)).thenReturn(
                new LlmInstanceManager.RuntimeKbStatusSnapshot(
                        tenantId,
                        new LlmInstanceManager.RuntimeKbDesiredSnapshot(
                                "chatbot/kb/demo",
                                "LEGACY_TENANT_KB_DIR",
                                null,
                                null,
                                null
                        ),
                        new LlmInstanceManager.RuntimeKbRunningSnapshot(
                                LlmInstanceManager.OBSERVABILITY_EXTERNAL_BASE_URL,
                                null,
                                null,
                                null,
                                null,
                                null,
                                null,
                                null,
                                "Java does not own external Python process"
                        ),
                        null
                )
        );

        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/runtime-status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.running.mode").value("EXTERNAL_BASE_URL"))
                .andExpect(jsonPath("$.running.kb_dir").doesNotExist())
                .andExpect(jsonPath("$.running.note").value("Java does not own external Python process"))
                .andExpect(jsonPath("$.in_sync").doesNotExist());
    }

    @Test
    void tenantMemberCannotViewRuntimeKbStatus() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.TENANT_ADMIN, AppRole.PLATFORM_ADMIN);
        MockMvc mvc = mvc();

        mvc.perform(get("/api/kb/runtime-status"))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new TenantKbRuntimeStatusController(llmInstanceManager, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private AppPrincipal principal(UUID tenantId, AppRole role) {
        return new AppPrincipal("admin-1", role, tenantId.toString(), "Admin", "admin@tenant.local");
    }
}
