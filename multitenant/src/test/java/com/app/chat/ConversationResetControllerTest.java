package com.app.chat;

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

import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class ConversationResetControllerTest {

    @Mock
    private ConversationResetService resetService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void platformAdminResetsConversationForSelectedTenant() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        TenantContext.set(tenantId.toString());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform", "platform@test.local"));
        when(resetService.reset(eq(tenantId), any(ConversationResetRequest.class)))
                .thenReturn(ConversationResetResponse.success(tenantId.toString(), conversationId.toString(), 4));

        mvc().perform(post("/api/admin/conversations/reset")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "conversationId": "%s",
                                  "deleteMessages": true
                                }
                                """.formatted(conversationId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.tenantId").value(tenantId.toString()))
                .andExpect(jsonPath("$.conversationId").value(conversationId.toString()))
                .andExpect(jsonPath("$.messagesDeleted").value(4))
                .andExpect(jsonPath("$.runtimeCacheCleared").value(false))
                .andExpect(jsonPath("$.leadsDeleted").value(0))
                .andExpect(jsonPath("$.purchaseRequestsDeleted").value(0));

        verify(resetService).reset(eq(tenantId), any(ConversationResetRequest.class));
    }

    @Test
    void tenantAdminResetsOwnTenantConversation() throws Exception {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        UUID conversationId = UUID.fromString("fd0f4034-42c9-4217-9df3-0353c93fcd7f");
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("tenant-admin", AppRole.TENANT_ADMIN, tenantId.toString(), "Tenant", "tenant@test.local"));
        when(resetService.reset(eq(tenantId), any(ConversationResetRequest.class)))
                .thenReturn(ConversationResetResponse.success(tenantId.toString(), conversationId.toString(), 1));

        mvc().perform(post("/api/admin/conversations/reset")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "conversationId": "%s",
                                  "deleteMessages": true
                                }
                                """.formatted(conversationId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.messagesDeleted").value(1));
    }

    @Test
    void tenantMemberCannotResetConversation() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN);

        mvc().perform(post("/api/admin/conversations/reset")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "conversationId": "fd0f4034-42c9-4217-9df3-0353c93fcd7f"
                                }
                                """))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new ConversationResetController(resetService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }
}
