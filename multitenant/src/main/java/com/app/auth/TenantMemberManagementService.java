package com.app.auth;

import com.app.tenants.TenantRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantMemberManagementService {

    private final TenantMemberRepository tenantMemberRepository;
    private final TenantRepository tenantRepository;
    private final PasswordEncoder passwordEncoder;

    public TenantMemberManagementService(
            TenantMemberRepository tenantMemberRepository,
            TenantRepository tenantRepository,
            PasswordEncoder passwordEncoder
    ) {
        this.tenantMemberRepository = tenantMemberRepository;
        this.tenantRepository = tenantRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public List<TenantMemberResponse> listByTenant(UUID tenantId) {
        assertTenantExists(tenantId);
        return tenantMemberRepository.findAllByTenantIdOrderByEmailAsc(tenantId).stream()
                .map(TenantMemberResponse::from)
                .toList();
    }

    public TenantMemberResponse create(UUID tenantId, CreateTenantMemberRequest request) {
        assertTenantExists(tenantId);

        String email = normalizeRequired(request.email(), "email").toLowerCase(Locale.ROOT);
        String password = normalizeRequired(request.password(), "password");
        if (password.length() < 6) {
            throw new IllegalArgumentException("password must be at least 6 characters");
        }

        tenantMemberRepository.findByTenantIdAndEmailIgnoreCase(tenantId, email)
                .ifPresent(existing -> {
                    throw new IllegalArgumentException("Tenant member email already exists");
                });

        TenantMember member = new TenantMember();
        member.setId(UUID.randomUUID());
        member.setTenantId(tenantId);
        member.setEmail(email);
        member.setDisplayName(defaultDisplayName(request.displayName(), email));
        member.setRole(normalizeRole(request.role()));
        member.setStatus(normalizeStatus(request.status()));
        member.setPasswordHash(passwordEncoder.encode(password));

        return TenantMemberResponse.from(tenantMemberRepository.save(member));
    }

    private void assertTenantExists(UUID tenantId) {
        if (!tenantRepository.existsById(tenantId)) {
            throw new IllegalArgumentException("Tenant not found");
        }
    }

    private static String defaultDisplayName(String rawDisplayName, String email) {
        String displayName = normalizeOptional(rawDisplayName);
        return displayName == null ? email : displayName;
    }

    private static String normalizeRole(String rawRole) {
        String value = normalizeRequired(rawRole, "role").toUpperCase(Locale.ROOT);
        if (!value.equals(AppRole.TENANT_ADMIN.name()) && !value.equals(AppRole.TENANT_MEMBER.name())) {
            throw new IllegalArgumentException("Unsupported tenant member role: " + rawRole);
        }
        return value;
    }

    private static String normalizeStatus(String rawStatus) {
        String value = normalizeOptional(rawStatus);
        if (value == null) {
            return "ACTIVE";
        }
        String normalized = value.toUpperCase(Locale.ROOT);
        if (!normalized.equals("ACTIVE") && !normalized.equals("INACTIVE")) {
            throw new IllegalArgumentException("Unsupported tenant member status: " + rawStatus);
        }
        return normalized;
    }

    private static String normalizeRequired(String value, String field) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new IllegalArgumentException("Missing " + field);
        }
        return normalized;
    }

    private static String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    public record CreateTenantMemberRequest(
            String email,
            String displayName,
            String role,
            String status,
            String password
    ) {
    }

    public record TenantMemberResponse(
            UUID id,
            UUID tenantId,
            String email,
            String displayName,
            String role,
            String status
    ) {
        public static TenantMemberResponse from(TenantMember member) {
            return new TenantMemberResponse(
                    member.getId(),
                    member.getTenantId(),
                    member.getEmail(),
                    member.getDisplayName(),
                    member.getRole(),
                    member.getStatus()
            );
        }
    }
}
