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
@Table(name = "customer_identities")
public class CustomerIdentity {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "unified_customer_id", nullable = false)
    private UUID unifiedCustomerId;

    @Column(nullable = false, length = 64)
    private String channel;

    @Column(name = "external_user_id", nullable = false, length = 512)
    private String externalUserId;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "last_seen_at")
    private Instant lastSeenAt;

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

    public UUID getUnifiedCustomerId() {
        return unifiedCustomerId;
    }

    public void setUnifiedCustomerId(UUID unifiedCustomerId) {
        this.unifiedCustomerId = unifiedCustomerId;
    }

    public String getChannel() {
        return channel;
    }

    public void setChannel(String channel) {
        this.channel = required(channel, "channel");
    }

    public String getExternalUserId() {
        return externalUserId;
    }

    public void setExternalUserId(String externalUserId) {
        this.externalUserId = required(externalUserId, "externalUserId");
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = clean(displayName);
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getLastSeenAt() {
        return lastSeenAt;
    }

    public void markSeen() {
        lastSeenAt = Instant.now();
    }

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (createdAt == null) {
            createdAt = Instant.now();
        }
        if (lastSeenAt == null) {
            lastSeenAt = createdAt;
        }
        normalizeFields();
    }

    @PreUpdate
    void preUpdate() {
        if (lastSeenAt == null) {
            lastSeenAt = Instant.now();
        }
        normalizeFields();
    }

    private void normalizeFields() {
        channel = required(channel, "channel");
        externalUserId = required(externalUserId, "externalUserId");
        displayName = clean(displayName);
    }

    private static String required(String value, String field) {
        String cleaned = clean(value);
        if (cleaned == null) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
        return cleaned;
    }

    private static String clean(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isBlank() ? null : trimmed;
    }
}
