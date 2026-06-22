package com.app.customers;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.*;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.data.domain.Sort.Direction.ASC;
import static org.springframework.http.HttpStatus.NOT_FOUND;

class CustomerIdentityQueryServiceTest {

    private UnifiedCustomerRepository unifiedCustomerRepository;
    private CustomerIdentityRepository customerIdentityRepository;
    private CustomerIdentityService identityService;
    private CustomerIdentityQueryService queryService;

    private final Map<UUID, UnifiedCustomer> customers = new LinkedHashMap<>();
    private final Map<String, CustomerIdentity> identities = new LinkedHashMap<>();

    @BeforeEach
    void setUp() {
        customers.clear();
        identities.clear();
        unifiedCustomerRepository = mock(UnifiedCustomerRepository.class);
        customerIdentityRepository = mock(CustomerIdentityRepository.class);

        when(unifiedCustomerRepository.save(any(UnifiedCustomer.class))).thenAnswer(invocation -> {
            UnifiedCustomer customer = invocation.getArgument(0);
            if (customer.getId() == null) {
                customer.setId(UUID.randomUUID());
            }
            if (customer.getCreatedAt() == null) {
                setCustomerTimestamps(customer);
            }
            customers.put(customer.getId(), customer);
            return customer;
        });
        when(customerIdentityRepository.save(any(CustomerIdentity.class))).thenAnswer(invocation -> {
            CustomerIdentity identity = invocation.getArgument(0);
            if (identity.getId() == null) {
                identity.setId(UUID.randomUUID());
            }
            if (identity.getCreatedAt() == null) {
                setIdentityTimestamps(identity);
            }
            identities.put(identityKey(identity.getTenantId(), identity.getChannel(), identity.getExternalUserId()), identity);
            return identity;
        });
        when(unifiedCustomerRepository.findFirstByTenantIdAndNormalizedPhone(any(UUID.class), any(String.class))).thenAnswer(invocation -> customers.values().stream()
                .filter(customer -> invocation.getArgument(0).equals(customer.getTenantId()))
                .filter(customer -> invocation.getArgument(1).equals(customer.getNormalizedPhone()))
                .findFirst());
        when(unifiedCustomerRepository.findFirstByTenantIdAndNormalizedEmail(any(UUID.class), any(String.class))).thenAnswer(invocation -> customers.values().stream()
                .filter(customer -> invocation.getArgument(0).equals(customer.getTenantId()))
                .filter(customer -> invocation.getArgument(1).equals(customer.getNormalizedEmail()))
                .findFirst());
        when(customerIdentityRepository.findByTenantIdAndChannelAndExternalUserId(any(UUID.class), any(String.class), any(String.class)))
                .thenAnswer(invocation -> Optional.ofNullable(identities.get(identityKey(invocation.getArgument(0), invocation.getArgument(1), invocation.getArgument(2)))));
        when(unifiedCustomerRepository.findByTenantId(any(UUID.class), any(org.springframework.data.domain.Sort.class))).thenAnswer(invocation -> {
            UUID tenantId = invocation.getArgument(0);
            return customers.values().stream()
                    .filter(customer -> tenantId.equals(customer.getTenantId()))
                    .sorted(Comparator.comparing(UnifiedCustomer::getCreatedAt))
                    .toList();
        });
        when(unifiedCustomerRepository.findByIdAndTenantId(any(UUID.class), any(UUID.class))).thenAnswer(invocation -> {
            UUID customerId = invocation.getArgument(0);
            UUID tenantId = invocation.getArgument(1);
            UnifiedCustomer customer = customers.get(customerId);
            if (customer == null || !tenantId.equals(customer.getTenantId())) {
                return Optional.empty();
            }
            return Optional.of(customer);
        });
        when(customerIdentityRepository.findByTenantIdAndUnifiedCustomerId(any(UUID.class), any(UUID.class))).thenAnswer(invocation -> {
            UUID tenantId = invocation.getArgument(0);
            UUID unifiedCustomerId = invocation.getArgument(1);
            return identities.values().stream()
                    .filter(identity -> tenantId.equals(identity.getTenantId()))
                    .filter(identity -> unifiedCustomerId.equals(identity.getUnifiedCustomerId()))
                    .sorted(Comparator.comparing(CustomerIdentity::getCreatedAt))
                    .toList();
        });

        identityService = new CustomerIdentityService(unifiedCustomerRepository, customerIdentityRepository);
        queryService = new CustomerIdentityQueryService(unifiedCustomerRepository, customerIdentityRepository);
    }

