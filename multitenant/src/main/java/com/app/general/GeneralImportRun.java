package com.app.general;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "general_import_runs")
@Getter
@Setter
public class GeneralImportRun {

    @Id
    private UUID id;

    @Column(name = "source_type", nullable = false, length = 64)
    private String sourceType;

    @Column(name = "source_ref", nullable = false, length = 255)
    private String sourceRef;

    @Column(name = "general_source_id")
    private UUID generalSourceId;

    @Column(nullable = false, length = 32)
    private String status;

    @Column(name = "products_seen", nullable = false)
    private int productsSeen;

    @Column(name = "products_imported", nullable = false)
    private int productsImported;

    @Column(name = "products_updated", nullable = false)
    private int productsUpdated;

    @Column(name = "chunks_seen", nullable = false)
    private int chunksSeen;

    @Column(name = "chunks_imported", nullable = false)
    private int chunksImported;

    @Column(name = "chunks_updated", nullable = false)
    private int chunksUpdated;

    @Column(columnDefinition = "text")
    private String message;

    @Column(name = "started_at", nullable = false)
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (startedAt == null) {
            startedAt = Instant.now();
        }
    }
}
