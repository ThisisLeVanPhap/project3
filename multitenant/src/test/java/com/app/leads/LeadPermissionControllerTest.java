package com.app.leads;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import com.app.leads.channel.MessengerOutbox;
import com.app.leads.channel.TelegramOutbox;
import com.app.tenant.TenantContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class LeadPermissionControllerTest {

    @Mock
    private LeadRepository leadRepository;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Mock
    private MessengerOutbox messengerOutbox;

    @Mock
    private TelegramOutbox telegramOutbox;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void platformAdminListsSelectedTenantLeads() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        Lead lead = lead(11L, tenantId, "messenger", "conv-1", "psid-1");
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN)).thenReturn(platformAdmin());
        when(leadRepository.findTop200ByTenantIdOrderByCreatedAtDesc(tenantId)).thenReturn(List.of(lead));

        mvc(new LeadAdminController(leadRepository, principalAccessor))
                .perform(get("/admin/api/leads").param("tenantId", tenantId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(11))
                .andExpect(jsonPath("$[0].tenantId").value(tenantId))
                .andExpect(jsonPath("$[0].conversationId").value("conv-1"));
    }

    @Test
    void platformAdminUpdatesLeadStatusWithinSelectedTenantOnly() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        Lead lead = lead(12L, tenantId, "telegram", "conv-2", "chat-1");
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN)).thenReturn(platformAdmin());
        when(leadRepository.findByIdAndTenantId(12L, tenantId)).thenReturn(Optional.of(lead));
        when(leadRepository.save(lead)).thenReturn(lead);

        mvc(new LeadAdminController(leadRepository, principalAccessor))
                .perform(post("/admin/api/leads/{id}/status", 12L)
                        .param("tenantId", tenantId)
                        .param("status", "CONTACTED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CONTACTED"));

        verify(leadRepository).findByIdAndTenantId(12L, tenantId);
    }

    @Test
    void tenantMemberViewsOwnTenantLeadDetail() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        Lead lead = lead(13L, tenantId, "web", "conv-3", "web-user");
        when(principalAccessor.requireTenantOperator()).thenReturn(tenantMember(tenantId));
        when(principalAccessor.requireTenantIdMatching(tenantId)).thenReturn(tenantId);
        when(leadRepository.findByIdAndTenantId(13L, tenantId)).thenReturn(Optional.of(lead));

        mvc(new TenantLeadController(leadRepository, principalAccessor))
                .perform(get("/tenant/api/leads/{id}", 13L).param("tid", tenantId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(13))
                .andExpect(jsonPath("$.tenantId").value(tenantId));
    }

    @Test
    void tenantMemberCannotUpdateLeadFromDifferentTenant() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        when(principalAccessor.requireTenantOperator()).thenReturn(tenantMember(tenantId));
        when(principalAccessor.requireTenantIdMatching(tenantId)).thenReturn(tenantId);
        when(leadRepository.findByIdAndTenantId(99L, tenantId)).thenReturn(Optional.empty());

        mvc(new TenantLeadController(leadRepository, principalAccessor))
                .perform(post("/tenant/api/leads/{id}/status", 99L)
                        .param("tid", tenantId)
                        .param("status", "CONTACTED"))
                .andExpect(status().isNotFound());
    }

    @Test
    void tenantMemberReplyUsesTenantScopedLeadLookup() throws Exception {
        String tenantId = "8e0f40c4-83de-4d44-bf0f-5e53769595e0";
        Lead lead = lead(14L, tenantId, "messenger", "conv-4", "psid-4");
        when(principalAccessor.requireTenantOperator()).thenReturn(tenantMember(tenantId));
        when(principalAccessor.requireTenantIdMatching(tenantId)).thenReturn(tenantId);
        when(leadRepository.findByIdAndTenantId(14L, tenantId)).thenReturn(Optional.of(lead));

        mvc(new ReplyController(leadRepository, messengerOutbox, telegramOutbox, principalAccessor))
                .perform(post("/tenant/api/reply")
                        .param("tid", tenantId)
                        .contentType("application/json")
                        .content("""
                                {
                                  "leadId": 14,
                                  "message": "We will call you shortly"
                                }
                                """))
                .andExpect(status().isOk());

        verify(messengerOutbox).sendText(tenantId, "psid-4", "We will call you shortly");
    }

    private MockMvc mvc(Object controller) {
        return MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private static AppPrincipal platformAdmin() {
        return new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform", "platform@test.local");
    }

    private static AppPrincipal tenantMember(String tenantId) {
        return new AppPrincipal(UUID.randomUUID().toString(), AppRole.TENANT_MEMBER, tenantId, "Member", "member@test.local");
    }

    private static Lead lead(Long id, String tenantId, String channel, String conversationId, String customerHandle) throws Exception {
        Lead lead = Lead.createNew(tenantId, channel, conversationId, customerHandle, "{}", "user: hello");
        Field idField = Lead.class.getDeclaredField("id");
        idField.setAccessible(true);
        idField.set(lead, id);
        return lead;
    }
}
