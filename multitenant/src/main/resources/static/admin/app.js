function $(id){ return document.getElementById(id); }

async function setTelegramWebhook(botToken, fullWebhookUrl){
    const url = "https://api.telegram.org/bot" + botToken + "/setWebhook";
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: fullWebhookUrl })
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch(e) {}
    return { ok: res.ok, status: res.status, data };
}

const cfgKeys = {
    apiBase: "adminui.apiBase",
    basicAuth: "adminui.basicAuth",
    apiKey: "adminui.apiKey",
    tenantId: "adminui.tenantId"
};

const state = {
    tenants: [],
    bots: [],
    selectedTenant: null, // {id, name, apiKey, code}
    selectedBot: null     // {id, name, channel, ...}
};

function showMsg(id, text, ms=1200){
    $(id).innerText = text || "";
    if(text) setTimeout(()=> $(id).innerText="", ms);
}

function loadCfg(){
    $("apiBase").value = localStorage.getItem(cfgKeys.apiBase) || "http://localhost:8080";
    $("basicAuth").value = localStorage.getItem(cfgKeys.basicAuth) || "";
    $("apiKey").value = localStorage.getItem(cfgKeys.apiKey) || "";
    $("tenantId").value = localStorage.getItem(cfgKeys.tenantId) || "";
}

function saveCfg(){
    localStorage.setItem(cfgKeys.apiBase, $("apiBase").value.trim());
    localStorage.setItem(cfgKeys.basicAuth, $("basicAuth").value.trim());
    localStorage.setItem(cfgKeys.apiKey, $("apiKey").value.trim());
    localStorage.setItem(cfgKeys.tenantId, $("tenantId").value.trim());
    showMsg("cfgMsg", "Saved");
}

function baseUrl(){
    return $("apiBase").value.trim().replace(/\/+$/,"");
}

function headersJson(){
    const h = { "Content-Type": "application/json" };
    const auth = $("basicAuth").value.trim();
    const apiKey = $("apiKey").value.trim();
    const tenantId = $("tenantId").value.trim();

    if(auth) h["Authorization"] = auth;

    // TenantResolver: ưu tiên apiKey, nếu không có thì tenantId
    if(apiKey) h["X-API-Key"] = apiKey;
    else if(tenantId) h["X-Tenant-Id"] = tenantId;

    return h;
}

async function req(method, path, body, opts = { tenantHeaders: true }){
    const url = baseUrl() + path;
    const headers = { "Content-Type": "application/json" };

    // tenant headers ON/OFF
    if(opts.tenantHeaders !== false){
        Object.assign(headers, headersJson());
    } else {
        // chỉ giữ Authorization nếu có
        const auth = $("basicAuth").value.trim();
        if(auth) headers["Authorization"] = auth;
    }

    const opt = { method, headers };
    if(body !== undefined) opt.body = JSON.stringify(body);

    const res = await fetch(url, opt);
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch(e) {}
    return { ok: res.ok, status: res.status, data };
}

/* ---------------- Tabs ---------------- */
function setTab(name){
    document.querySelectorAll(".tab").forEach(b=>{
        b.classList.toggle("active", b.dataset.tab === name);
    });
    ["tenants","chatbots","bindings","monitor"].forEach(t=>{
        $("tab-"+t).classList.toggle("hidden", t !== name);
    });
}
document.querySelectorAll(".tab").forEach(b=>{
    b.addEventListener("click", ()=> setTab(b.dataset.tab));
});

/* ---------------- Tenant select helpers ---------------- */
function renderTenantSelect(selectId){
    const sel = $(selectId);
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "— chọn tenant —";
    sel.appendChild(opt0);

    for(const t of state.tenants){
        const op = document.createElement("option");
        op.value = t.id;
        op.textContent = `${t.name} (${t.code || "no_code"})`;
        sel.appendChild(op);
    }

    // auto select current
    if(state.selectedTenant){
        sel.value = state.selectedTenant.id;
    }
}

function applyTenantById(tenantId){
    const t = state.tenants.find(x => x.id === tenantId);
    if(!t){
        state.selectedTenant = null;
        $("selectedTenantName").innerText = "—";
        return;
    }
    state.selectedTenant = t;

    // auto-fill headers (ưu tiên apiKey)
    $("apiKey").value = t.apiKey || "";
    $("tenantId").value = t.id;

    $("selectedTenantName").innerText = t.name || t.id;
    saveCfg();
}

