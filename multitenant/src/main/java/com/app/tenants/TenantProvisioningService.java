package com.app.tenants;

import com.app.feedback.FeedbackRepository;
import com.app.leads.LeadRepository;
import com.app.modelserver.LlmInstanceManager;
import com.app.purchases.PurchaseRequestRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.List;
import java.util.UUID;

@Service
public class TenantProvisioningService {

    private static final String DEFAULT_KB_BASE_DIR = "/opt/app/chatbot/kb";

    private final TenantRepository tenantRepository;
    private final LeadRepository leadRepository;
    private final PurchaseRequestRepository purchaseRequestRepository;
    private final FeedbackRepository feedbackRepository;
    private final LlmInstanceManager llmInstanceManager;

    public TenantProvisioningService(
            TenantRepository tenantRepository,
            LeadRepository leadRepository,
            PurchaseRequestRepository purchaseRequestRepository,
            FeedbackRepository feedbackRepository,
            LlmInstanceManager llmInstanceManager
    ) {
        this.tenantRepository = tenantRepository;
        this.leadRepository = leadRepository;
        this.purchaseRequestRepository = purchaseRequestRepository;
        this.feedbackRepository = feedbackRepository;
        this.llmInstanceManager = llmInstanceManager;
    }

    @Transactional
    public Tenant create(CreateTenantRequest request) {
        String code = normalizeRequired(request.code(), "code");
        String name = normalizeRequired(request.name(), "name");
        String apiKey = normalizeApiKey(request.apiKey());
        String kbDir = normalizeOptional(request.kbDir());
        if (kbDir == null) {
            kbDir = defaultKbDir(code);
        }
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

    @Transactional
    public void delete(UUID tenantId) {
        Tenant tenant = get(tenantId);
        String tenantIdText = tenant.getId().toString();
        leadRepository.deleteByTenantId(tenantIdText);
        purchaseRequestRepository.deleteByTenantId(tenantIdText);
        feedbackRepository.deleteByTenantId(tenantIdText);
        tenantRepository.delete(tenant);
        llmInstanceManager.evictTenant(tenantId);
    }

    private static String defaultKbDir(String code) {
        return DEFAULT_KB_BASE_DIR + "/" + sanitizeTenantCodeForPath(code);
    }

    private static String sanitizeTenantCodeForPath(String code) {
        String normalized = code == null ? "" : code.trim().toLowerCase();
        normalized = normalized.replaceAll("[^a-z0-9_-]+", "_").replaceAll("^_+|_+$", "");
        if (normalized.isBlank()) {
            throw new IllegalArgumentException("Tenant code cannot be used as kbDir");
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
