package com.app.general;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "crawl_materialize_jobs")
@Getter
@Setter
public class CrawlMaterializeJob {

    @Id
    private UUID id;

    @Column(name = "source_code", nullable = false, length = 160)
    private String sourceCode;

    @Column(name = "source_name", length = 255)
    private String sourceName;

    @Column(name = "root_url", columnDefinition = "text")
    private String rootUrl;

    @Column(name = "sitemap_url", columnDefinition = "text")
    private String sitemapUrl;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "product_urls", columnDefinition = "jsonb")
    private String productUrls;

    @Column(name = "dataset_id", length = 160)
    private String datasetId;

    @Column(name = "dataset_path", columnDefinition = "text")
    private String datasetPath;

    @Column(name = "max_urls", nullable = false)
    private int maxUrls;

    @Column(name = "product_only", nullable = false)
    private boolean productOnly;

    @Column(name = "run_quality_audit", nullable = false)
    private boolean runQualityAudit;

    @Column(name = "run_taxonomy_normalize", nullable = false)
    private boolean runTaxonomyNormalize;

    @Column(name = "register_dataset", nullable = false)
    private boolean registerDataset;

    @Column(length = 64)
    private String stage;

    @Column(name = "stage_message", columnDefinition = "text")
    private String stageMessage;

    @Column(name = "stage_updated_at")
    private Instant stageUpdatedAt;

    @Column(name = "total_urls", nullable = false)
    private int totalUrls;

    @Column(name = "processed_urls", nullable = false)
    private int processedUrls;

    @Column(name = "tenant_id")
    private UUID tenantId;

    @Column(nullable = false, length = 32)
    private String visibility;

    @Column(name = "build_artifact", nullable = false)
    private boolean buildArtifact;

    @Column(name = "bind_tenant", nullable = false)
    private boolean bindTenant;

    @Column(name = "import_general", nullable = false)
    private boolean importGeneral;

    @Column(name = "artifact_id")
    private UUID artifactId;

    @Column(name = "artifact_path", columnDefinition = "text")
    private String artifactPath;

    @Column(name = "active_kb_version_id")
    private UUID activeKbVersionId;

    @Column(name = "general_source_id")
    private UUID generalSourceId;

    @Column(name = "import_run_id")
    private UUID importRunId;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "product_count", nullable = false)
    private int productCount;

    @Column(name = "rag_chunk_count", nullable = false)
    private int ragChunkCount;

    @Column(name = "quality_status", length = 32)
    private String qualityStatus;

    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    @Column(name = "created_by", length = 255)
    private String createdBy;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (status == null || status.isBlank()) {
            status = "QUEUED";
        }
        if (visibility == null || visibility.isBlank()) {
            visibility = "TENANT_BOUND";
        }
        if (createdAt == null) {
            createdAt = now;
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
