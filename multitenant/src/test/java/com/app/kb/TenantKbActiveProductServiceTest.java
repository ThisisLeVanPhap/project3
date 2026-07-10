package com.app.kb;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TenantKbActiveProductServiceTest {

    @TempDir
    private Path tempDir;

    @Test
    void listReadsProductUrlsFromActiveKbProductsJsonl() throws Exception {
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        Path kbDir = tempDir.resolve("kb");
        Files.createDirectories(kbDir);
        Files.writeString(kbDir.resolve("products.jsonl"), """
                {"product_name":"Chair A","sku":"A-1","category":"Chair","source_url":"https://example.com/a","price":1200000}
                {"title":"Table B","metadata":{"sku":"B-2","category":"Table","source_url":"https://example.com/b"}}
                """);

        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                kbDir.toString(),
                TenantKbDirectorySource.ACTIVE_VERSION,
                versionId,
                "v1",
                null
        ));
        TenantKbActiveProductService service = new TenantKbActiveProductService(resolver, new ObjectMapper());

        TenantKbActiveProductService.ActiveProductsResponse response = service.list(tenantId, 0, 10, null);

        assertEquals(2, response.total());
        assertEquals(versionId, response.versionId());
        assertEquals("https://example.com/a", response.products().get(0).url());
        assertEquals("Chair A", response.products().get(0).name());
        assertEquals("A-1", response.products().get(0).sku());
        assertEquals("https://example.com/b", response.products().get(1).url());
    }

    @Test
    void listFiltersAndPaginatesProducts() throws Exception {
        UUID tenantId = UUID.randomUUID();
        Path kbDir = tempDir.resolve("filtered-kb");
        Files.createDirectories(kbDir);
        Files.writeString(kbDir.resolve("products.jsonl"), """
                {"product_name":"Blue Sofa","url":"https://example.com/sofa-blue"}
                {"product_name":"Oak Table","url":"https://example.com/oak-table"}
                {"product_name":"Green Sofa","url":"https://example.com/sofa-green"}
                """);

        TenantKbDirectoryResolver resolver = mock(TenantKbDirectoryResolver.class);
        when(resolver.resolve(tenantId)).thenReturn(new ResolvedTenantKbDirectory(
                tenantId,
                kbDir.toString(),
                TenantKbDirectorySource.ACTIVE_VERSION,
                UUID.randomUUID(),
                "v1",
                null
        ));
        TenantKbActiveProductService service = new TenantKbActiveProductService(resolver, new ObjectMapper());

        TenantKbActiveProductService.ActiveProductsResponse response = service.list(tenantId, 1, 1, "sofa");

        assertEquals(2, response.total());
        assertEquals(1, response.products().size());
        assertEquals("Green Sofa", response.products().get(0).name());
    }
}
