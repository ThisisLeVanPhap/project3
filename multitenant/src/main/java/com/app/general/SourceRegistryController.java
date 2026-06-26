package com.app.general;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/source-registry")
public class SourceRegistryController {

    private final SourceRegistryService service;
    private final SessionPrincipalAccessor principalAccessor;

    public SourceRegistryController(SourceRegistryService service, SessionPrincipalAccessor principalAccessor) {
        this.service = service;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<SourceRegistryResponse> list() {
        principalAccessor.requirePlatformAdmin();
        return service.list();
    }

    @GetMapping("/enabled")
    public List<SourceRegistryResponse> listEnabled() {
        principalAccessor.requirePlatformAdmin();
        return service.listEnabled();
    }

    @GetMapping("/{id}")
    public SourceRegistryResponse get(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        return service.get(id);
    }

    @GetMapping("/by-code/{sourceCode}")
    public SourceRegistryResponse getByCode(@PathVariable String sourceCode) {
        principalAccessor.requirePlatformAdmin();
        return service.getByCode(sourceCode);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SourceRegistryResponse create(@RequestBody SourceRegistryRequest request) {
        principalAccessor.requirePlatformAdmin();
        return service.create(request);
    }

    @PutMapping("/{id}")
    public SourceRegistryResponse update(@PathVariable UUID id, @RequestBody SourceRegistryRequest request) {
        principalAccessor.requirePlatformAdmin();
        return service.update(id, request);
    }

    @PatchMapping("/{id}/enabled")
    public SourceRegistryResponse setEnabled(@PathVariable UUID id, @RequestBody EnableRequest body) {
        principalAccessor.requirePlatformAdmin();
        return service.setEnabled(id, body.enabled());
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        principalAccessor.requirePlatformAdmin();
        service.delete(id);
    }

    record EnableRequest(boolean enabled) {}
}
