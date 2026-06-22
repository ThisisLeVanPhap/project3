package com.app.customers;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.*;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Integration test chứng minh identity stitching hoạt động qua query service.
 * Test này verify flow:
 * 1. Resolve Messenger identity với phone/email cụ thể
 * 2. Resolve Telegram identity với cùng phone/email
 * 3. Query API list/detail để verify cùng unifiedCustomerId và 2 identities
 */
class CustomerIdentityIntegrationTest {

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

        when(unifiedCustomerRepository.findFirstByTenantIdAndNormalizedPhone(any(UUID.class), any(String.class))).thenAnswer(invocation ->
                customers.values().stream()
                        .filter(customer -> invocation.getArgument(0).equals(customer.getTenantId()))
                        .filter(customer -> invocation.getArgument(1).equals(customer.getNormalizedPhone()))
                        .findFirst()
        );

        when(unifiedCustomerRepository.findFirstByTenantIdAndNormalizedEmail(any(UUID.class), any(String.class))).thenAnswer(invocation ->
                customers.values().stream()
                        .filter(customer -> invocation.getArgument(0).equals(customer.getTenantId()))
                        .filter(customer -> invocation.getArgument(1).equals(customer.getNormalizedEmail()))
                        .findFirst()
        );

        when(customerIdentityRepository.findByTenantIdAndChannelAndExternalUserId(any(UUID.class), any(String.class), any(String.class)))
                .thenAnswer(invocation -> Optional.ofNullable(identities.get(identityKey(
                        invocation.getArgument(0),
                        invocation.getArgument(1),
                        invocation.getArgument(2)
                ))));

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
    void identityStitchingAcrossMessengerAndTelegramWithSamePhoneAndEmail() {
        UUID tenantId = UUID.randomUUID();
        String testPhone = "0987654321";
        String testEmail = "customer@example.com";

        // Step 1: Resolve Messenger identity với phone/email
        ResolvedCustomer messenger = identityService.resolveOrCreateIdentity(
                tenantId,
                "messenger",
                "page:p123:sender:s456",
                "Nguyễn Văn A",
                testPhone,
                testEmail
        );

        // Step 2: Resolve Telegram identity với cùng phone/email
        ResolvedCustomer telegram = identityService.resolveOrCreateIdentity(
                tenantId,
                "telegram",
                "chat:789",
                "A Nguyễn",
                "+84 " + testPhone, // Different format but normalizes to same
                testEmail.toUpperCase() // Different case but normalizes to same
        );

        // Verify: Cùng unified customer
        assertEquals(
                messenger.unifiedCustomer().getId(),
                telegram.unifiedCustomer().getId(),
                "Messenger và Telegram với cùng phone/email phải resolve về cùng unified customer"
        );

        // Step 3: Query list customers
        List<CustomerIdentityQueryService.CustomerIdentityCustomerView> customerList = queryService.listCustomers(tenantId);
        assertEquals(1, customerList.size(), "Phải có đúng 1 unified customer");

        CustomerIdentityQueryService.CustomerIdentityCustomerView listView = customerList.get(0);
        assertEquals(messenger.unifiedCustomer().getId(), listView.unifiedCustomerId());
        assertEquals("0987654321", listView.normalizedPhone());
        assertEquals("customer@example.com", listView.normalizedEmail());

        // Step 4: Query detail customer
        CustomerIdentityQueryService.CustomerIdentityCustomerDetailView detail =
                queryService.getCustomerDetail(tenantId, messenger.unifiedCustomer().getId());

        // Verify detail response
        assertEquals(messenger.unifiedCustomer().getId(), detail.unifiedCustomerId());
        assertEquals(tenantId, detail.tenantId());
        assertEquals("0987654321", detail.normalizedPhone());
        assertEquals("customer@example.com", detail.normalizedEmail());

        // Verify identities
        assertEquals(2, detail.identities().size(), "Phải có 2 identities (Messenger + Telegram)");

        Set<String> channels = new HashSet<>();
        for (CustomerIdentityQueryService.CustomerIdentityIdentityView identity : detail.identities()) {
            channels.add(identity.channel());
            assertEquals(messenger.unifiedCustomer().getId(), identity.unifiedCustomerId());
        }

        assertTrue(channels.contains("messenger"), "Phải có Messenger identity");
        assertTrue(channels.contains("telegram"), "Phải có Telegram identity");
    }

    @Test
    void identityStitchingWorksWithLateLinking() {
        UUID tenantId = UUID.randomUUID();

        // Step 1: Tạo anonymous Messenger identity (không có phone/email)
        ResolvedCustomer anonymousMessenger = identityService.resolveOrCreateIdentity(
                tenantId,
                "messenger",
                "page:p1:sender:s1",
                "Anonymous User",
                null,
                null
        );

        // Step 2: Tạo Telegram identity với phone
        String testPhone = "0912345678";
        ResolvedCustomer knownTelegram = identityService.resolveOrCreateIdentity(
                tenantId,
                "telegram",
                "chat:42",
                "Known User",
                testPhone,
                null
        );

        // Verify: 2 customers khác nhau (chưa merge)
        assertEquals(2, queryService.listCustomers(tenantId).size());

        // Step 3: Messenger identity later cung cấp phone (late linking)
        ResolvedCustomer updatedMessenger = identityService.resolveOrCreateIdentity(
                tenantId,
                "messenger",
                "page:p1:sender:s1",
                "Anonymous User",
                testPhone,
                null
        );

        // Verify: Giờ merge về cùng customer
        assertEquals(
                knownTelegram.unifiedCustomer().getId(),
                updatedMessenger.unifiedCustomer().getId(),
                "Late linking phải merge anonymous identity vào known customer"
        );

        // Step 4: Query detail verify
        CustomerIdentityQueryService.CustomerIdentityCustomerDetailView detail =
                queryService.getCustomerDetail(tenantId, knownTelegram.unifiedCustomer().getId());

        assertEquals(2, detail.identities().size());
        assertEquals(testPhone, detail.normalizedPhone());
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