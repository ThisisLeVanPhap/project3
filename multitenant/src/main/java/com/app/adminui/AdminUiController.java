package com.app.adminui;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class AdminUiController {

    @GetMapping({"/login", "/login/"})
    public String login() {
        return "forward:/login/index.html";
    }

    @GetMapping({"/admin", "/admin/"})
    public String admin() {
        return "redirect:/admin/index.html";
    }

    @GetMapping({"/tenant", "/tenant/"})
    public String tenant() { return "forward:/tenant/index.html"; }

    @GetMapping({"/tenant/purchase-requests", "/tenant/purchase-requests/"})
    public String tenantPurchaseRequests() {
        return "forward:/tenant/purchase-requests/index.html";
    }
}
