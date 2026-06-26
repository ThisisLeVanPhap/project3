package com.app.general;

import com.app.auth.SessionPrincipalAccessor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/admin/general")
@RequiredArgsConstructor
public class GeneralCatalogAdminController {

    private final GeneralCatalogAdminService generalCatalogAdminService;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping("/sources")
    public List<GeneralSourceResponse> listSources() {
        principalAccessor.requirePlatformAdmin();
        return generalCatalogAdminService.listSources();
    }

    @GetMapping("/import-runs")
    public List<GeneralImportRunResponse> listImportRuns() {
        principalAccessor.requirePlatformAdmin();
        return generalCatalogAdminService.listImportRuns();
    }

    @GetMapping("/products")
    public List<GeneralProductResponse> listProducts(
            @RequestParam(required = false) String sourceCode
    ) {
        principalAccessor.requirePlatformAdmin();
        return generalCatalogAdminService.listProducts(sourceCode);
    }
}
