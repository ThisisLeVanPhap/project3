package com.app.ops;

import com.app.ops.dto.PurchaseRequestOpsStatsDto;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PurchaseRequestOpsStatsServiceTest {

    @Mock
    private PurchaseRequestRepository purchaseRequestRepository;

    @InjectMocks
    private PurchaseRequestOpsStatsService purchaseRequestOpsStatsService;

    @Test
    void computesPlatformAndTenantStats() {
        when(purchaseRequestRepository.findAll()).thenReturn(List.of(
                purchaseRequest("tenant-a", "NEW", null),
                purchaseRequest("tenant-a", "CONTACTED", UUID.randomUUID()),
                purchaseRequest("tenant-a", "COMPLETED", UUID.randomUUID()),
                purchaseRequest("tenant-b", "NEW", null)
        ));

        PurchaseRequestOpsStatsDto platform = purchaseRequestOpsStatsService.getPlatformStats();
        Map<String, PurchaseRequestOpsStatsDto> byTenant = purchaseRequestOpsStatsService.getStatsByTenant();

        assertThat(platform.totalRequests()).isEqualTo(4);
        assertThat(platform.newCount()).isEqualTo(2);
        assertThat(platform.contactedCount()).isEqualTo(1);
        assertThat(platform.completedCount()).isEqualTo(1);
        assertThat(platform.assignedCount()).isEqualTo(2);
        assertThat(platform.unassignedCount()).isEqualTo(2);

        assertThat(byTenant.get("tenant-a").totalRequests()).isEqualTo(3);
        assertThat(byTenant.get("tenant-a").assignedCount()).isEqualTo(2);
        assertThat(byTenant.get("tenant-b").newCount()).isEqualTo(1);
        assertThat(purchaseRequestOpsStatsService.getTenantStats("missing")).isEqualTo(PurchaseRequestOpsStatsDto.empty());
    }

    private static PurchaseRequest purchaseRequest(String tenantId, String status, UUID assignedToMemberId) {
        PurchaseRequest request = new PurchaseRequest();
        request.setTenantId(tenantId);
        request.setChannel("messenger");
        request.setConversationId(UUID.randomUUID().toString());
        request.setCustomerName("Customer");
        request.setPhone("0123456789");
        request.setShippingAddress("123 Street");
        request.setStatus(status);
        request.setAssignedToMemberId(assignedToMemberId);
        return request;
    }
}
