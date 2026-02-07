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

            if (path === "admin"){
                window.location.href = "/admin";
            } else {
                window.location.href =
                    `/tenant?tid=${encodeURIComponent(data.tenantId)}&name=${encodeURIComponent(data.tenantName)}`;
            }

        } catch (e){
            console.error(e);
            $("msg").innerText = "Network error";
        }
    }

    btnTenant.addEventListener("click", () => login("tenant"));
    btnAdmin.addEventListener("click",  () => login("admin"));
});
