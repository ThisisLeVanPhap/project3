package com.app.customers;

import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

import static org.springframework.http.HttpStatus.NOT_FOUND;

@Service
public class CustomerIdentityQueryService {

    private final UnifiedCustomerRepository unifiedCustomerRepository;
    private final CustomerIdentityRepository customerIdentityRepository;

    public CustomerIdentityQueryService(
            UnifiedCustomerRepository unifiedCustomerRepository,
            CustomerIdentityRepository customerIdentityRepository
    ) {
        this.unifiedCustomerRepository = unifiedCustomerRepository;
        this.customerIdentityRepository = customerIdentityRepository;
    }

    @Transactional(readOnly = true)
    public List<CustomerIdentityCustomerView> listCustomers(UUID tenantId) {
        return unifiedCustomerRepository.findByTenantId(tenantId, Sort.by(Sort.Direction.ASC, "createdAt")).stream()
                .map(customer -> new CustomerIdentityCustomerView(
                        customer.getId(),
                        customer.getTenantId(),
                        customer.getDisplayName(),
                        customer.getNormalizedPhone(),
                        customer.getNormalizedEmail(),
                        customer.getCreatedAt(),
                        customer.getUpdatedAt()
                ))
                .toList();
    }

    @Transactional(readOnly = true)
    public CustomerIdentityCustomerDetailView getCustomerDetail(UUID tenantId, UUID customerId) {
        UnifiedCustomer customer = unifiedCustomerRepository.findByIdAndTenantId(customerId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Unified customer not found"));
        List<CustomerIdentityIdentityView> identities = customerIdentityRepository
                .findByTenantIdAndUnifiedCustomerId(tenantId, customerId)
                .stream()
                .map(identity -> new CustomerIdentityIdentityView(
                        identity.getId(),
                        identity.getUnifiedCustomerId(),
                        identity.getChannel(),
                        identity.getExternalUserId(),
                        identity.getDisplayName(),
                        identity.getCreatedAt(),
                        identity.getLastSeenAt()
                ))
                .toList();
        return new CustomerIdentityCustomerDetailView(
                customer.getId(),
                customer.getTenantId(),
                customer.getDisplayName(),
                customer.getNormalizedPhone(),
                customer.getNormalizedEmail(),
                customer.getCreatedAt(),
                customer.getUpdatedAt(),
                identities
        );
    }

    public record CustomerIdentityCustomerView(
            UUID unifiedCustomerId,
            UUID tenantId,
            String displayName,
            String normalizedPhone,
            String normalizedEmail,
            java.time.Instant createdAt,
            java.time.Instant updatedAt
    ) {
    }

    public record CustomerIdentityIdentityView(
            UUID identityId,
            UUID unifiedCustomerId,
            String channel,
            String externalUserId,
            String displayName,
            java.time.Instant createdAt,
            java.time.Instant lastSeenAt
    ) {
    }

    public record CustomerIdentityCustomerDetailView(
            UUID unifiedCustomerId,
            UUID tenantId,
            String displayName,
            String normalizedPhone,
            String normalizedEmail,
            java.time.Instant createdAt,
            java.time.Instant updatedAt,
            List<CustomerIdentityIdentityView> identities
    ) {
    }
}
