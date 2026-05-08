package com.app.kb;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantKbSourceService {

    private static final String RAW_URLS_FILE = "raw_urls.txt";

    private final TenantRepository tenantRepository;

    public TenantKbSourceService(TenantRepository tenantRepository) {
        this.tenantRepository = tenantRepository;
    }

    public SourceUrlsResponse list(UUID tenantId) {
        return new SourceUrlsResponse(tenantId, readUrls(tenantId));
    }

    public SourceUrlsResponse add(UUID tenantId, SourceUrlRequest request) {
        String url = normalizeAndValidateUrl(request.url());
        LinkedHashSet<String> urls = new LinkedHashSet<>(readUrls(tenantId));
        urls.add(url);
        writeUrls(tenantId, urls);
        return new SourceUrlsResponse(tenantId, new ArrayList<>(urls));
    }

    public SourceUrlsResponse remove(UUID tenantId, SourceUrlRequest request) {
        String url = normalizeAndValidateUrl(request.url());
        LinkedHashSet<String> urls = new LinkedHashSet<>(readUrls(tenantId));
        urls.remove(url);
        writeUrls(tenantId, urls);
        return new SourceUrlsResponse(tenantId, new ArrayList<>(urls));
    }

    private List<String> readUrls(UUID tenantId) {
        Path rawUrlsPath = resolveRawUrlsPath(tenantId);
        if (!Files.exists(rawUrlsPath)) {
            return List.of();
        }
        try {
            return Files.readAllLines(rawUrlsPath, StandardCharsets.UTF_8).stream()
                    .map(String::trim)
                    .filter(line -> !line.isBlank())
                    .distinct()
                    .toList();
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read tenant KB source URLs");
        }
    }

    private void writeUrls(UUID tenantId, LinkedHashSet<String> urls) {
        Path rawUrlsPath = resolveRawUrlsPath(tenantId);
        try {
            Files.createDirectories(rawUrlsPath.getParent());
            String content = String.join(System.lineSeparator(), urls);
            if (!content.isBlank()) {
                content = content + System.lineSeparator();
            }
            Files.writeString(rawUrlsPath, content, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to write tenant KB source URLs");
        }
    }

    private Path resolveRawUrlsPath(UUID tenantId) {
        Tenant tenant = tenantRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Tenant not found"));
        String kbDir = tenant.getKbDir() == null ? "" : tenant.getKbDir().trim();
        if (kbDir.isBlank()) {
            throw new IllegalArgumentException("Tenant kb_dir is not configured");
        }
        Path kbDirPath = Path.of(kbDir).normalize();
        if (kbDirPath.getFileName() == null) {
            throw new IllegalArgumentException("Tenant kb_dir is invalid");
        }
        return kbDirPath.resolve(RAW_URLS_FILE).normalize();
    }

    private String normalizeAndValidateUrl(String rawUrl) {
        String url = rawUrl == null ? "" : rawUrl.trim();
        if (url.isBlank()) {
            throw new IllegalArgumentException("Missing url");
        }
        URI uri;
        try {
            uri = URI.create(url);
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("Invalid source URL");
        }
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
        if (!scheme.equals("http") && !scheme.equals("https")) {
            throw new IllegalArgumentException("Source URL must use http or https");
        }
        if (uri.getHost() == null || uri.getHost().isBlank()) {
            throw new IllegalArgumentException("Invalid source URL");
        }
        return url;
    }

    public record SourceUrlRequest(String url) {
    }

    public record SourceUrlsResponse(UUID tenantId, List<String> urls) {
    }
}
