package com.app.tenants;

import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
import java.util.UUID;

@Service
public class TenantProvisioningService {

    private final TenantRepository tenantRepository;

    public TenantProvisioningService(TenantRepository tenantRepository) {
        this.tenantRepository = tenantRepository;
    }

    public Tenant create(CreateTenantRequest request) {
        String code = normalizeRequired(request.code(), "code");
        String name = normalizeRequired(request.name(), "name");
        String apiKey = normalizeApiKey(request.apiKey());
        String kbDir = normalizeOptional(request.kbDir());
        String status = normalizeOptional(request.status());

        tenantRepository.findByCodeIgnoreCase(code)
                .ifPresent(existing -> {
                    throw new IllegalArgumentException("Tenant code already exists");
                });

        if (apiKey == null) {
            apiKey = UUID.randomUUID().toString().replace("-", "");
        } else {
            tenantRepository.findByApiKey(apiKey)
                    .ifPresent(existing -> {
                        throw new IllegalArgumentException("Tenant API key already exists");
                    });
        }

        Tenant tenant = new Tenant();
        tenant.setId(UUID.randomUUID());
        tenant.setCode(code);
        tenant.setName(name);
        tenant.setApiKey(apiKey);
        tenant.setKbDir(kbDir);
        tenant.setStatus(status == null ? "ACTIVE" : status);
        return tenantRepository.save(tenant);
    }

    public List<Tenant> list() {
        return tenantRepository.findAll().stream()
                .sorted(Comparator
                        .comparing((Tenant tenant) -> safe(tenant.getName()))
                        .thenComparing(tenant -> safe(tenant.getCode())))
                .toList();
    }

    public Tenant get(UUID tenantId) {
        return tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
    }

    private static String normalizeRequired(String value, String field) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new IllegalArgumentException("Missing " + field);
        }
        return normalized;
    }

    private static String normalizeApiKey(String value) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            return null;
        }
        if (normalized.length() < 12) {
            throw new IllegalArgumentException("apiKey must be at least 12 characters");
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

    private static String safe(String value) {
        return value == null ? "" : value.toLowerCase();
    }

    public record CreateTenantRequest(
            String code,
            String name,
            String apiKey,
            String kbDir,
            String status
    ) {
    }
}
