package com.app.general;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface GeneralProductRepository extends JpaRepository<GeneralProduct, UUID> {
    Optional<GeneralProduct> findByArtifactIdAndProductId(UUID artifactId, String productId);

    Optional<GeneralProduct> findByArtifactIdAndContentHash(UUID artifactId, String contentHash);

    Optional<GeneralProduct> findByGeneralSourceIdAndExternalProductId(UUID generalSourceId, String externalProductId);

    Optional<GeneralProduct> findByGeneralSourceIdAndContentHash(UUID generalSourceId, String contentHash);

    List<GeneralProduct> findTop100ByOrderByUpdatedAtDesc();

    List<GeneralProduct> findTop100BySourceCodeOrderByUpdatedAtDesc(String sourceCode);

    long countByArtifactId(UUID artifactId);

    long countByGeneralSourceId(UUID generalSourceId);
}