/* ---------------- Bot select helpers ---------------- */
function renderBotSelect(){
    const sel = $("botSelect");
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "— chọn chatbot —";
    sel.appendChild(opt0);

    for(const b of state.bots){
        const op = document.createElement("option");
        op.value = b.id;
        // Hiện NAME + CHANNEL (đúng ý bạn)
        op.textContent = `${b.name}  [${b.channel}]`;
        sel.appendChild(op);
    }

    // auto select first if none
    if(state.bots.length && !state.selectedBot){
        sel.value = state.bots[0].id;
        state.selectedBot = state.bots[0];
        $("selectedBotChannel").innerText = state.selectedBot.channel || "—";
    }
}

function setSelectedBot(botId){
    const b = state.bots.find(x => x.id === botId);
    state.selectedBot = b || null;
    $("selectedBotChannel").innerText = b?.channel || "—";
}

/* ---------------- Health ---------------- */
$("pingHealth").addEventListener("click", async ()=>{
    $("healthMsg").innerText = "";
    const r = await req("GET", "/actuator/health", undefined, { tenantHeaders:false });
    $("healthMsg").innerText = r.ok ? "health: OK" : `health: FAIL (${r.status})`;
});

/* ---------------- Tenants ---------------- */
$("createTenant").addEventListener("click", async ()=>{
    $("tenantsMsg").innerText = "";
    const code = $("tenantCode").value.trim();
    const name = $("tenantName").value.trim();
    if(!code || !name){
        $("tenantsMsg").innerText = "Thiếu code hoặc name";
        return;
    }

    // Endpoint đúng theo code bạn gửi: /api/admin/tenants (WebConfig exclude)
    const r = await req("POST", "/api/admin/tenants", { code, name }, { tenantHeaders:false });
    $("tenantsOut").innerText = JSON.stringify(r, null, 2);

    // refresh list ngay để chọn tenant
    await loadTenants(true);
});

async function loadTenants(autoPickFirst=false){
    const r = await req("GET", "/api/admin/tenants", undefined, { tenantHeaders:false });
    $("tenantsOut").innerText = JSON.stringify(r, null, 2);

    if(r.ok && Array.isArray(r.data)){
        state.tenants = r.data;
        renderTenantSelect("tenantSelectBots");
        renderTenantSelect("tenantSelectBindings");

        if(autoPickFirst && state.tenants.length){
            applyTenantById(state.tenants[0].id);
            $("tenantSelectBots").value = state.tenants[0].id;
            $("tenantSelectBindings").value = state.tenants[0].id;
        }
    }
}
$("loadTenants").addEventListener("click", ()=> loadTenants(false));
$("clearTenantsOut").addEventListener("click", ()=> $("tenantsOut").innerText = "");

/* ---------------- Chatbots ---------------- */
$("useTenantBots").addEventListener("click", async ()=>{
    const id = $("tenantSelectBots").value;
    if(!id){ showMsg("botsMsg", "Chọn tenant trước"); return; }
    applyTenantById(id);
    showMsg("botsMsg", "Tenant applied");
});

$("createBot").addEventListener("click", async ()=>{
    $("botsMsg").innerText = "";

    if(!state.selectedTenant){
        $("botsMsg").innerText = "Chưa chọn tenant";
        return;
    }

    const name = $("botName").value.trim();
    const channel = $("botChannel").value.trim();
    const personaJson = ($("botPersona").value || "").trim();

    if(!name || !channel){
        $("botsMsg").innerText = "Thiếu bot name hoặc channel";
        return;
    }

    const payload = { name, channel, personaJson: personaJson || "{}" };
    const r = await req("POST", "/api/chatbots", payload);
    $("botsOut").innerText = JSON.stringify(r, null, 2);

    // refresh bots list after create
    await loadBots(false);
});

async function loadBots(silent=false){
    $("botsMsg").innerText = "";
    if(!state.selectedTenant){
        if(!silent) $("botsMsg").innerText = "Chưa chọn tenant (Use tenant)";
        return;
    }

    const r = await req("GET", "/api/chatbots");
    $("botsOut").innerText = JSON.stringify(r, null, 2);

    if(r.ok && Array.isArray(r.data)){
        state.bots = r.data;
    } else {
        state.bots = [];
    }

    // Also refresh bot dropdown in Bindings
    renderBotSelect();
}

$("loadBots").addEventListener("click", ()=> loadBots(false));
$("clearBotsOut").addEventListener("click", ()=> $("botsOut").innerText = "");

