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
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/system-status")
@RequiredArgsConstructor
public class SystemStatusController {

    private final TenantRepository tenantRepository;
    private final ChatbotInstanceRepository chatbotInstanceRepository;
    private final MessengerPageBindingRepository messengerPageBindingRepository;
    private final TenantKbVersionRepository tenantKbVersionRepository;
    private final LlmInstanceManager llmInstanceManager;
    private final LlmProperties llmProperties;
    private final PurchaseRequestRepository purchaseRequestRepository;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public SystemStatusResponse status() {
        principalAccessor.requirePlatformAdmin();

        long totalMessengerBindings = messengerPageBindingRepository.count();
        long activeMessengerBindings = messengerPageBindingRepository.countByStatus("ACTIVE");
        long inactiveMessengerBindings = messengerPageBindingRepository.countByStatus("INACTIVE");

        return new SystemStatusResponse(
                new SystemStatusResponse.Tenants(tenantRepository.count()),
                new SystemStatusResponse.Chatbots(chatbotInstanceRepository.count()),
                new SystemStatusResponse.MessengerBindings(
                        totalMessengerBindings,
                        activeMessengerBindings,
                        inactiveMessengerBindings,
                        messengerPageBindingRepository.countWithConfiguredToken()
                ),
                new SystemStatusResponse.Kb(
                        tenantKbVersionRepository.count(),
                        tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.READY),
                        tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.FAILED),
                        tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.BUILDING),
                        tenantKbVersionRepository.countByStatus(TenantKbVersionStatus.ARCHIVED)
                ),
                new SystemStatusResponse.Runtime(
                        llmInstanceManager.dumpRuntimeStatuses().size(),
                        llmProperties.getBaseUrl() != null && !llmProperties.getBaseUrl().isBlank()
                ),
                new SystemStatusResponse.PurchaseRequests(
                        purchaseRequestRepository.count(),
                        purchaseRequestRepository.countByStatus(PurchaseRequestStatus.NEW.name()),
                        purchaseRequestRepository.countByStatus(PurchaseRequestStatus.CONTACTED.name()),
                        purchaseRequestRepository.countByStatus(PurchaseRequestStatus.COMPLETED.name())
                )
        );
    }
}
