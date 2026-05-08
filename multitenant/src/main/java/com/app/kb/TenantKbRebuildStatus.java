package com.app.kb;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "tenant_kb_rebuild_status")
@Getter
@Setter
public class TenantKbRebuildStatus {

    @Id
    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "last_rebuild_started_at")
    private Instant lastRebuildStartedAt;

    @Column(name = "last_rebuild_finished_at")
    private Instant lastRebuildFinishedAt;

    @Column(name = "last_rebuild_status", length = 32)
    private String lastRebuildStatus;

    @Column(name = "last_rebuild_message", columnDefinition = "text")
    private String lastRebuildMessage;

    @Column(name = "rebuild_history_json", columnDefinition = "text")
    private String rebuildHistoryJson;
}
