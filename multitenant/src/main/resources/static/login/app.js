document.addEventListener("DOMContentLoaded", () => {
    function $(id){ return document.getElementById(id); }

    const btnLogin = $("btn-login");
    const accountInput = $("name");
    const tenantCodeInput = $("tenantCode");
    const passwordInput = $("code");
    const msg = $("msg");
    const onboardingForm = $("onboarding-form");
    const onboardingMsg = $("onboardingMsg");
    const submitOnboardingBtn = $("btn-submit-onboarding");

    async function login(){
        const name = accountInput.value.trim();
        const tenantCode = tenantCodeInput.value.trim();
        const code = passwordInput.value.trim();

        if (!name || !code){
            msg.innerText = "Vui lòng nhập tài khoản và mật khẩu";
            return;
        }

        msg.innerText = "Đang đăng nhập...";
        btnLogin.disabled = true;

        try{
            const res = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, code, tenantCode })
            });

            const data = await res.json();

            if (!data.ok){
                msg.innerText = data.message || "Đăng nhập không thành công";
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
            msg.innerText = "Không kết nối được tới hệ thống";
        } finally {
            btnLogin.disabled = false;
        }
    }

    btnLogin.addEventListener("click", login);
    [accountInput, tenantCodeInput, passwordInput].forEach((input) => {
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                login();
            }
        });
    });

    $("btn-show-onboarding").addEventListener("click", () => {
        onboardingForm.classList.toggle("hidden");
    });

    async function submitOnboardingRequest(){
        const payload = {
            storeName: $("requestStoreName").value.trim(),
            contactName: $("requestContactName").value.trim(),
            email: $("requestEmail").value.trim(),
            phone: $("requestPhone").value.trim(),
            websiteUrl: $("requestWebsiteUrl").value.trim(),
            note: $("requestNote").value.trim()
        };

        if (!payload.storeName || !payload.contactName || !payload.email || !payload.phone) {
            onboardingMsg.innerText = "Vui lòng nhập tên cửa hàng, người liên hệ, email và số điện thoại";
            return;
        }

        onboardingMsg.innerText = "Đang gửi yêu cầu...";
        submitOnboardingBtn.disabled = true;
        try {
            const res = await fetch("/api/onboarding-requests", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const text = await res.text();
            let data = text;
            try { data = JSON.parse(text); } catch (e) {}
            if (!res.ok) {
                const detail = data?.message || (typeof data === "string" ? data.slice(0, 160).trim() : "");
                onboardingMsg.innerText = detail
                    ? `Không gửi được yêu cầu (${res.status}): ${detail}`
                    : `Không gửi được yêu cầu (${res.status})`;
                return;
            }

            onboardingMsg.innerText = `Đã gửi yêu cầu. Mã yêu cầu: ${data.id}. Quản trị hệ thống sẽ liên hệ sau khi xem xét.`;
            ["requestStoreName","requestContactName","requestEmail","requestPhone","requestWebsiteUrl","requestNote"]
                .forEach(id => { $(id).value = ""; });
        } catch (e) {
            console.error(e);
            onboardingMsg.innerText = "Không kết nối được tới hệ thống";
        } finally {
            submitOnboardingBtn.disabled = false;
        }
    }

    submitOnboardingBtn.addEventListener("click", submitOnboardingRequest);
});
