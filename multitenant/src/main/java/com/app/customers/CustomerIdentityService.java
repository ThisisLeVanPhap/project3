package com.app.customers;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Locale;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Service
public class CustomerIdentityService {

    private final UnifiedCustomerRepository unifiedCustomerRepository;
    private final CustomerIdentityRepository customerIdentityRepository;

    public CustomerIdentityService(
            UnifiedCustomerRepository unifiedCustomerRepository,
            CustomerIdentityRepository customerIdentityRepository
    ) {
        this.unifiedCustomerRepository = unifiedCustomerRepository;
        this.customerIdentityRepository = customerIdentityRepository;
    }

    @Transactional
    public ResolvedCustomer resolveOrCreateIdentity(
            UUID tenantId,
            String channel,
            String externalUserId,
            String displayName,
            String phone,
            String email
    ) {
        UUID requiredTenantId = requireTenantId(tenantId);
        String normalizedChannel = normalizeRequired(channel, "channel").toLowerCase(Locale.ROOT);
        String normalizedExternalUserId = normalizeRequired(externalUserId, "externalUserId");
        String cleanDisplayName = normalizeNullable(displayName);
        String normalizedPhone = normalizePhone(phone);
        String normalizedEmail = normalizeEmail(email);

        Optional<CustomerIdentity> existingIdentity =
                customerIdentityRepository.findByTenantIdAndChannelAndExternalUserId(
                        requiredTenantId,
                        normalizedChannel,
                        normalizedExternalUserId
                );
        if (existingIdentity.isPresent()) {
            return resolveExistingIdentity(
                    existingIdentity.get(),
                    cleanDisplayName,
                    normalizedPhone,
                    normalizedEmail
            );
        }

        MatchResult match = findByStrongIdentifier(requiredTenantId, normalizedPhone, normalizedEmail);
        UnifiedCustomer customer = match.customer()
                .orElseGet(() -> createCustomer(requiredTenantId, cleanDisplayName, normalizedPhone, normalizedEmail));
        boolean createdCustomer = match.customer().isEmpty();

        if (!createdCustomer) {
            fillStrongIdentifiers(customer, normalizedPhone, normalizedEmail);
            fillDisplayName(customer, cleanDisplayName);
            unifiedCustomerRepository.save(customer);
        }

        CustomerIdentity identity = new CustomerIdentity();
        identity.setTenantId(requiredTenantId);
        identity.setUnifiedCustomerId(customer.getId());
        identity.setChannel(normalizedChannel);
        identity.setExternalUserId(normalizedExternalUserId);
        identity.setDisplayName(cleanDisplayName);
        identity.markSeen();
        CustomerIdentity savedIdentity = customerIdentityRepository.save(identity);

        return new ResolvedCustomer(
                customer,
                savedIdentity,
                createdCustomer,
                true,
                match.matched(),
                ""
        );
    }

    public static String normalizePhone(String value) {
        String cleaned = normalizeNullable(value);
        if (cleaned == null) {
            return null;
        }
        String digits = cleaned.replaceAll("\\D", "");
        if (digits.isBlank()) {
            return null;
        }
        if (digits.startsWith("84") && digits.length() == 11) {
            return "0" + digits.substring(2);
        }
        if (digits.startsWith("0084") && digits.length() == 13) {
            return "0" + digits.substring(4);
        }
        return digits;
    }

    public static String normalizeEmail(String value) {
        String cleaned = normalizeNullable(value);
        return cleaned == null ? null : cleaned.toLowerCase(Locale.ROOT);
    }

