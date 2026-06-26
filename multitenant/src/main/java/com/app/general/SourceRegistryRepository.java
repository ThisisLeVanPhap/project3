package com.app.general;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SourceRegistryRepository extends JpaRepository<SourceRegistry, UUID> {
    Optional<SourceRegistry> findBySourceCode(String sourceCode);

    List<SourceRegistry> findByEnabledTrueOrderBySourceCodeAsc();

    List<SourceRegistry> findAllByOrderByUpdatedAtDesc();

    boolean existsBySourceCode(String sourceCode);
}
