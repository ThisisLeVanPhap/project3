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
@Table(name = "source_registry")
@Getter
@Setter
public class SourceRegistry {

    @Id
    private UUID id;

    @Column(name = "source_code", nullable = false, unique = true, length = 160)
    private String sourceCode;

    @Column(name = "source_name", length = 255)
    private String sourceName;

    @Column(name = "root_url", columnDefinition = "text")
    private String rootUrl;

    @Column(name = "sitemap_url", columnDefinition = "text")
    private String sitemapUrl;

    @Column(length = 255)
    private String domain;

    @Column(nullable = false, length = 32)
    private String visibility;

    @Column(name = "owner_tenant_id")
    private UUID ownerTenantId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "product_url_patterns", columnDefinition = "jsonb")
    private String productUrlPatterns;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "exclude_patterns", columnDefinition = "jsonb")
    private String excludePatterns;

    @Column(nullable = false)
    private boolean enabled;

    @Column(columnDefinition = "text")
    private String notes;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (id == null) id = UUID.randomUUID();
        if (visibility == null || visibility.isBlank()) visibility = "TENANT_BOUND";
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
    }

    @PreUpdate
    void preUpdate() { updatedAt = Instant.now(); }
}
