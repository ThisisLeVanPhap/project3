package com.app.general;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "general_product_chunks")
@Getter
@Setter
public class GeneralProductChunk {

    @Id
    private UUID id;

    @Column(name = "general_product_id", nullable = false)
    private UUID generalProductId;

    @Column(name = "general_source_id", nullable = false)
    private UUID generalSourceId;

    @Column(nullable = false, columnDefinition = "text")
    private String text;

    @Column(name = "chunk_type", nullable = false, length = 64)
    private String chunkType;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private JsonNode metadata;

    @Column(name = "content_hash", nullable = false, length = 128)
    private String contentHash;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (chunkType == null || chunkType.isBlank()) {
            chunkType = "PRODUCT";
        }
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }
}
