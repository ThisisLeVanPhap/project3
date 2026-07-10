package com.app.admin;

import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstanceRepository;
import com.app.kb.TenantKbVersionRepository;
import com.app.kb.TenantKbVersionStatus;
import com.app.messenger.MessengerPageBindingRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.modelserver.LlmProperties;
import com.app.purchases.PurchaseRequestRepository;
import com.app.purchases.PurchaseRequestStatus;
import com.app.tenants.TenantRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SystemStatusControllerTest {

    @Mock
    private TenantRepository tenantRepository;
    @Mock
    private ChatbotInstanceRepository chatbotInstanceRepository;
    @Mock
    private MessengerPageBindingRepository messengerPageBindingRepository;
    @Mock
    private TenantKbVersionRepository tenantKbVersionRepository;
    @Mock
    private LlmInstanceManager llmInstanceManager;
    @Mock
    private PurchaseRequestRepository purchaseRequestRepository;
    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void returnsAggregateStatusWithoutTokenData() throws Exception {
        LlmProperties llmProperties = new LlmProperties();
        llmProperties.setBaseUrl("");

        when(tenantRepository.count()).thenReturn(5L);
        when(chatbotInstanceRepository.count()).thenReturn(7L);
        when(messengerPageBindingRepository.count()).thenReturn(3L);
        when(messengerPageBindingRepository.countByStatus("ACTIVE")).thenReturn(2L);
        when(messengerPageBindingRepository.countByStatus("INACTIVE")).thenReturn(1L);
        when(messengerPageBindingRepository.countWithConfiguredToken()).thenReturn(2L);
        when(tenantKbVersionRepository.count()).thenReturn(12L);
        when(tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.READY)).thenReturn(8L);
        when(tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.FAILED)).thenReturn(1L);
        when(tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.BUILDING)).thenReturn(0L);
        when(tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.ARCHIVED)).thenReturn(3L);
        when(llmInstanceManager.dumpRuntimeStatuses()).thenReturn(Map.of());
        when(purchaseRequestRepository.count()).thenReturn(7L);
        when(purchaseRequestRepository.countByStatus(PurchaseRequestStatus.NEW.name())).thenReturn(4L);
        when(purchaseRequestRepository.countByStatus(PurchaseRequestStatus.PROCESSING.name())).thenReturn(2L);
        when(purchaseRequestRepository.countByStatus(PurchaseRequestStatus.COMPLETED.name())).thenReturn(1L);

        SystemStatusController controller = new SystemStatusController(
                tenantRepository,
                chatbotInstanceRepository,
                messengerPageBindingRepository,
                tenantKbVersionRepository,
                llmInstanceManager,
                llmProperties,
                purchaseRequestRepository,
                principalAccessor
        );

        SystemStatusResponse response = controller.status();
        String json = new ObjectMapper().writeValueAsString(response);

        verify(principalAccessor).requirePlatformAdmin();
        assertEquals(5L, response.tenants().total());
        assertEquals(7L, response.chatbots().total());
        assertEquals(3L, response.messengerBindings().total());
        assertEquals(2L, response.messengerBindings().active());
        assertEquals(2L, response.messengerBindings().tokenConfigured());
        assertEquals(12L, response.kb().versionsTotal());
        assertEquals(4L, response.purchaseRequests().newCount());
        assertFalse(json.contains("pageAccessToken"));
        assertFalse(json.contains("EAAB"));
    }
}
