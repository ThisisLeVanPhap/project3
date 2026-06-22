package com.app.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProductDatasetArtifactRepository extends JpaRepository<ProductDatasetArtifact, UUID> {
    List<ProductDatasetArtifact> findAllByDatasetRecordIdOrderByBuiltAtDescCreatedAtDesc(UUID datasetRecordId);

    Optional<ProductDatasetArtifact> findFirstByDatasetIdAndStatusOrderByBuiltAtDescCreatedAtDesc(String datasetId, ProductDatasetArtifactStatus status);

    Optional<ProductDatasetArtifact> findByDatasetIdAndBuildTag(String datasetId, String buildTag);
}
