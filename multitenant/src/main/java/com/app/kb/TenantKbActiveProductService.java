package com.app.kb;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantKbActiveProductService {

    private static final int MAX_LIMIT = 200;

    private final TenantKbDirectoryResolver directoryResolver;
    private final ObjectMapper objectMapper;

    public TenantKbActiveProductService(TenantKbDirectoryResolver directoryResolver, ObjectMapper objectMapper) {
        this.directoryResolver = directoryResolver;
        this.objectMapper = objectMapper;
    }

    public ActiveProductsResponse list(UUID tenantId, int offset, int limit, String query) {
        ResolvedTenantKbDirectory resolved = directoryResolver.resolve(tenantId);
        Path kbDir = Path.of(resolved.kbDir()).normalize();
        Path productFile = productFile(kbDir);
        if (productFile == null) {
            return new ActiveProductsResponse(
                    tenantId,
                    kbDir.toString(),
                    resolved.source().name(),
                    resolved.versionId(),
                    resolved.versionTag(),
                    0,
                    normalizeLimit(limit),
                    0,
                    List.of()
            );
        }

        int normalizedOffset = Math.max(0, offset);
        int normalizedLimit = normalizeLimit(limit);
        String normalizedQuery = normalizeQuery(query);
        List<ActiveProductItem> products = new ArrayList<>();
        int matched = 0;

        try (BufferedReader reader = Files.newBufferedReader(productFile, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                ActiveProductItem item = parseProduct(line);
                if (item == null || !matches(item, normalizedQuery)) {
                    continue;
                }
                if (matched >= normalizedOffset && products.size() < normalizedLimit) {
                    products.add(item);
                }
                matched++;
            }
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Unable to read active KB products");
        }

        return new ActiveProductsResponse(
                tenantId,
                kbDir.toString(),
                resolved.source().name(),
                resolved.versionId(),
                resolved.versionTag(),
                normalizedOffset,
                normalizedLimit,
                matched,
                products
        );
    }

    private Path productFile(Path kbDir) {
        Path products = kbDir.resolve("products.jsonl").normalize();
        if (Files.isRegularFile(products)) {
            return products;
        }
        Path chunks = kbDir.resolve("chunks.jsonl").normalize();
        if (Files.isRegularFile(chunks)) {
            return chunks;
        }
        return null;
    }

    private ActiveProductItem parseProduct(String line) {
        try {
            JsonNode root = objectMapper.readTree(line);
            JsonNode metadata = root.path("metadata");
            String url = firstText(
                    root.path("url"),
                    root.path("source_url"),
                    root.path("source"),
                    root.path("canonical_url"),
                    metadata.path("source_url"),
                    metadata.path("canonical_url")
            );
            String name = firstText(
                    root.path("product_name"),
                    root.path("title"),
                    metadata.path("product_name")
            );
            String sku = firstText(root.path("sku"), metadata.path("sku"));
            String category = firstText(root.path("category"), metadata.path("category"));
            String price = priceText(firstText(root.path("price"), metadata.path("price")));
            if (url == null && name == null) {
                return null;
            }
            return new ActiveProductItem(url, name, sku, category, price);
        } catch (IOException ignored) {
            return null;
        }
    }

    private boolean matches(ActiveProductItem item, String query) {
        if (query == null) {
            return true;
        }
        return contains(item.url(), query)
                || contains(item.name(), query)
                || contains(item.sku(), query)
                || contains(item.category(), query);
    }

    private boolean contains(String value, String query) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(query);
    }

    private String normalizeQuery(String query) {
        if (query == null || query.trim().isBlank()) {
            return null;
        }
        return query.trim().toLowerCase(Locale.ROOT);
    }

    private int normalizeLimit(int limit) {
        if (limit <= 0) {
            return 50;
        }
        return Math.min(limit, MAX_LIMIT);
    }

    private String firstText(JsonNode... nodes) {
        for (JsonNode node : nodes) {
            if (node == null || node.isMissingNode() || node.isNull()) {
                continue;
            }
            String value = node.asText();
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return null;
    }

    private String priceText(String value) {
        if (value == null || value.isBlank() || "null".equalsIgnoreCase(value)) {
            return null;
        }
        return value;
    }

    public record ActiveProductsResponse(
            UUID tenantId,
            String kbDir,
            String source,
            UUID versionId,
            String versionTag,
            int offset,
            int limit,
            int total,
            List<ActiveProductItem> products
    ) {
    }

    public record ActiveProductItem(
            String url,
            String name,
            String sku,
            String category,
            String price
    ) {
    }
}
