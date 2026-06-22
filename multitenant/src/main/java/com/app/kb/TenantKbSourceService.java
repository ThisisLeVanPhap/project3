package com.app.kb;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class TenantKbSourceService {

    private static final String RAW_URLS_FILE = "raw_urls.txt";
    private static final String SOURCE_MANIFEST_FILE = "source_manifest.json";

    private final TenantRepository tenantRepository;
    private final ObjectMapper objectMapper;

    public TenantKbSourceService(TenantRepository tenantRepository, ObjectMapper objectMapper) {
        this.tenantRepository = tenantRepository;
        this.objectMapper = objectMapper;
    }

    public SourceUrlsResponse list(UUID tenantId) {
        SourceManifest manifest = readManifest(tenantId);
        return new SourceUrlsResponse(tenantId, manifest.urls());
    }

    public SourceUrlsResponse add(UUID tenantId, SourceUrlRequest request) {
        String url = normalizeAndValidateUrl(request.url());
        SourceManifest current = readManifest(tenantId);
        LinkedHashSet<String> urls = new LinkedHashSet<>(current.urls());
        urls.add(url);
        SourceManifest next = current.withUrls(new ArrayList<>(urls));
        writeManifest(tenantId, next);
        syncLegacyRawUrls(tenantId, next.urls());
        return new SourceUrlsResponse(tenantId, next.urls());
    }

    public SourceUrlsResponse remove(UUID tenantId, SourceUrlRequest request) {
        String url = normalizeAndValidateUrl(request.url());
        SourceManifest current = readManifest(tenantId);
        LinkedHashSet<String> urls = new LinkedHashSet<>(current.urls());
        urls.remove(url);
        SourceManifest next = current.withUrls(new ArrayList<>(urls));
        writeManifest(tenantId, next);
        syncLegacyRawUrls(tenantId, next.urls());
        return new SourceUrlsResponse(tenantId, next.urls());
    }

    public SourceConfigResponse getConfig(UUID tenantId) {
        SourceManifest manifest = readManifest(tenantId);
        return new SourceConfigResponse(tenantId, manifest);
    }

    public SourceConfigResponse setSitemap(UUID tenantId, SitemapSourceRequest request) {
        String sitemapUrl = normalizeAndValidateUrl(request.sitemapUrl());
        String provider = blankToNull(request.provider());
        if (provider == null) {
            provider = inferProvider(sitemapUrl);
        }
        SourceManifest next = new SourceManifest(
                "SITEMAP",
                sitemapUrl,
                sitemapUrl,
                provider,
                List.of(),
                Instant.now()
        );
        writeManifest(tenantId, next);
        syncLegacyRawUrls(tenantId, List.of());
        return new SourceConfigResponse(tenantId, next);
    }

    public SourceManifest readManifest(UUID tenantId) {
        Path manifestPath = resolveKbDir(tenantId).resolve(SOURCE_MANIFEST_FILE).normalize();
        if (Files.exists(manifestPath)) {
            try {
                SourceManifest manifest = objectMapper.readValue(manifestPath.toFile(), SourceManifest.class);
                return normalizeManifest(manifest);
            } catch (IOException e) {
                throw new IllegalStateException("Failed to read tenant KB source manifest");
            }
        }
        return legacyManifest(tenantId);
    }

    public Path sourceManifestPath(UUID tenantId) {
        return resolveKbDir(tenantId).resolve(SOURCE_MANIFEST_FILE).normalize();
    }

    private SourceManifest legacyManifest(UUID tenantId) {
        List<String> urls = readLegacyUrls(tenantId);
        String sourceUrl = urls.isEmpty() ? null : urls.get(0);
        return new SourceManifest(
                "PRODUCT_URL_LIST",
                sourceUrl,
                null,
                inferProvider(sourceUrl),
                urls,
                null
        );
    }

    private SourceManifest normalizeManifest(SourceManifest manifest) {
        if (manifest == null) {
            return new SourceManifest("PRODUCT_URL_LIST", null, null, null, List.of(), null);
        }
        List<String> normalizedUrls = manifest.urls() == null
                ? List.of()
                : manifest.urls().stream()
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
        String mode = normalizeMode(manifest.mode(), normalizedUrls);
        String sourceUrl = blankToNull(manifest.sourceUrl());
        String sitemapUrl = blankToNull(manifest.sitemapUrl());
        String provider = blankToNull(manifest.provider());
        Instant updatedAt = manifest.updatedAt();
        return new SourceManifest(mode, sourceUrl, sitemapUrl, provider, normalizedUrls, updatedAt);
    }

    private String normalizeMode(String mode, List<String> urls) {
        String normalized = blankToNull(mode);
        if (normalized == null) {
            return urls.isEmpty() ? "PRODUCT_URL_LIST" : "PRODUCT_URL_LIST";
        }
        String upper = normalized.toUpperCase(Locale.ROOT);
        return switch (upper) {
            case "SITEMAP", "PRODUCT_URL_LIST" -> upper;
            default -> "PRODUCT_URL_LIST";
        };
    }

    private List<String> readLegacyUrls(UUID tenantId) {
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

    private void writeManifest(UUID tenantId, SourceManifest manifest) {
        Path manifestPath = sourceManifestPath(tenantId);
        try {
            Files.createDirectories(manifestPath.getParent());
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(
                    manifestPath.toFile(),
                    manifest.withUpdatedAt(Instant.now())
            );
        } catch (IOException e) {
            throw new IllegalStateException("Failed to write tenant KB source manifest");
        }
    }

    private void syncLegacyRawUrls(UUID tenantId, List<String> urls) {
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

    private Path resolveKbDir(UUID tenantId) {
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
        return kbDirPath;
    }

    private Path resolveRawUrlsPath(UUID tenantId) {
        return resolveKbDir(tenantId).resolve(RAW_URLS_FILE).normalize();
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

    private String inferProvider(String url) {
        if (url == null || url.isBlank()) {
            return null;
        }
        try {
            String host = URI.create(url).getHost();
            if (host == null || host.isBlank()) {
                return null;
            }
            String normalized = host.toLowerCase(Locale.ROOT);
            if (normalized.contains("gotrangtri.vn")) {
                return "gotrangtri";
            }
            return normalized;
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private String blankToNull(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isBlank() ? null : normalized;
    }

    public record SourceUrlRequest(String url) {
    }

    public record SitemapSourceRequest(String sitemapUrl, String provider) {
    }

    public record SourceUrlsResponse(UUID tenantId, List<String> urls) {
    }

    public record SourceConfigResponse(UUID tenantId, SourceManifest source) {
    }

    public record SourceManifest(
            String mode,
            String sourceUrl,
            String sitemapUrl,
            String provider,
            List<String> urls,
            Instant updatedAt
    ) {
        public SourceManifest withUrls(List<String> nextUrls) {
            String nextSourceUrl = sourceUrl;
            if ((nextSourceUrl == null || nextSourceUrl.isBlank()) && nextUrls != null && !nextUrls.isEmpty()) {
                nextSourceUrl = nextUrls.get(0);
            }
            String nextProvider = provider;
            if ((nextProvider == null || nextProvider.isBlank()) && nextSourceUrl != null && !nextSourceUrl.isBlank()) {
                nextProvider = URI.create(nextSourceUrl).getHost();
                if (nextProvider != null && nextProvider.contains("gotrangtri.vn")) {
                    nextProvider = "gotrangtri";
                }
            }
            return new SourceManifest("PRODUCT_URL_LIST", nextSourceUrl, sitemapUrl, nextProvider, List.copyOf(nextUrls), updatedAt);
        }

        public SourceManifest withUpdatedAt(Instant nextUpdatedAt) {
            return new SourceManifest(mode, sourceUrl, sitemapUrl, provider, urls == null ? List.of() : List.copyOf(urls), nextUpdatedAt);
        }
    }
}
