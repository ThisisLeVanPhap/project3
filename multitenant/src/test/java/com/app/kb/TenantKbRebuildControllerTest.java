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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class TenantKbRebuildControllerTest {

    @Mock
    private TenantKbRebuildService tenantKbRebuildService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void tenantAdminCanTriggerOwnKbRebuild() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        when(principalAccessor.requireTenantAdmin()).thenReturn(
                new AppPrincipal("admin-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant Admin", "admin@tenant.local")
        );
        when(tenantKbRebuildService.rebuild(tenantId)).thenReturn(
                new TenantKbRebuildService.RebuildResponse(
                        true,
                        "KB rebuilt successfully. The next tenant chat request will start with the updated KB.",
                        "2026-04-05T22:00:00Z",
                        java.time.Instant.parse("2026-04-05T21:55:00Z"),
                        java.time.Instant.parse("2026-04-05T22:00:00Z"),
                        "SUCCESS",
                        "KB rebuilt successfully. The next tenant chat request will start with the updated KB."
                )
        );

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbRebuildController(tenantKbRebuildService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/kb/rebuild"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("KB rebuilt successfully. The next tenant chat request will start with the updated KB."));

        verify(tenantKbRebuildService).rebuild(tenantId);
    }

    @Test
    void tenantMemberCannotTriggerKbRebuild() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireTenantAdmin();

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new TenantKbRebuildController(tenantKbRebuildService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();

        mvc.perform(post("/api/kb/rebuild"))
                .andExpect(status().isForbidden());
    }
}
