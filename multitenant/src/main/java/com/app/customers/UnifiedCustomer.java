package com.app.customers;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "unified_customers")
public class UnifiedCustomer {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "normalized_phone")
    private String normalizedPhone;

    @Column(name = "normalized_email")
    private String normalizedEmail;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getTenantId() {
        return tenantId;
    }

    public void setTenantId(UUID tenantId) {
        this.tenantId = tenantId;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = clean(displayName);
    }

    public String getNormalizedPhone() {
        return normalizedPhone;
    }

    public void setNormalizedPhone(String normalizedPhone) {
        this.normalizedPhone = clean(normalizedPhone);
    }

    public String getNormalizedEmail() {
        return normalizedEmail;
    }

    public void setNormalizedEmail(String normalizedEmail) {
        this.normalizedEmail = clean(normalizedEmail);
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (createdAt == null) {
            createdAt = Instant.now();
        }
        updatedAt = updatedAt == null ? createdAt : updatedAt;
        normalizeFields();
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
        normalizeFields();
    }

    private void normalizeFields() {
        displayName = clean(displayName);
        normalizedPhone = clean(normalizedPhone);
        normalizedEmail = clean(normalizedEmail);
    }

    private static String clean(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isBlank() ? null : trimmed;
    }
}
