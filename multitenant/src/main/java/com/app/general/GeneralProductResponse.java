package com.app.general;

import java.math.BigDecimal;
import java.util.UUID;

public record GeneralProductResponse(
        UUID id,
        UUID generalSourceId,
        String sourceCode,
        String sourceDomain,
        String externalProductId,
        String name,
        String category,
        String productType,
        BigDecimal price,
        BigDecimal originalPrice,
        String currency,
        String brand,
        String material,
        String sourceUrl,
        String visibility,
        String status
) {
    public static GeneralProductResponse from(GeneralProduct product) {
        return new GeneralProductResponse(
                product.getId(),
                product.getGeneralSourceId(),
                product.getSourceCode(),
                product.getSourceDomain(),
                product.getExternalProductId(),
                product.getName(),
                product.getCategory(),
                product.getProductType(),
                product.getPrice(),
                product.getOriginalPrice(),
                product.getCurrency(),
                product.getBrand(),
                product.getMaterial(),
                product.getSourceUrl(),
                product.getVisibility(),
                product.getStatus()
        );
    }
}
