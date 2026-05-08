console.log("login app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM fully loaded");

    function $(id){ return document.getElementById(id); }

    const btnTenant = $("btn-tenant");
    const btnAdmin  = $("btn-admin");

    console.log("Buttons:", btnTenant, btnAdmin);

    async function login(path){
        console.log("Login clicked:", path);

        const name = $("name").value.trim();
        const code = $("code").value.trim();

        if (!name || !code){
            $("msg").innerText = "Please enter name and password";
            return;
        }

        $("msg").innerText = "Logging in...";

        try{
            const res = await fetch(`/api/login/${path}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, code })
            });

            const data = await res.json();
            console.log("Login response:", data);

            if (!data.ok){
                $("msg").innerText = data.message || "Login failed";
                return;
            }

            if (data.role === "PLATFORM_ADMIN"){
                localStorage.removeItem("tenant_id");
                localStorage.removeItem("tenant_name");
                window.location.href = "/admin";
            } else {
                localStorage.setItem("tenant_id", data.tenantId || "");
                localStorage.setItem("tenant_name", data.displayName || "");
                window.location.href =
                    `/tenant?tid=${encodeURIComponent(data.tenantId || "")}&name=${encodeURIComponent(data.displayName || "")}`;
            }

        } catch (e){
            console.error(e);
            $("msg").innerText = "Network error";
        }
    }

    btnTenant.addEventListener("click", () => login("tenant"));
    btnAdmin.addEventListener("click",  () => login("admin"));
});