    private ResolvedCustomer resolveExistingIdentity(
            CustomerIdentity identity,
            String displayName,
            String normalizedPhone,
            String normalizedEmail
    ) {
        UnifiedCustomer current = unifiedCustomerRepository.findById(identity.getUnifiedCustomerId())
                .orElseGet(() -> createCustomer(identity.getTenantId(), displayName, normalizedPhone, normalizedEmail));

        MatchResult match = findByStrongIdentifier(identity.getTenantId(), normalizedPhone, normalizedEmail);
        Optional<UnifiedCustomer> matchedCustomer = match.customer();
        if (matchedCustomer.isPresent() && matchedCustomer.get().getId().equals(current.getId())) {
            matchedCustomer = Optional.empty();
        }

        String warning = "";
        boolean linkedByStrongIdentifier = false;
        if (matchedCustomer.isPresent()) {
            if (hasNoStrongIdentifier(current)) {
                current = matchedCustomer.get();
                identity.setUnifiedCustomerId(current.getId());
                linkedByStrongIdentifier = true;
            } else {
                warning = "identity_conflict_not_merged";
                log.warn(
                        "Skipped customer identity merge tenant={} identity={} currentCustomer={} matchedCustomer={}",
                        identity.getTenantId(),
                        identity.getId(),
                        identity.getUnifiedCustomerId(),
                        matchedCustomer.get().getId()
                );
            }
        }

        if (warning.isBlank()) {
            fillStrongIdentifiers(current, normalizedPhone, normalizedEmail);
            fillDisplayName(current, displayName);
            unifiedCustomerRepository.save(current);
        }
        if (displayName != null && (identity.getDisplayName() == null || identity.getDisplayName().isBlank())) {
            identity.setDisplayName(displayName);
        }
        identity.markSeen();
        CustomerIdentity savedIdentity = customerIdentityRepository.save(identity);

        return new ResolvedCustomer(
                current,
                savedIdentity,
                false,
                false,
                linkedByStrongIdentifier || match.matched(),
                warning
        );
    }

    private MatchResult findByStrongIdentifier(UUID tenantId, String normalizedPhone, String normalizedEmail) {
        if (normalizedPhone != null) {
            Optional<UnifiedCustomer> byPhone =
                    unifiedCustomerRepository.findFirstByTenantIdAndNormalizedPhone(tenantId, normalizedPhone);
            if (byPhone.isPresent()) {
                return new MatchResult(byPhone, true);
            }
        }
        if (normalizedEmail != null) {
            Optional<UnifiedCustomer> byEmail =
                    unifiedCustomerRepository.findFirstByTenantIdAndNormalizedEmail(tenantId, normalizedEmail);
            if (byEmail.isPresent()) {
                return new MatchResult(byEmail, true);
            }
        }
        return new MatchResult(Optional.empty(), false);
    }

    private UnifiedCustomer createCustomer(
            UUID tenantId,
            String displayName,
            String normalizedPhone,
            String normalizedEmail
    ) {
        UnifiedCustomer customer = new UnifiedCustomer();
        customer.setId(UUID.randomUUID());
        customer.setTenantId(tenantId);
        customer.setDisplayName(displayName);
        customer.setNormalizedPhone(normalizedPhone);
        customer.setNormalizedEmail(normalizedEmail);
        return unifiedCustomerRepository.save(customer);
    }

    private static void fillStrongIdentifiers(
            UnifiedCustomer customer,
            String normalizedPhone,
            String normalizedEmail
    ) {
        if (customer.getNormalizedPhone() == null && normalizedPhone != null) {
            customer.setNormalizedPhone(normalizedPhone);
        }
        if (customer.getNormalizedEmail() == null && normalizedEmail != null) {
            customer.setNormalizedEmail(normalizedEmail);
        }
    }

    private static void fillDisplayName(UnifiedCustomer customer, String displayName) {
        if ((customer.getDisplayName() == null || customer.getDisplayName().isBlank()) && displayName != null) {
            customer.setDisplayName(displayName);
        }
    }

    private static boolean hasNoStrongIdentifier(UnifiedCustomer customer) {
        return customer.getNormalizedPhone() == null && customer.getNormalizedEmail() == null;
    }

    private static UUID requireTenantId(UUID tenantId) {
        if (tenantId == null) {
            throw new IllegalArgumentException("tenantId must not be null");
        }
        return tenantId;
    }

    private static String normalizeRequired(String value, String field) {
        String normalized = normalizeNullable(value);
        if (normalized == null) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
        return normalized;
    }

    private static String normalizeNullable(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.replaceAll("\\s{2,}", " ").trim();
        return trimmed.isBlank() ? null : trimmed;
    }

    private record MatchResult(Optional<UnifiedCustomer> customer, boolean matched) {
    }
}
