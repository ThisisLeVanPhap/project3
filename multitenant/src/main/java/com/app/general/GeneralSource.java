package com.app.general;

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
@Table(name = "general_sources")
@Getter
@Setter
public class GeneralSource {

    @Id
    private UUID id;

    @Column(name = "source_code", nullable = false, length = 160)
    private String sourceCode;

    @Column(name = "source_name", length = 255)
    private String sourceName;

    @Column(name = "source_domain", length = 255)
    private String sourceDomain;

    @Column(name = "source_type", nullable = false, length = 64)
    private String sourceType;

    @Column(name = "tenant_id")
    private UUID tenantId;

    @Column(name = "dataset_id", length = 160)
    private String datasetId;

    @Column(name = "kb_version_id")
    private UUID kbVersionId;

    @Column(name = "artifact_id")
    private UUID artifactId;

    @Column(name = "source_ref", length = 255)
    private String sourceRef;

    @Column(nullable = false, length = 32)
    private String visibility;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "imported_at", nullable = false, updatable = false)
    private Instant importedAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (visibility == null || visibility.isBlank()) {
            visibility = "GLOBAL_PUBLIC";
        }
        if (status == null || status.isBlank()) {
            status = "ACTIVE";
        }
        if (importedAt == null) {
            importedAt = now;
        }
        if (updatedAt == null) {
            updatedAt = now;
        }
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }
}
