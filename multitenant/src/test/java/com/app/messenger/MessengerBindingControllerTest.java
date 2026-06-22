package com.app.messenger;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.kb.ResolvedTenantKbDirectory;
import com.app.kb.TenantKbDirectoryResolver;
import com.app.kb.TenantKbDirectorySource;
import com.app.messenger.dto.CreateMessengerBindingDto;
import com.app.messenger.dto.MessengerBindingStatusResponse;
import com.app.messenger.dto.MessengerPageBindingResponse;
import com.app.modelserver.LlmInstanceManager;
import com.app.tenant.TenantContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class MessengerBindingControllerTest {

    @Mock
    private MessengerPageBindingRepository bindingRepo;
    @Mock
    private ChatbotInstanceRepository botRepo;
    @Mock
    private SessionPrincipalAccessor principalAccessor;
    @Mock
    private TenantKbDirectoryResolver tenantKbDirectoryResolver;
    @Mock
    private LlmInstanceManager llmInstanceManager;

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void platformAdminCanCreateBindingForTenantContext() {
        UUID tenantId = UUID.fromString("10000000-0000-4000-8000-000000000101");
        UUID chatbotId = UUID.randomUUID();
        TenantContext.set(tenantId.toString());

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("platform-admin", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin"));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot(chatbotId, tenantId)));
        when(bindingRepo.findByPageIdAndStatus("page-1", "ACTIVE")).thenReturn(Optional.empty());
        when(bindingRepo.save(any(MessengerPageBinding.class))).thenAnswer(invocation -> invocation.getArgument(0));

        MessengerBindingController controller = new MessengerBindingController(
                bindingRepo,
                botRepo,
                principalAccessor,
                tenantKbDirectoryResolver,
                llmInstanceManager
        );

        MessengerPageBindingResponse result = controller.create(new CreateMessengerBindingDto(
                "page-1",
                chatbotId,
                "EAAB-token-1-abcd"
        ));

        assertEquals(tenantId, result.tenantId());
        assertEquals(chatbotId, result.chatbotId());
        assertEquals("page-1", result.pageId());
        assertEquals("ACTIVE", result.status());
        assertTrue(result.tokenConfigured());
        assertEquals("EAAB...abcd", result.tokenPreview());

        ArgumentCaptor<MessengerPageBinding> saved = ArgumentCaptor.forClass(MessengerPageBinding.class);
        verify(bindingRepo).save(saved.capture());
        assertEquals(tenantId, saved.getValue().getTenantId());
    }

    @Test
    void tenantAdminStillCreatesBindingForOwnTenant() {
        UUID tenantId = UUID.fromString("10000000-0000-4000-8000-000000000101");
        UUID chatbotId = UUID.randomUUID();

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("member-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Admin", "admin@example.test"));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot(chatbotId, tenantId)));
        when(bindingRepo.findByPageIdAndStatus("page-2", "ACTIVE")).thenReturn(Optional.empty());
        when(bindingRepo.save(any(MessengerPageBinding.class))).thenAnswer(invocation -> invocation.getArgument(0));

        MessengerBindingController controller = new MessengerBindingController(
                bindingRepo,
                botRepo,
                principalAccessor,
                tenantKbDirectoryResolver,
                llmInstanceManager
        );

        MessengerPageBindingResponse result = controller.create(new CreateMessengerBindingDto(
                "page-2",
                chatbotId,
                "token-2"
        ));

        assertEquals(tenantId, result.tenantId());
        assertEquals(chatbotId, result.chatbotId());
    }

    @Test
    void createAndListResponsesDoNotExposeRawPageAccessToken() throws Exception {
        UUID tenantId = UUID.fromString("10000000-0000-4000-8000-000000000101");
        UUID chatbotId = UUID.randomUUID();
        String rawToken = "EAAB-secret-token-abcd";

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("member-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Admin", "admin@example.test"));
        when(botRepo.findById(chatbotId)).thenReturn(Optional.of(bot(chatbotId, tenantId)));
        when(bindingRepo.findByPageIdAndStatus("page-3", "ACTIVE")).thenReturn(Optional.empty());
        when(bindingRepo.save(any(MessengerPageBinding.class))).thenAnswer(invocation -> invocation.getArgument(0));

        MessengerPageBinding saved = binding(tenantId, chatbotId, "page-3", rawToken, "ACTIVE");
        when(bindingRepo.findAllByTenantId(tenantId)).thenReturn(java.util.List.of(saved));

        MessengerBindingController controller = new MessengerBindingController(
                bindingRepo,
                botRepo,
                principalAccessor,
                tenantKbDirectoryResolver,
                llmInstanceManager
        );
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

        String createJson = objectMapper.writeValueAsString(controller.create(new CreateMessengerBindingDto(
                "page-3",
                chatbotId,
                rawToken
        )));
        String listJson = objectMapper.writeValueAsString(controller.listMine());
        String entityJson = objectMapper.writeValueAsString(saved);

        assertFalse(createJson.contains(rawToken));
        assertFalse(listJson.contains(rawToken));
        assertFalse(entityJson.contains(rawToken));
        assertFalse(createJson.contains("pageAccessToken"));
        assertFalse(listJson.contains("pageAccessToken"));
        assertFalse(entityJson.contains("pageAccessToken"));
        assertTrue(createJson.contains("\"token_configured\":true"));
        assertTrue(listJson.contains("\"token_preview\":\"EAAB...abcd\""));
    }

    @Test
    void bindingStatusReturnsDesiredKbAndRuntimeWithoutToken() throws Exception {
        UUID tenantId = UUID.fromString("10000000-0000-4000-8000-000000000101");
        UUID chatbotId = UUID.randomUUID();
        String rawToken = "EAAB-status-token-abcd";
        MessengerPageBinding binding = binding(tenantId, chatbotId, "page-status", rawToken, "ACTIVE");
        ResolvedTenantKbDirectory desired = new ResolvedTenantKbDirectory(
                tenantId,
                "/kb/tenant/v1",
                TenantKbDirectorySource.ACTIVE_VERSION,
                UUID.fromString("20000000-0000-4000-8000-000000000201"),
                "v1",
                null
        );
        LlmInstanceManager.RuntimeKbRunningSnapshot running = new LlmInstanceManager.RuntimeKbRunningSnapshot(
                LlmInstanceManager.OBSERVABILITY_JAVA_SPAWNED,
                "/kb/tenant/v1",
                "ACTIVE_VERSION",
                desired.versionId(),
                "v1",
                java.time.Instant.parse("2026-06-09T00:00:00Z"),
                java.time.Instant.parse("2026-06-09T00:05:00Z"),
                true,
                123L,
                null,
                null,
                null,
                null
        );

        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("member-1", AppRole.TENANT_ADMIN, tenantId.toString(), "Admin", "admin@example.test"));
        when(bindingRepo.findByPageIdAndStatus("page-status", "ACTIVE")).thenReturn(Optional.of(binding));
        when(tenantKbDirectoryResolver.resolve(tenantId)).thenReturn(desired);
        when(llmInstanceManager.getRuntimeKbStatus(tenantId))
                .thenReturn(new LlmInstanceManager.RuntimeKbStatusSnapshot(
                        tenantId,
                        new LlmInstanceManager.RuntimeKbDesiredSnapshot("/kb/tenant/v1", "ACTIVE_VERSION", desired.versionId(), "v1", null),
                        running,
                        true
                ));

        MessengerBindingController controller = new MessengerBindingController(
                bindingRepo,
                botRepo,
                principalAccessor,
                tenantKbDirectoryResolver,
                llmInstanceManager
        );
        MessengerBindingStatusResponse response = controller.status("page-status");
        String json = new ObjectMapper().findAndRegisterModules().writeValueAsString(response);

        assertTrue(response.bindingActive());
        assertEquals(tenantId, response.tenantId());
        assertEquals(chatbotId, response.chatbotId());
        assertEquals("/kb/tenant/v1", response.desiredKb().kbDir());
        assertEquals("JAVA_SPAWNED", response.runtime().mode());
        assertEquals(Boolean.TRUE, response.runtimeInSync());
        assertFalse(json.contains(rawToken));
        assertFalse(json.contains("pageAccessToken"));
    }

    @Test
    void bindingStatusReturnsInactiveForMissingActiveBinding() {
        when(principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN))
                .thenReturn(new AppPrincipal("member-1", AppRole.TENANT_ADMIN, UUID.randomUUID().toString(), "Admin", "admin@example.test"));
        when(bindingRepo.findByPageIdAndStatus("missing-page", "ACTIVE")).thenReturn(Optional.empty());

        MessengerBindingController controller = new MessengerBindingController(
                bindingRepo,
                botRepo,
                principalAccessor,
                tenantKbDirectoryResolver,
                llmInstanceManager
        );

        MessengerBindingStatusResponse response = controller.status("missing-page");

        assertFalse(response.bindingActive());
        assertEquals("NO_ACTIVE_BINDING", response.reason());
    }

    private static ChatbotInstance bot(UUID chatbotId, UUID tenantId) {
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(chatbotId);
        bot.setTenantId(tenantId);
        return bot;
    }

    private static MessengerPageBinding binding(UUID tenantId, UUID chatbotId, String pageId, String token, String status) {
        MessengerPageBinding binding = new MessengerPageBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenantId);
        binding.setChatbotId(chatbotId);
        binding.setPageId(pageId);
        binding.setPageAccessToken(token);
        binding.setStatus(status);
        return binding;
    }
}
