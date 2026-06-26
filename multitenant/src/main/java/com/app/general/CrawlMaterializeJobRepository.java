package com.app.general;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface CrawlMaterializeJobRepository extends JpaRepository<CrawlMaterializeJob, UUID> {
    List<CrawlMaterializeJob> findTop50ByOrderByCreatedAtDesc();
}
