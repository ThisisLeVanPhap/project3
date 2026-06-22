package com.app.customers;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CustomerIdentityServiceTest {

    private UnifiedCustomerRepository customerRepository;
    private CustomerIdentityRepository identityRepository;
    private CustomerIdentityService service;

    private final Map<UUID, UnifiedCustomer> customers = new HashMap<>();
    private final Map<String, CustomerIdentity> identities = new HashMap<>();

    @BeforeEach
    void setUp() {
        customers.clear();
        identities.clear();
        customerRepository = mock(UnifiedCustomerRepository.class);
        identityRepository = mock(CustomerIdentityRepository.class);

        when(customerRepository.save(any(UnifiedCustomer.class))).thenAnswer(invocation -> {
            UnifiedCustomer customer = invocation.getArgument(0);
            if (customer.getId() == null) {
                customer.setId(UUID.randomUUID());
            }
            customers.put(customer.getId(), customer);
            return customer;
        });
        when(identityRepository.save(any(CustomerIdentity.class))).thenAnswer(invocation -> {
            CustomerIdentity identity = invocation.getArgument(0);
            if (identity.getId() == null) {
                identity.setId(UUID.randomUUID());
            }
            identities.put(identityKey(identity.getTenantId(), identity.getChannel(), identity.getExternalUserId()), identity);
            return identity;
        });
        when(customerRepository.findById(any(UUID.class))).thenAnswer(invocation ->
                Optional.ofNullable(customers.get(invocation.getArgument(0))));
        when(customerRepository.findFirstByTenantIdAndNormalizedPhone(any(UUID.class), any(String.class))).thenAnswer(invocation -> {
            UUID tenantId = invocation.getArgument(0);
            String phone = invocation.getArgument(1);
            return customers.values().stream()
                    .filter(customer -> tenantId.equals(customer.getTenantId()))
                    .filter(customer -> phone.equals(customer.getNormalizedPhone()))
                    .findFirst();
        });
        when(customerRepository.findFirstByTenantIdAndNormalizedEmail(any(UUID.class), any(String.class))).thenAnswer(invocation -> {
            UUID tenantId = invocation.getArgument(0);
            String email = invocation.getArgument(1);
            return customers.values().stream()
                    .filter(customer -> tenantId.equals(customer.getTenantId()))
                    .filter(customer -> email.equals(customer.getNormalizedEmail()))
                    .findFirst();
        });
        when(identityRepository.findByTenantIdAndChannelAndExternalUserId(any(UUID.class), any(String.class), any(String.class)))
                .thenAnswer(invocation -> Optional.ofNullable(identities.get(identityKey(
                        invocation.getArgument(0),
                        invocation.getArgument(1),
                        invocation.getArgument(2)
                ))));

        service = new CustomerIdentityService(customerRepository, identityRepository);
    }

    @Test
    void sameTenantMessengerExternalIdRepeatIsIdempotent() {
        UUID tenantId = UUID.randomUUID();

        ResolvedCustomer first = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "An", "0987 654 321", null);
        ResolvedCustomer second = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "An", "0987654321", null);

        assertEquals(first.unifiedCustomer().getId(), second.unifiedCustomer().getId());
        assertEquals(first.identity().getId(), second.identity().getId());
        assertEquals(1, identities.size());
    }

    @Test
    void sameTenantSamePhoneMessengerThenTelegramResolvesSameCustomer() {
        UUID tenantId = UUID.randomUUID();

        ResolvedCustomer messenger = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "An", "0987 654 321", null);
        ResolvedCustomer telegram = service.resolveOrCreateIdentity(
                tenantId, "telegram", "telegram:chat:42", "An Telegram", "+84 987 654 321", null);

        assertEquals(messenger.unifiedCustomer().getId(), telegram.unifiedCustomer().getId());
        assertTrue(telegram.linkedByStrongIdentifier());
        assertEquals(2, identities.size());
    }

    @Test
    void differentTenantSamePhoneDoesNotMerge() {
        UUID tenantA = UUID.randomUUID();
        UUID tenantB = UUID.randomUUID();

        ResolvedCustomer a = service.resolveOrCreateIdentity(
                tenantA, "messenger", "messenger:page:p1:sender:s1", "An", "0987654321", null);
        ResolvedCustomer b = service.resolveOrCreateIdentity(
                tenantB, "telegram", "telegram:chat:42", "An", "0987654321", null);

        assertNotEquals(a.unifiedCustomer().getId(), b.unifiedCustomer().getId());
    }

    @Test
    void sameDisplayNameOnlyDoesNotMerge() {
        UUID tenantId = UUID.randomUUID();

        ResolvedCustomer first = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "Nguyen Van A", null, null);
        ResolvedCustomer second = service.resolveOrCreateIdentity(
                tenantId, "telegram", "telegram:chat:42", "Nguyen Van A", null, null);

        assertNotEquals(first.unifiedCustomer().getId(), second.unifiedCustomer().getId());
        assertFalse(second.linkedByStrongIdentifier());
    }

    @Test
    void phoneAndEmailNormalizationUseStrongIdentifiers() {
        assertEquals("0987654321", CustomerIdentityService.normalizePhone("0987 654 321"));
        assertEquals("0987654321", CustomerIdentityService.normalizePhone("+84 987 654 321"));
        assertEquals("buyer@example.com", CustomerIdentityService.normalizeEmail(" Buyer@Example.COM "));
    }

    @Test
    void existingIdentityWithoutPhoneLaterLinksToStrongCustomerSafely() {
        UUID tenantId = UUID.randomUUID();
        ResolvedCustomer anonymous = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "Anonymous", null, null);
        ResolvedCustomer known = service.resolveOrCreateIdentity(
                tenantId, "telegram", "telegram:chat:42", "Known", "0987654321", null);

        ResolvedCustomer updatedAnonymous = service.resolveOrCreateIdentity(
                tenantId, "messenger", "messenger:page:p1:sender:s1", "Anonymous", "+84 987 654 321", null);

        assertNotEquals(anonymous.unifiedCustomer().getId(), known.unifiedCustomer().getId());
        assertEquals(known.unifiedCustomer().getId(), updatedAnonymous.unifiedCustomer().getId());
        assertEquals(known.unifiedCustomer().getId(), updatedAnonymous.identity().getUnifiedCustomerId());
        assertTrue(updatedAnonymous.warning().isBlank());
    }

    private static String identityKey(UUID tenantId, String channel, String externalUserId) {
        return tenantId + "|" + channel + "|" + externalUserId;
    }
}
