package com.app.general;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
public class SourceRegistryService {

    private static final Logger log = LoggerFactory.getLogger(SourceRegistryService.class);
    private static final Set<String> VALID_VISIBILITY = Set.of("GLOBAL_PUBLIC", "TENANT_BOUND", "PRIVATE", "ADMIN_ONLY");
    private static final Set<String> PRIVATE_PREFIXES = Set.of(
            "127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
            "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
            "0.", "169.254.", "::1", "fc00:", "fd00:", "fe80:");

    private final SourceRegistryRepository repository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SourceRegistryService(SourceRegistryRepository repository) {
        this.repository = repository;
    }

    public SourceRegistryResponse create(SourceRegistryRequest req) {
        validateRequest(req, false);
        if (repository.existsBySourceCode(req.sourceCode().trim().toLowerCase())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Source code already exists: " + req.sourceCode());
        }
        SourceRegistry entity = mapToEntity(req, new SourceRegistry());
        repository.save(entity);
        return SourceRegistryResponse.from(entity);
    }

    public SourceRegistryResponse update(UUID id, SourceRegistryRequest req) {
        SourceRegistry entity = repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Source not found"));
        validateRequest(req, true);
        if (!entity.getSourceCode().equalsIgnoreCase(req.sourceCode().trim())
                && repository.existsBySourceCode(req.sourceCode().trim().toLowerCase())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Source code already exists: " + req.sourceCode());
        }
        mapToEntity(req, entity);
        repository.save(entity);
        return SourceRegistryResponse.from(entity);
    }

    public SourceRegistryResponse get(UUID id) {
        SourceRegistry entity = repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Source not found"));
        return SourceRegistryResponse.from(entity);
    }

    public SourceRegistryResponse getByCode(String sourceCode) {
        SourceRegistry entity = repository.findBySourceCode(sourceCode.trim().toLowerCase())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Source not found: " + sourceCode));
        return SourceRegistryResponse.from(entity);
    }

    public List<SourceRegistryResponse> list() {
        return repository.findAllByOrderByUpdatedAtDesc().stream()
                .map(SourceRegistryResponse::from)
                .toList();
    }

    public List<SourceRegistryResponse> listEnabled() {
        return repository.findByEnabledTrueOrderBySourceCodeAsc().stream()
                .map(SourceRegistryResponse::from)
                .toList();
    }

    public SourceRegistryResponse setEnabled(UUID id, boolean enabled) {
        SourceRegistry entity = repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Source not found"));
        entity.setEnabled(enabled);
        repository.save(entity);
        return SourceRegistryResponse.from(entity);
    }

    public void delete(UUID id) {
        if (!repository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Source not found");
        }
        repository.deleteById(id);
    }

    private void validateRequest(SourceRegistryRequest req, boolean isUpdate) {
        if (req.sourceCode() == null || req.sourceCode().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sourceCode is required");
        }
        String vis = req.visibility() != null ? req.visibility().trim().toUpperCase() : "TENANT_BOUND";
        if (!VALID_VISIBILITY.contains(vis)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid visibility: " + vis);
        }
        if ("TENANT_BOUND".equals(vis) && (req.ownerTenantId() == null || req.ownerTenantId().isBlank())) {
            log.warn("Source {} set to TENANT_BOUND without ownerTenantId — source will not be accessible via tenant_sales", req.sourceCode());
        }
        checkPrivateUrl("rootUrl", req.rootUrl());
        checkPrivateUrl("sitemapUrl", req.sitemapUrl());
    }

    private String toJson(Object value) {
        try { return objectMapper.writeValueAsString(value); }
        catch (JsonProcessingException e) { return null; }
    }

    private void checkPrivateUrl(String fieldName, String url) {
        if (url == null || url.isBlank()) return;
        try {
            URI uri = new URI(url.trim());
            String scheme = uri.getScheme();
            if (scheme != null && !scheme.equalsIgnoreCase("http") && !scheme.equalsIgnoreCase("https")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        fieldName + " must use http or https scheme: " + url);
            }
            String host = uri.getHost();
            if (host == null) host = url.trim().toLowerCase();
            else host = host.toLowerCase();
            for (String prefix : PRIVATE_PREFIXES) {
                if (host.startsWith(prefix)) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            fieldName + " URL resolves to a private/loopback address: " + url);
                }
            }
            if (host.equals("postgres") || host.equals("chatbot-api") || host.endsWith(".internal")
                    || host.endsWith(".local") || host.equals("localhost") || host.equals("host.docker.internal")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        fieldName + " URL resolves to an internal address: " + url);
            }
        } catch (ResponseStatusException e) { throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    fieldName + " URL is invalid or malformed: " + url);
        }
    }

    private SourceRegistry mapToEntity(SourceRegistryRequest req, SourceRegistry entity) {
        entity.setSourceCode(req.sourceCode().trim().toLowerCase());
        entity.setSourceName(req.sourceName() != null ? req.sourceName().trim() : null);
        entity.setRootUrl(req.rootUrl());
        entity.setSitemapUrl(req.sitemapUrl());
        if (req.rootUrl() != null) {
            try { entity.setDomain(new URI(req.rootUrl()).getHost()); } catch (Exception ignored) {}
        }
        entity.setVisibility(req.visibility() != null ? req.visibility().trim().toUpperCase() : "TENANT_BOUND");
        if (req.ownerTenantId() != null && !req.ownerTenantId().isBlank()) {
            entity.setOwnerTenantId(UUID.fromString(req.ownerTenantId().trim()));
        } else {
            entity.setOwnerTenantId(null);
        }
        if (req.productUrlPatterns() != null) entity.setProductUrlPatterns(toJson(req.productUrlPatterns()));
        if (req.excludePatterns() != null) entity.setExcludePatterns(toJson(req.excludePatterns()));
        if (req.notes() != null) entity.setNotes(req.notes());
        entity.setEnabled(req.enabled() == null || req.enabled());
        return entity;
    }
}
