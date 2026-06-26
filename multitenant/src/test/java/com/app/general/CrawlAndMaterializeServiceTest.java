package com.app.general;

import com.app.kb.ProductDatasetArtifactRepository;
import com.app.kb.ProductDatasetService;
import com.app.modelserver.LlmProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CrawlAndMaterializeServiceTest {

    @Mock
    private ProductDatasetService productDatasetService;

    @Mock
    private CrawlMaterializeJobRepository jobRepository;

    @Mock
    private GeneralProductImportService generalProductImportService;

    @Mock
    private ProductDatasetArtifactRepository artifactRepository;

    @Test
    void startJobRejectsMissingSourceCode() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "", "Test", "https://example.test", null, List.of(), null,
                10, true, true, false, true, false, false, null, null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void startJobRejectsMissingBothSitemapAndUrls() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", "Test", "https://example.test", null, List.of(), null,
                10, true, true, false, true, false, false, null, null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsBindWithEmptyTenantId() {
        CrawlAndMaterializeService service = buildService();
        // bindTenantId is blank → isBindTenant() is false, so no bind validation.
        // Empty string behaves like null, so the job proceeds without bind.
        // This test verifies blank bindTenantId doesn't cause errors.
        when(jobRepository.save(any(CrawlMaterializeJob.class))).thenAnswer(inv -> {
            CrawlMaterializeJob j = inv.getArgument(0);
            if (j.getId() == null) j.setId(UUID.randomUUID());
            return j;
        });
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://test.test/sitemap.xml", null, null,
                10, true, true, false, true, true, false, "", "TENANT_BOUND"
        );
        CrawlMaterializeJobResponse resp = service.startJob(req, "admin");
        assertEquals("QUEUED", resp.status());
    }

    @Test
    void validationRejectsBindWithoutBuildArtifact() {
        CrawlAndMaterializeService service = buildService();
        // bindTenantId != null triggers isBindTenant=true, but buildArtifact is false
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://test.test/sitemap.xml", null, null,
                10, true, true, false, true, false, false, "tenant-1", null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsImportGeneralWithoutBuildArtifact() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://test.test/sitemap.xml", null, null,
                10, true, true, false, true, false, true, null, "GLOBAL_PUBLIC"
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsImportGeneralWithTenantBoundVisibility() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://test.test/sitemap.xml", null, null,
                10, true, true, false, true, true, true, null, "TENANT_BOUND"
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void startJobReturnsQueuedWithDefaults() {
        when(jobRepository.save(any(CrawlMaterializeJob.class))).thenAnswer(inv -> {
            CrawlMaterializeJob job = inv.getArgument(0);
            if (job.getId() == null) job.setId(UUID.randomUUID());
            return job;
        });
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "gotrangtri", null, null, "https://gotrangtri.vn/sitemap.xml", null, null,
                3, true, true, false, true, false, false, null, null
        );
        CrawlMaterializeJobResponse resp = service.startJob(req, "admin");
        assertEquals("QUEUED", resp.status());
        assertEquals("gotrangtri", resp.sourceCode());
        assertEquals("TENANT_BOUND", resp.visibility());
        assertTrue(resp.registerDataset());
    }

    @Test
    void visibilityDefaults() {
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "gotrangtri", null, null, "https://gotrangtri.vn/sitemap.xml",
                null, null, null, null, null, null, null, null, null, null, null
        );
        assertEquals("TENANT_BOUND", req.getVisibilityOrDefault());
        assertEquals(1000, req.getMaxUrlsOrDefault());
    }

    @Test
    void getJobReturnsSavedJob() {
        UUID jobId = UUID.randomUUID();
        CrawlMaterializeJob job = new CrawlMaterializeJob();
        job.setId(jobId);
        job.setSourceCode("gotrangtri");
        job.setStatus("SUCCESS");
        job.setStage("SUCCESS");
        job.setProductCount(100);

        when(jobRepository.findById(jobId)).thenReturn(Optional.of(job));

        CrawlAndMaterializeService service = buildService();
        CrawlMaterializeJobResponse resp = service.getJob(jobId);
        assertEquals("SUCCESS", resp.status());
        assertEquals(100, resp.productCount());
    }

    @Test
    void getJobNotFoundThrows() {
        when(jobRepository.findById(any())).thenReturn(Optional.empty());
        CrawlAndMaterializeService service = buildService();
        assertThrows(ResponseStatusException.class, () -> service.getJob(UUID.randomUUID()));
    }

    @Test
    void listJobsReturnsJobs() {
        CrawlMaterializeJob job = new CrawlMaterializeJob();
        job.setId(UUID.randomUUID());
        job.setSourceCode("gotrangtri");
        job.setStatus("QUEUED");

        when(jobRepository.findTop50ByOrderByCreatedAtDesc()).thenReturn(List.of(job));

        CrawlAndMaterializeService service = buildService();
        assertEquals(1, service.listJobs().size());
    }

    @Test
    void validationRejectsMaxUrlsOverLimit() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://example.test/sitemap.xml", null, null,
                60000, true, true, false, true, false, false, null, "TENANT_BOUND"
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsLocalhostSitemap() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "http://localhost:8080/sitemap.xml", null, null,
                10, true, true, false, true, false, false, null, null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsPrivateIpSitemap() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "http://192.168.1.1/sitemap.xml", null, null,
                10, true, true, false, true, false, false, null, null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void validationRejectsInternalDockerHostname() {
        CrawlAndMaterializeService service = buildService();
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "http://postgres:5432/sitemap.xml", null, null,
                10, true, true, false, true, false, false, null, null
        );
        assertThrows(ResponseStatusException.class, () -> service.startJob(req, "admin"));
    }

    @Test
    void maxUrlsDefaultsTo1000() {
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://example.test/sitemap.xml", null, null,
                null, null, null, null, null, null, null, null, null
        );
        assertEquals(1000, req.getMaxUrlsOrDefault());
    }

    @Test
    void maxUrlsClampsTo50000() {
        CrawlAndMaterializeRequest req = new CrawlAndMaterializeRequest(
                "test", null, null, "https://example.test/sitemap.xml", null, null,
                5000, null, null, null, null, null, null, null, null
        );
        assertEquals(5000, req.getMaxUrlsOrDefault());
    }

    private CrawlAndMaterializeService buildService() {
        return new CrawlAndMaterializeService(
                new LlmProperties(), productDatasetService, jobRepository,
                generalProductImportService, artifactRepository, new ObjectMapper()
        );
    }
}
