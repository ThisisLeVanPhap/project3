package com.app.kb;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "tenant_kb_bindings")
@Getter
@Setter
public class TenantKbBinding {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "artifact_id")
    private UUID artifactId;

    @Column(name = "dataset_id", nullable = false, length = 160)
    private String datasetId;

    @Column(nullable = false)
    private boolean active;

    @Enumerated(EnumType.STRING)
    @Column(name = "update_policy", nullable = false, length = 32)
    private TenantKbBindingUpdatePolicy updatePolicy;

    @Column(name = "active_kb_version_id")
    private UUID activeKbVersionId;

    @Column(name = "bound_at")
    private Instant boundAt;

    @Column(name = "unbound_at")
    private Instant unboundAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (createdAt == null) {
            createdAt = now;
        }
        if (updatedAt == null) {
            updatedAt = now;
        }
    }
}
