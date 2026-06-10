package com.app.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProductDatasetRepository extends JpaRepository<ProductDataset, UUID> {

    Optional<ProductDataset> findByDatasetId(String datasetId);

    List<ProductDataset> findAllByOrderByRegisteredAtDesc();
}
