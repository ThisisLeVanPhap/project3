package com.app.onboarding;

import com.app.auth.TenantMemberManagementService;
import com.app.auth.TenantMemberManagementService.CreateTenantMemberRequest;
import com.app.auth.TenantMemberManagementService.TenantMemberResponse;
import com.app.tenants.Tenant;
import com.app.tenants.TenantProvisioningService;
import com.app.tenants.TenantProvisioningService.CreateTenantRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.text.Normalizer;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantOnboardingService {

    private final TenantOnboardingRequestRepository repository;
    private final TenantProvisioningService tenantProvisioningService;
    private final TenantMemberManagementService tenantMemberManagementService;

    public TenantOnboardingService(
            TenantOnboardingRequestRepository repository,
            TenantProvisioningService tenantProvisioningService,
            TenantMemberManagementService tenantMemberManagementService
    ) {
        this.repository = repository;
        this.tenantProvisioningService = tenantProvisioningService;
        this.tenantMemberManagementService = tenantMemberManagementService;
    }

    public TenantOnboardingResponse create(CreateOnboardingRequest request) {
        TenantOnboardingRequest entity = new TenantOnboardingRequest();
        entity.setStoreName(normalizeRequired(request.storeName(), "storeName"));
        entity.setContactName(normalizeRequired(request.contactName(), "contactName"));
        entity.setEmail(normalizeEmail(request.email()));
        entity.setPhone(normalizeRequired(request.phone(), "phone"));
        entity.setWebsiteUrl(normalizeOptional(request.websiteUrl()));
        entity.setNote(normalizeOptional(request.note()));
        entity.setStatus(TenantOnboardingStatus.NEW.name());
        return TenantOnboardingResponse.from(repository.save(entity));
    }

    public List<TenantOnboardingResponse> list(String status) {
        List<TenantOnboardingRequest> items;
        String normalizedStatus = normalizeOptional(status);
        if (normalizedStatus == null) {
            items = repository.findAllByOrderByCreatedAtDesc();
        } else {
            items = repository.findAllByStatusOrderByCreatedAtDesc(TenantOnboardingStatus.parse(normalizedStatus).name());
        }
        return items.stream().map(TenantOnboardingResponse::from).toList();
    }

    @Transactional
    public TenantOnboardingResponse updateStatus(UUID requestId, UpdateOnboardingStatusRequest request) {
        TenantOnboardingRequest entity = getEntity(requestId);
        TenantOnboardingStatus status = TenantOnboardingStatus.parse(request.status());
        if (status == TenantOnboardingStatus.PROVISIONED) {
            throw new IllegalArgumentException("Use provision action to mark a request as PROVISIONED");
        }
        if (TenantOnboardingStatus.PROVISIONED.name().equals(entity.getStatus())) {
            throw new IllegalStateException("Provisioned request status cannot be changed");
        }
        entity.setStatus(status.name());
        entity.setAdminNote(normalizeOptional(request.adminNote()));
        return TenantOnboardingResponse.from(repository.save(entity));
    }

    @Transactional
    public TenantOnboardingResponse provision(UUID requestId, ProvisionTenantFromOnboardingRequest request) {
        TenantOnboardingRequest entity = getEntity(requestId);
        TenantOnboardingStatus currentStatus = TenantOnboardingStatus.parse(entity.getStatus());
        if (currentStatus == TenantOnboardingStatus.PROVISIONED) {
            return TenantOnboardingResponse.from(entity);
        }
        if (currentStatus == TenantOnboardingStatus.REJECTED) {
            throw new IllegalStateException("Rejected request cannot be provisioned");
        }
        if (currentStatus != TenantOnboardingStatus.APPROVED) {
            throw new IllegalStateException("Approve request before provisioning");
        }

        String tenantName = firstNonBlank(request.tenantName(), entity.getStoreName());
        String tenantCode = firstNonBlank(request.tenantCode(), slugify(tenantName));
        String ownerEmail = firstNonBlank(request.ownerEmail(), entity.getEmail());
        String ownerDisplayName = firstNonBlank(request.ownerDisplayName(), entity.getContactName());
        String ownerPassword = normalizeRequired(request.ownerPassword(), "ownerPassword");

        Tenant tenant = tenantProvisioningService.create(new CreateTenantRequest(
                tenantCode,
                tenantName,
                null,
                normalizeOptional(request.kbDir()),
                "ACTIVE"
        ));
        TenantMemberResponse owner = tenantMemberManagementService.create(
                tenant.getId(),
                new CreateTenantMemberRequest(
                        ownerEmail,
                        ownerDisplayName,
                        "TENANT_ADMIN",
                        "ACTIVE",
                        ownerPassword
                )
        );

        entity.setStatus(TenantOnboardingStatus.PROVISIONED.name());
        entity.setTenantId(tenant.getId());
        entity.setOwnerMemberId(owner.id());
        entity.setAdminNote(firstNonBlankOptional(request.adminNote(), entity.getAdminNote()));
        entity.setProvisionedAt(Instant.now());
        return TenantOnboardingResponse.from(repository.save(entity));
    }

    private TenantOnboardingRequest getEntity(UUID requestId) {
        return repository.findById(requestId)
                .orElseThrow(() -> new IllegalArgumentException("Onboarding request not found"));
    }

    private static String normalizeRequired(String value, String field) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new IllegalArgumentException("Missing " + field);
        }
        return normalized;
    }

    private static String normalizeEmail(String value) {
        String email = normalizeRequired(value, "email").toLowerCase(Locale.ROOT);
        if (!email.contains("@")) {
            throw new IllegalArgumentException("Invalid email");
        }
        return email;
    }

    private static String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String firstNonBlank(String first, String fallback) {
        String normalized = normalizeOptional(first);
        return normalized == null ? normalizeRequired(fallback, "fallback") : normalized;
    }

    private static String firstNonBlankOptional(String first, String fallback) {
        String normalized = normalizeOptional(first);
        return normalized == null ? normalizeOptional(fallback) : normalized;
    }

    private static String slugify(String value) {
        String withoutMarks = Normalizer.normalize(value, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "");
        String slug = withoutMarks.toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9]+", "_")
                .replaceAll("^_+|_+$", "");
        return slug.isBlank() ? "tenant_" + UUID.randomUUID().toString().substring(0, 8) : slug;
    }

    public record CreateOnboardingRequest(
            String storeName,
            String contactName,
            String email,
            String phone,
            String websiteUrl,
            String note
    ) {
    }

    public record UpdateOnboardingStatusRequest(
            String status,
            String adminNote
    ) {
    }

    public record ProvisionTenantFromOnboardingRequest(
            String tenantCode,
            String tenantName,
            String kbDir,
            String ownerEmail,
            String ownerDisplayName,
            String ownerPassword,
            String adminNote
    ) {
    }

    public record TenantOnboardingResponse(
            UUID id,
            String storeName,
            String contactName,
            String email,
            String phone,
            String websiteUrl,
            String note,
            String status,
            String adminNote,
            UUID tenantId,
            UUID ownerMemberId,
            Instant createdAt,
            Instant updatedAt,
            Instant provisionedAt
    ) {
        public static TenantOnboardingResponse from(TenantOnboardingRequest request) {
            return new TenantOnboardingResponse(
                    request.getId(),
                    request.getStoreName(),
                    request.getContactName(),
                    request.getEmail(),
                    request.getPhone(),
                    request.getWebsiteUrl(),
                    request.getNote(),
                    request.getStatus(),
                    request.getAdminNote(),
                    request.getTenantId(),
                    request.getOwnerMemberId(),
                    request.getCreatedAt(),
                    request.getUpdatedAt(),
                    request.getProvisionedAt()
            );
        }
    }
}
