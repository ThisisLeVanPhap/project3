package com.app.kb;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "tenant_kb_versions",
        uniqueConstraints = @UniqueConstraint(name = "uq_tenant_kb_versions_tenant_version_tag", columnNames = {"tenant_id", "version_tag"})
)
@Getter
@Setter
public class TenantKbVersion {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "version_tag", nullable = false, length = 64)
    private String versionTag;

    @Column(name = "kb_dir", nullable = false, length = 1024)
    private String kbDir;

    @Column(name = "source_url_snapshot", columnDefinition = "text")
    private String sourceUrlSnapshot;

    @Column(name = "source_type", length = 64)
    private String sourceType;

    @Column(name = "dataset_id", length = 160)
    private String datasetId;

    @Column(name = "artifact_count")
    private Integer artifactCount;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private TenantKbVersionStatus status;

    @Column(name = "build_message", columnDefinition = "text")
    private String buildMessage;

    @Column(name = "built_at")
    private Instant builtAt;

    @Column(name = "published_at")
    private Instant publishedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }
}
