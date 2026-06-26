package com.app.kb;

import com.app.auth.SessionPrincipalAccessor;
import com.app.general.CrawlAndMaterializeRequest;
import com.app.general.CrawlAndMaterializeService;
import com.app.general.CrawlMaterializeJobResponse;
import com.app.general.GeneralProductImportResponse;
import com.app.general.GeneralProductImportService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/product-datasets")
@RequiredArgsConstructor
public class ProductDatasetController {

    private final ProductDatasetService productDatasetService;
    private final GeneralProductImportService generalProductImportService;
    private final CrawlAndMaterializeService crawlAndMaterializeService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<ProductDatasetResponse> list() {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.list();
    }

    @PostMapping("/register")
    public ProductDatasetResponse register(@RequestBody ProductDatasetRegisterRequest request) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.register(request);
    }

    @GetMapping("/{id}")
    public ProductDatasetResponse get(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.get(id);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        productDatasetService.delete(id);
    }

    @GetMapping("/{id}/artifacts")
    public List<ProductDatasetArtifactResponse> listArtifacts(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.listArtifacts(id);
    }

    @PostMapping("/{id}/artifacts/build")
    public ProductDatasetArtifactResponse buildArtifact(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.buildArtifact(id);
    }

    @PostMapping("/artifacts/{artifactId}/import-general")
    public GeneralProductImportResponse importArtifactToGeneralProducts(@PathVariable UUID artifactId) {
        principalAccessor.requirePlatformAdmin();
        return generalProductImportService.importArtifact(artifactId);
    }

    @PostMapping("/crawl-materialize-jobs")
    public CrawlMaterializeJobResponse startCrawlMaterializeJob(@RequestBody CrawlAndMaterializeRequest request) {
        var principal = principalAccessor.requirePlatformAdmin();
        return crawlAndMaterializeService.startJob(request, principal.userId());
    }

    @GetMapping("/crawl-materialize-jobs")
    public List<CrawlMaterializeJobResponse> listCrawlMaterializeJobs() {
        principalAccessor.requirePlatformAdmin();
        return crawlAndMaterializeService.listJobs();
    }

    @GetMapping("/crawl-materialize-jobs/{jobId}")
    public CrawlMaterializeJobResponse getCrawlMaterializeJob(@PathVariable UUID jobId) {
        principalAccessor.requirePlatformAdmin();
        return crawlAndMaterializeService.getJob(jobId);
    }

    @PostMapping("/kb-bindings/bind")
    public TenantKbBindingResponse bindArtifact(@RequestBody TenantKbBindRequest request) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.bindArtifactToTenant(request);
    }

    @PostMapping("/kb-bindings/unbind")
    public TenantKbBindingResponse unbindTenantKb(@RequestBody TenantKbUnbindRequest request) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.unbindTenantKb(request);
    }

    @PostMapping("/{id}/assign")
    public ProductDatasetAssignResponse assign(
            @PathVariable UUID id,
            @RequestBody ProductDatasetAssignRequest request
    ) {
        principalAccessor.requirePlatformAdmin();
        return productDatasetService.assignToTenant(id, request);
    }
}
