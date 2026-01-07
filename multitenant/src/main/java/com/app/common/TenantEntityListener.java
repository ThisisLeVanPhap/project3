package com.app.common;

import com.app.tenant.TenantContext;
import jakarta.persistence.PrePersist;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
public class TenantEntityListener {
    @PrePersist
    public void prePersist(Object entity) {
        if (entity instanceof TenantScoped scoped && scoped.getTenantId() == null) {
            String tid = TenantContext.get();
            if (tid != null) scoped.setTenantId(UUID.fromString(tid));
        }
    }
}