    @Test
    void detailShowsSameUnifiedCustomerWithTwoChannelIdentities() {
        UUID tenantId = UUID.randomUUID();
        ResolvedCustomer messenger = identityService.resolveOrCreateIdentity(
                tenantId, "messenger", "page:p1:sender:s1", "An", "0987654321", "an@example.com");
        ResolvedCustomer telegram = identityService.resolveOrCreateIdentity(
                tenantId, "telegram", "chat:42", "An Telegram", "+84 987 654 321", "AN@example.com");

        assertEquals(messenger.unifiedCustomer().getId(), telegram.unifiedCustomer().getId());

        CustomerIdentityQueryService.CustomerIdentityCustomerDetailView detail =
                queryService.getCustomerDetail(tenantId, messenger.unifiedCustomer().getId());

        assertEquals(2, detail.identities().size());
        assertEquals(Set.of("messenger", "telegram"), detail.identities().stream().map(CustomerIdentityQueryService.CustomerIdentityIdentityView::channel).collect(java.util.stream.Collectors.toSet()));
        assertEquals("0987654321", detail.normalizedPhone());
        assertEquals("an@example.com", detail.normalizedEmail());
    }

    @Test
    void listAndDetailAreTenantIsolated() {
        UUID tenantA = UUID.randomUUID();
        UUID tenantB = UUID.randomUUID();
        ResolvedCustomer a = identityService.resolveOrCreateIdentity(
                tenantA, "messenger", "page:p1:sender:s1", "An", "0987654321", null);
        identityService.resolveOrCreateIdentity(
                tenantB, "telegram", "chat:42", "Binh", "0987654321", null);

        List<CustomerIdentityQueryService.CustomerIdentityCustomerView> tenantAList = queryService.listCustomers(tenantA);
        assertEquals(1, tenantAList.size());
        assertEquals(a.unifiedCustomer().getId(), tenantAList.get(0).unifiedCustomerId());

        org.springframework.web.server.ResponseStatusException ex = assertThrows(
                org.springframework.web.server.ResponseStatusException.class,
                () -> queryService.getCustomerDetail(tenantB, a.unifiedCustomer().getId())
        );
        assertEquals(NOT_FOUND, ex.getStatusCode());
    }

    @Test
    void displayNameOnlyDoesNotMergeInQueryResults() {
        UUID tenantId = UUID.randomUUID();
        identityService.resolveOrCreateIdentity(tenantId, "messenger", "page:p1:sender:s1", "Nguyen Van A", null, null);
        identityService.resolveOrCreateIdentity(tenantId, "telegram", "chat:42", "Nguyen Van A", null, null);

        List<CustomerIdentityQueryService.CustomerIdentityCustomerView> list = queryService.listCustomers(tenantId);
        assertEquals(2, list.size());
    }

    private static String identityKey(UUID tenantId, String channel, String externalUserId) {
        return tenantId + "|" + channel + "|" + externalUserId;
    }

    private static void setCustomerTimestamps(UnifiedCustomer customer) {
        try {
            java.lang.reflect.Field createdAt = UnifiedCustomer.class.getDeclaredField("createdAt");
            java.lang.reflect.Field updatedAt = UnifiedCustomer.class.getDeclaredField("updatedAt");
            createdAt.setAccessible(true);
            updatedAt.setAccessible(true);
            Instant now = Instant.now();
            if (createdAt.get(customer) == null) {
                createdAt.set(customer, now);
            }
            if (updatedAt.get(customer) == null) {
                updatedAt.set(customer, now);
            }
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(e);
        }
    }

    private static void setIdentityTimestamps(CustomerIdentity identity) {
        try {
            java.lang.reflect.Field createdAt = CustomerIdentity.class.getDeclaredField("createdAt");
            java.lang.reflect.Field lastSeenAt = CustomerIdentity.class.getDeclaredField("lastSeenAt");
            createdAt.setAccessible(true);
            lastSeenAt.setAccessible(true);
            Instant now = Instant.now();
            if (createdAt.get(identity) == null) {
                createdAt.set(identity, now);
            }
            if (lastSeenAt.get(identity) == null) {
                lastSeenAt.set(identity, now);
            }
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(e);
        }
    }
}
