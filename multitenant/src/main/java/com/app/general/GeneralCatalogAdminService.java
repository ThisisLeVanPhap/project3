package com.app.general;

import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GeneralCatalogAdminService {

    private final GeneralSourceRepository generalSourceRepository;
    private final GeneralImportRunRepository generalImportRunRepository;
    private final GeneralProductRepository generalProductRepository;

    public GeneralCatalogAdminService(
            GeneralSourceRepository generalSourceRepository,
            GeneralImportRunRepository generalImportRunRepository,
            GeneralProductRepository generalProductRepository
    ) {
        this.generalSourceRepository = generalSourceRepository;
        this.generalImportRunRepository = generalImportRunRepository;
        this.generalProductRepository = generalProductRepository;
    }

    public List<GeneralSourceResponse> listSources() {
        return generalSourceRepository.findTop100ByOrderByUpdatedAtDesc().stream()
                .map(GeneralSourceResponse::from)
                .toList();
    }

    public List<GeneralImportRunResponse> listImportRuns() {
        return generalImportRunRepository.findTop100ByOrderByStartedAtDesc().stream()
                .map(GeneralImportRunResponse::from)
                .toList();
    }

    public List<GeneralProductResponse> listProducts(String sourceCode) {
        List<GeneralProduct> products = sourceCode == null || sourceCode.isBlank()
                ? generalProductRepository.findTop100ByOrderByUpdatedAtDesc()
                : generalProductRepository.findTop100BySourceCodeOrderByUpdatedAtDesc(sourceCode.trim());
        return products.stream().map(GeneralProductResponse::from).toList();
    }
}
