package com.app.ops;

import com.app.ops.dto.PurchaseRequestOpsStatsDto;
import com.app.purchases.PurchaseRequest;
import com.app.purchases.PurchaseRequestRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PurchaseRequestOpsStatsService {

    private final PurchaseRequestRepository purchaseRequestRepository;

    public PurchaseRequestOpsStatsDto getPlatformStats() {
        return summarize(purchaseRequestRepository.findAll());
    }

    public PurchaseRequestOpsStatsDto getTenantStats(String tenantId) {
        return getStatsByTenant().getOrDefault(tenantId, PurchaseRequestOpsStatsDto.empty());
    }

    public Map<String, PurchaseRequestOpsStatsDto> getStatsByTenant() {
        return purchaseRequestRepository.findAll().stream()
                .collect(Collectors.groupingBy(PurchaseRequest::getTenantId))
                .entrySet().stream()
                .collect(Collectors.toMap(
                        Map.Entry::getKey,
                        entry -> summarize(entry.getValue())
                ));
    }

    private PurchaseRequestOpsStatsDto summarize(List<PurchaseRequest> requests) {
        long total = requests.size();
        long newCount = countByStatus(requests, "NEW");
        long contactedCount = countByStatus(requests, "PROCESSING");
        long completedCount = countByStatus(requests, "COMPLETED");
        long assignedCount = requests.stream().filter(request -> request.getAssignedToMemberId() != null).count();
        return new PurchaseRequestOpsStatsDto(
                total,
                newCount,
                contactedCount,
                completedCount,
                assignedCount,
                total - assignedCount
        );
    }

    private long countByStatus(List<PurchaseRequest> requests, String expectedStatus) {
        return requests.stream()
                .map(PurchaseRequest::getStatus)
                .filter(expectedStatus::equals)
                .count();
    }
}
