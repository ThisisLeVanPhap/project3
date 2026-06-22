package com.app.tenants;

import com.app.feedback.FeedbackRepository;
import com.app.leads.LeadRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.purchases.PurchaseRequestRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TenantProvisioningServiceTest {

    @Mock
    private TenantRepository tenantRepository;

    @Mock
    private LeadRepository leadRepository;

    @Mock
    private PurchaseRequestRepository purchaseRequestRepository;

    @Mock
    private FeedbackRepository feedbackRepository;

    @Mock
    private LlmInstanceManager llmInstanceManager;

    @Test
    void createsDefaultKbDirFromTenantCodeWhenMissing() {
        TenantProvisioningService service = service();
        when(tenantRepository.findByCodeIgnoreCase("moho_demo")).thenReturn(Optional.empty());
        when(tenantRepository.save(org.mockito.ArgumentMatchers.any(Tenant.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        Tenant tenant = service.create(new TenantProvisioningService.CreateTenantRequest(
                "moho_demo",
                "MOHO Demo",
                null,
                null,
                null
        ));

        assertThat(tenant.getKbDir()).isEqualTo("/opt/app/chatbot/kb/moho_demo");
        assertThat(tenant.getStatus()).isEqualTo("ACTIVE");
    }

    @Test
    void deletesTenantAndStringTenantScopedRecords() {
        UUID tenantId = UUID.fromString("daf0378f-53e1-4705-8234-41c74287e489");
        Tenant tenant = new Tenant();
        tenant.setId(tenantId);
        tenant.setCode("demo");
        TenantProvisioningService service = service();
        when(tenantRepository.findById(tenantId)).thenReturn(Optional.of(tenant));

        service.delete(tenantId);

        verify(leadRepository).deleteByTenantId(tenantId.toString());
        verify(purchaseRequestRepository).deleteByTenantId(tenantId.toString());
        verify(feedbackRepository).deleteByTenantId(tenantId.toString());
        verify(tenantRepository).delete(tenant);
        verify(llmInstanceManager).evictTenant(tenantId);
    }

    private TenantProvisioningService service() {
        return new TenantProvisioningService(
                tenantRepository,
                leadRepository,
                purchaseRequestRepository,
                feedbackRepository,
                llmInstanceManager
        );
    }
}
