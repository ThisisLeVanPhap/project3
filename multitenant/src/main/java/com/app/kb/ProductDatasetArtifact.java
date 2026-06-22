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
        name = "product_dataset_artifacts",
        uniqueConstraints = @UniqueConstraint(name = "uq_product_dataset_artifacts_dataset_build", columnNames = {"dataset_id", "build_tag"})
)
@Getter
@Setter
public class ProductDatasetArtifact {

    @Id
    private UUID id;

    @Column(name = "dataset_record_id", nullable = false)
    private UUID datasetRecordId;

    @Column(name = "dataset_id", nullable = false, length = 160)
    private String datasetId;

    @Column(name = "build_tag", nullable = false, length = 96)
    private String buildTag;

    @Column(name = "artifact_path", nullable = false, length = 1024)
    private String artifactPath;

    @Column(name = "artifact_count")
    private Integer artifactCount;

    @Column(name = "quality_status", length = 32)
    private String qualityStatus;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ProductDatasetArtifactStatus status;

    @Column(name = "build_message", columnDefinition = "text")
    private String buildMessage;

    @Column(name = "built_at")
    private Instant builtAt;

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
