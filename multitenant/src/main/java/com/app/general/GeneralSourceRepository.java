package com.app.general;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface GeneralSourceRepository extends JpaRepository<GeneralSource, UUID> {
    Optional<GeneralSource> findBySourceCode(String sourceCode);

    Optional<GeneralSource> findByArtifactId(UUID artifactId);

    Optional<GeneralSource> findBySourceTypeAndSourceRef(String sourceType, String sourceRef);

    List<GeneralSource> findTop100ByOrderByUpdatedAtDesc();
}
