package com.app.common;

import jakarta.persistence.Column;
import jakarta.persistence.MappedSuperclass;
import lombok.Getter;
import lombok.Setter;

import java.util.UUID;

@MappedSuperclass
@Getter @Setter
public abstract class TenantScoped {
    @Column(name="tenant_id", nullable=false)
    private UUID tenantId;
}
