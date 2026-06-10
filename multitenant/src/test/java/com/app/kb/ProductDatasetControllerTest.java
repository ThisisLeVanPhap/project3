package com.app.kb;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.common.ApiExceptionHandler;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class ProductDatasetControllerTest {

    @Mock
    private ProductDatasetService productDatasetService;

    @Mock
    private SessionPrincipalAccessor principalAccessor;

    @Test
    void platformAdminCanListDatasets() throws Exception {
        UUID id = UUID.randomUUID();
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());
        when(productDatasetService.list()).thenReturn(List.of(response(id)));

        mvc().perform(get("/api/admin/product-datasets"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(id.toString()))
                .andExpect(jsonPath("$[0].dataset_id").value("gotrangtri-20260610"))
                .andExpect(jsonPath("$[0].status").value("REGISTERED"));

        verify(productDatasetService).list();
    }

    @Test
    void platformAdminCanRegisterDataset() throws Exception {
        UUID id = UUID.randomUUID();
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());
        when(productDatasetService.register(new ProductDatasetRegisterRequest("gotrangtri-20260610", "data_pipeline/output/datasets/gotrangtri-20260610", null, null, null)))
                .thenReturn(response(id));

        mvc().perform(post("/api/admin/product-datasets/register")
                        .contentType("application/json")
                        .content("""
                                {
                                  "dataset_id": "gotrangtri-20260610",
                                  "path": "data_pipeline/output/datasets/gotrangtri-20260610"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.dataset_id").value("gotrangtri-20260610"));
    }

    @Test
    void platformAdminCanAssignDataset() throws Exception {
        UUID id = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());
        when(productDatasetService.assignToTenant(id, new ProductDatasetAssignRequest("datn_demo_moho", null)))
                .thenReturn(new ProductDatasetAssignResponse(
                        true,
                        "gotrangtri-20260610",
                        tenantId,
                        "datn_demo_moho",
                        "chatbot/kb/datn_demo_moho/versions/dataset-1",
                        2,
                        versionId,
                        "dataset-1",
                        Instant.parse("2026-06-10T00:00:00Z"),
                        "Imported"
                ));

        mvc().perform(post("/api/admin/product-datasets/{id}/assign", id)
                        .contentType("application/json")
                        .content("""
                                {"tenant_code": "datn_demo_moho"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.tenant_code").value("datn_demo_moho"))
                .andExpect(jsonPath("$.kb_version_id").value(versionId.toString()));
    }

    @Test
    void platformAdminCanDeleteDatasetRecordOnly() throws Exception {
        UUID id = UUID.randomUUID();
        when(principalAccessor.requirePlatformAdmin()).thenReturn(platformAdmin());

        mvc().perform(delete("/api/admin/product-datasets/{id}", id))
                .andExpect(status().isNoContent());

        verify(productDatasetService).delete(id);
    }

    @Test
    void tenantMemberCannotUseProductDatasetAdminApi() throws Exception {
        doThrow(new ResponseStatusException(FORBIDDEN, "Insufficient role"))
                .when(principalAccessor).requirePlatformAdmin();

        mvc().perform(get("/api/admin/product-datasets"))
                .andExpect(status().isForbidden());
    }

    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new ProductDatasetController(productDatasetService, principalAccessor))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    private AppPrincipal platformAdmin() {
        return new AppPrincipal("platform-1", AppRole.PLATFORM_ADMIN, null, "Platform Admin", "admin@platform.local");
    }

    private ProductDatasetResponse response(UUID id) {
        return new ProductDatasetResponse(
                id,
                "gotrangtri-20260610",
                "gotrangtri",
                "https://gotrangtri.vn",
                null,
                "data_pipeline/output/datasets/gotrangtri-20260610",
                1,
                2,
                "hash",
                "data_pipeline/output/datasets/gotrangtri-20260610/manifest.json",
                Instant.parse("2026-06-10T00:00:00Z"),
                Instant.parse("2026-06-10T00:00:01Z"),
                ProductDatasetStatus.REGISTERED,
                null,
                null
        );
    }
}
