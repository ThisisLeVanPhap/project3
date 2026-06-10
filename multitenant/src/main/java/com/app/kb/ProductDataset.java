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
        name = "product_datasets",
        uniqueConstraints = @UniqueConstraint(name = "uq_product_datasets_dataset_id", columnNames = "dataset_id")
)
@Getter
@Setter
public class ProductDataset {

    @Id
    private UUID id;

    @Column(name = "dataset_id", nullable = false, length = 160)
    private String datasetId;

    @Column(length = 120)
    private String source;

    @Column(name = "source_url", length = 1024)
    private String sourceUrl;

    @Column(length = 120)
    private String version;

    @Column(nullable = false, length = 1024)
    private String path;

    @Column(name = "product_count")
    private Integer productCount;

    @Column(name = "rag_chunk_count")
    private Integer ragChunkCount;

    @Column(name = "content_hash", length = 128)
    private String contentHash;

    @Column(name = "manifest_path", length = 1024)
    private String manifestPath;

    @Column(name = "created_at")
    private Instant createdAt;

    @Column(name = "registered_at", nullable = false, updatable = false)
    private Instant registeredAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ProductDatasetStatus status;

    @Column(name = "last_assigned_tenant_id")
    private UUID lastAssignedTenantId;

    @Column(name = "last_assigned_at")
    private Instant lastAssignedAt;

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (registeredAt == null) {
            registeredAt = Instant.now();
        }
        if (status == null) {
            status = ProductDatasetStatus.REGISTERED;
        }
    }
}
