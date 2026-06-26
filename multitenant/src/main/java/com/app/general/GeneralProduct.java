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
import com.fasterxml.jackson.databind.JsonNode;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "general_products")
@Getter
@Setter
public class GeneralProduct {

    @Id
    private UUID id;

    @Column(name = "general_source_id")
    private UUID generalSourceId;

    @Column(name = "dataset_record_id", nullable = false)
    private UUID datasetRecordId;

    @Column(name = "artifact_id")
    private UUID artifactId;

    @Column(name = "dataset_id", nullable = false, length = 160)
    private String datasetId;

    @Column(name = "artifact_build_tag", length = 96)
    private String artifactBuildTag;

    @Column(length = 120)
    private String source;

    @Column(name = "source_code", length = 160)
    private String sourceCode;

    @Column(name = "source_domain", length = 255)
    private String sourceDomain;

    @Column(name = "source_url", columnDefinition = "text")
    private String sourceUrl;

    @Column(name = "product_id", length = 160)
    private String productId;

    @Column(name = "external_product_id", length = 160)
    private String externalProductId;

    @Column(length = 160)
    private String sku;

    @Column(length = 512)
    private String name;

    @Column(name = "normalized_name", length = 512)
    private String normalizedName;

    @Column(length = 160)
    private String category;

    @Column(name = "product_type", length = 160)
    private String productType;

    @Column(length = 160)
    private String brand;

    @Column(length = 255)
    private String material;

    @Column(length = 255)
    private String dimensions;

    @Column(name = "dimensions_text", length = 255)
    private String dimensionsText;

    @Column(precision = 14, scale = 2)
    private BigDecimal price;

    @Column(name = "original_price", precision = 14, scale = 2)
    private BigDecimal originalPrice;

    @Column(length = 16)
    private String currency;

    @Column(name = "product_url", columnDefinition = "text")
    private String productUrl;

    @Column(name = "image_url", columnDefinition = "text")
    private String imageUrl;

    @Column(columnDefinition = "text")
    private String description;

    @Column(name = "quality_score", precision = 5, scale = 2)
    private BigDecimal qualityScore;

    @Column(name = "extraction_confidence", precision = 5, scale = 2)
    private BigDecimal extractionConfidence;

    @Column(nullable = false, length = 32)
    private String visibility;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "content_hash", length = 128)
    private String contentHash;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private JsonNode raw;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

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
        if (createdAt == null) {
            createdAt = now;
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