/* ---------------- Bindings ---------------- */
$("useTenantBindings").addEventListener("click", async ()=>{
    const id = $("tenantSelectBindings").value;
    if(!id){ showMsg("cfgMsg", "Chọn tenant trước"); return; }
    applyTenantById(id);
    // load bots for this tenant so binding dropdown works
    await loadBots(true);
    showMsg("cfgMsg", "Tenant applied for bindings");
});

$("refreshBotsForBindings").addEventListener("click", async ()=>{
    if(!state.selectedTenant){
        showMsg("cfgMsg", "Chưa chọn tenant");
        return;
    }
    await loadBots(true);
    showMsg("cfgMsg", "Chatbots reloaded");
});

$("botSelect").addEventListener("change", (e)=>{
    setSelectedBot(e.target.value);
});

$("createTgBinding").addEventListener("click", async ()=>{
    $("bindingsOut").innerText = "";

    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    if(!state.selectedBot){ showMsg("cfgMsg", "Chưa chọn chatbot"); return; }

    const botToken = $("tgToken").value.trim();
    if(!botToken){ showMsg("cfgMsg", "Thiếu bot token"); return; }

    const payload = { chatbotId: state.selectedBot.id, botToken };
    const r = await req("POST", "/api/telegram/bindings", payload);

    // Always show binding result first
    $("bindingsOut").innerText = JSON.stringify(r, null, 2);

    // Auto setWebhook if ngrok base URL is provided
    const publicBase = ($("tgPublicBase")?.value || "").trim().replace(/\/+$/,"");
    const secretPath = r?.data?.secretPath; // <-- đúng theo response bạn gửi

    if(!r.ok){
        showMsg("cfgMsg", "Create binding FAIL");
        return;
    }

    if(!publicBase){
        showMsg("cfgMsg", "Binding OK. Nhập ngrok base URL để auto setWebhook.", 2500);
        return;
    }

    if(!secretPath){
        showMsg("cfgMsg", "Binding OK nhưng thiếu secretPath trong response", 2500);
        return;
    }

    const webhookUrl = publicBase + "/webhook/telegram/" + secretPath;
    const w = await setTelegramWebhook(botToken, webhookUrl);

    const merged = {
        binding: r,
        setWebhook: {
            webhookUrl,
            result: w
        }
    };

    $("bindingsOut").innerText = JSON.stringify(merged, null, 2);

    if(w.ok){
        showMsg("cfgMsg", "Set Telegram webhook OK", 2500);
    } else {
        showMsg("cfgMsg", "Set Telegram webhook FAIL", 2500);
    }
});

$("loadTgBindings").addEventListener("click", async ()=>{
    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    const r = await req("GET", "/api/telegram/bindings");
    $("bindingsOut").innerText = JSON.stringify(r, null, 2);
});

$("createMsgBinding").addEventListener("click", async ()=>{
    $("bindingsOut").innerText = "";

    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    if(!state.selectedBot){ showMsg("cfgMsg", "Chưa chọn chatbot"); return; }

    const pageId = $("pageId").value.trim();
    const pageAccessToken = $("pageToken").value.trim();
    if(!pageId || !pageAccessToken){
        showMsg("cfgMsg", "Thiếu pageId hoặc page access token");
        return;
    }

    const payload = { pageId, chatbotId: state.selectedBot.id, pageAccessToken };
    const r = await req("POST", "/api/messenger/bindings", payload);
    $("bindingsOut").innerText = JSON.stringify(r, null, 2);
});

$("loadMsgBindings").addEventListener("click", async ()=>{
    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    const r = await req("GET", "/api/messenger/bindings");
    $("bindingsOut").innerText = JSON.stringify(r, null, 2);
});

$("clearBindingsOut").addEventListener("click", ()=> $("bindingsOut").innerText = "");

/* ---------------- Init ---------------- */
$("saveCfg").addEventListener("click", saveCfg);
loadCfg();
setTab("tenants");

// Auto-load tenants at start to make dropdowns usable
loadTenants(false).catch(()=>{});

$("loadRuntime").addEventListener("click", async ()=>{
    $("runtimeMsg").innerText = "";
    $("runtimeOut").innerText = "";

    // Nếu bạn làm Hướng A/B (exclude runtime) => KHÔNG cần tenant headers
    const r = await req("GET", "/api/runtime/llm", undefined, { tenantHeaders: false });

    $("runtimeOut").innerText = JSON.stringify(r, null, 2);
    $("runtimeMsg").innerText = r.ok ? "OK" : `FAIL (${r.status})`;
});

$("clearRuntimeOut").addEventListener("click", ()=>{
    $("runtimeOut").innerText = "";
});