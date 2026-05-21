package com.app.adminui;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.forwardedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminUiControllerTest {

    private final MockMvc mvc = MockMvcBuilders.standaloneSetup(new AdminUiController()).build();

    @Test
    void forwardsTenantPurchaseRequestsView() throws Exception {
        mvc.perform(get("/tenant/purchase-requests"))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/tenant/purchase-requests/index.html"));
    }

    @Test
    void keepsExistingTenantLandingRoute() throws Exception {
        mvc.perform(get("/tenant"))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/tenant/index.html"));
    }

    @Test
    void keepsExistingAdminLandingRoute() throws Exception {
        mvc.perform(get("/admin"))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/admin/index.html"));
    }

    @Test
    void forwardsTenantChatRoute() throws Exception {
        mvc.perform(get("/chat"))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/chat/index.html"));
    }

    @Test
    void forwardsGeneralChatRoute() throws Exception {
        mvc.perform(get("/chat/general/"))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/chat/general/index.html"));
    }

    @Test
    void forwardsPriceCheckRouteThroughGeneralChatComponent() throws Exception {
        mvc.perform(get("/price-check"))
                .andExpect(status().isOk())
                .andExpect(forwardedUrl("/chat/general/index.html"));
    }
}
