package com.app.tenants;

import jakarta.persistence.*;
import lombok.Getter; import lombok.Setter;
import java.util.UUID;

@Entity @Table(name="tenants")
@Getter @Setter
public class Tenant {
    @Id private UUID id;
    @Column(unique=true, nullable=false) private String code;
    private String name;
    @Column(unique=true, nullable=false) private String apiKey;
    private String status;
    @Column(name = "kb_dir")
    private String kbDir;
}
