package com.app.onboarding;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "tenant_onboarding_requests")
@Getter
@Setter
public class TenantOnboardingRequest {
    @Id
    private UUID id;

    @Column(name = "store_name", nullable = false)
    private String storeName;

    @Column(name = "contact_name", nullable = false)
    private String contactName;

    @Column(nullable = false)
    private String email;

    @Column(nullable = false)
    private String phone;

    @Column(name = "website_url")
    private String websiteUrl;

    @Column(columnDefinition = "TEXT")
    private String note;

    @Column(nullable = false)
    private String status = TenantOnboardingStatus.NEW.name();

    @Column(name = "admin_note", columnDefinition = "TEXT")
    private String adminNote;

    @Column(name = "tenant_id")
    private UUID tenantId;

    @Column(name = "owner_member_id")
    private UUID ownerMemberId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    @Column(name = "provisioned_at")
    private Instant provisionedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (createdAt == null) {
            createdAt = now;
        }
        updatedAt = now;
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }
}
