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
    selectedBot: null,    // {id, name, channel, ...}
    editingBotId: null,
    currentPrincipal: null
};

async function loadCurrentPrincipal(){
    const res = await fetch("/api/me");
    if (res.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required");
    }
    if (!res.ok) {
        throw new Error("Failed to load current principal");
    }

    const principal = await res.json();
    state.currentPrincipal = principal;
    if (principal.role !== "PLATFORM_ADMIN") {
        window.location.href = "/tenant";
        throw new Error("Platform admin access required");
    }

    if ($("adminIdentity")) {
        const label = principal.displayName || principal.email || principal.userId || "Platform Admin";
        $("adminIdentity").innerText = `${label} (${principal.role})`;
    }
    return principal;
}

function showMsg(id, text, ms=1200){
    $(id).innerText = text || "";
    if(text) setTimeout(()=> $(id).innerText="", ms);
}

function fmtDateTime(value){
    if(!value) return "";
    const date = new Date(value);
    if(Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
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

function renderPlatformOpsSummary(snapshot){
    const el = $("runtimeSummary");
    if(!el) return;
    if(!snapshot || !Array.isArray(snapshot.tenants)){
        el.classList.add("hidden");
        el.innerHTML = "";
        return;
    }

    const running = snapshot.activeRuntimeSessionCount ?? 0;
    const total = snapshot.tenantCount ?? snapshot.tenants.length;
    const readyKb = snapshot.tenants.filter(t => t.knowledgeBase?.status === "READY").length;
    const failedKb = snapshot.tenants.filter(t => t.knowledgeBase?.lastRebuildStatus === "FAILED").length;
    const inProgressKb = snapshot.tenants.filter(t => {
        const status = (t.knowledgeBase?.lastRebuildStatus || "").toUpperCase();
        return status === "IN_PROGRESS" || status === "RUNNING";
    }).length;
    const successKb = snapshot.tenants.filter(t => (t.knowledgeBase?.lastRebuildStatus || "").toUpperCase() === "SUCCESS").length;
    const aggregateKbStatus = failedKb > 0 ? "FAILED" : (inProgressKb > 0 ? "IN_PROGRESS" : (successKb > 0 ? "SUCCESS" : ""));
    const purchaseRequests = snapshot.purchaseRequests || {};
    const tenantKbHistory = snapshot.tenants
        .filter(t => Array.isArray(t.knowledgeBase?.rebuildHistory) && t.knowledgeBase.rebuildHistory.length > 0)
        .map(t => `
            <div class="kb-history-tenant">
                <div><b>${t.tenantName || t.tenantCode || t.tenantId}</b></div>
                ${renderKbRebuildHistory(t.knowledgeBase.rebuildHistory)}
            </div>
        `)
        .join("");
    const tenantRows = snapshot.tenants
        .filter(t => t.purchaseRequests && (t.purchaseRequests.totalRequests ?? 0) > 0)
        .map(t => `
            <tr>
                <td><b>${t.tenantName || t.tenantCode || t.tenantId}</b></td>
                <td class="metric">${t.purchaseRequests.totalRequests ?? 0}</td>
                <td class="metric">${t.purchaseRequests.newCount ?? 0}</td>
                <td class="metric">${t.purchaseRequests.contactedCount ?? 0}</td>
                <td class="metric">${t.purchaseRequests.completedCount ?? 0}</td>
                <td class="metric">${t.purchaseRequests.assignedCount ?? 0}</td>
                <td class="metric">${t.purchaseRequests.unassignedCount ?? 0}</td>
            </tr>
        `)
        .join("");
    el.classList.remove("hidden");
    el.innerHTML = `
        <div><b>Platform snapshot</b></div>
        <div>${running}/${total} tenant runtimes active</div>
        <div>${readyKb}/${total} tenants with ready KB artifacts</div>
        <div>${failedKb} tenant(s) with last tracked KB rebuild failure</div>
        <div>KB rebuild signal: ${renderKbStatusBadge(aggregateKbStatus)}</div>
        <div class="ops-stats-grid">
            <div class="ops-stat-card"><div class="muted">Purchase requests</div><div><b>${purchaseRequests.totalRequests ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">NEW</div><div><b>${purchaseRequests.newCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">CONTACTED</div><div><b>${purchaseRequests.contactedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">COMPLETED</div><div><b>${purchaseRequests.completedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Assigned</div><div><b>${purchaseRequests.assignedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Unassigned</div><div><b>${purchaseRequests.unassignedCount ?? 0}</b></div></div>
        </div>
        ${tenantRows ? `
            <table class="ops-stats-table">
                <thead>
                    <tr>
                        <th>Tenant</th>
                        <th>Total</th>
                        <th>NEW</th>
                        <th>CONTACTED</th>
                        <th>COMPLETED</th>
                        <th>Assigned</th>
                        <th>Unassigned</th>
                    </tr>
                </thead>
                <tbody>${tenantRows}</tbody>
            </table>
        ` : `<div class="ops-summary-copy">No purchase requests recorded yet.</div>`}
        <div class="ops-summary-copy"><b>Recent KB rebuild history</b></div>
        ${tenantKbHistory || `<div class="ops-summary-copy">No recent tenant KB rebuild history.</div>`}
    `;
}

function renderKbRebuildHistory(history){
    if(!Array.isArray(history) || history.length === 0){
        return `<div class="ops-summary-copy">No recent KB rebuild history.</div>`;
    }
    return `
        <div class="kb-history-list">
            ${history.map(item => `
                <div class="kb-history-item">
                    <div>${renderKbStatusBadge(item.status)}</div>
                    <div>Started: ${fmtDateTime(item.startedAt) || "—"}</div>
                    <div>Finished: ${fmtDateTime(item.finishedAt) || "—"}</div>
                    <div>${item.message || ""}</div>
                </div>
            `).join("")}
        </div>
    `;
}

function formatMetric(value){
    if(value === null || value === undefined || Number.isNaN(Number(value))){
        return "—";
    }
    return Number(value).toFixed(4);
}

function renderBenchmarkSummary(summary){
    const el = $("benchmarkSummary");
    if(!el) return;
    if(!summary || !Array.isArray(summary.modes) || summary.modes.length === 0){
        el.classList.add("hidden");
        el.innerHTML = "";
        return;
    }

    const interpretation = Array.isArray(summary.interpretation) ? summary.interpretation : [];
    const rows = summary.modes.map(mode => `
        <tr>
            <td><b>${mode.mode || "unknown"}</b></td>
            <td class="metric">${formatMetric(mode.recallAt5)}</td>
            <td class="metric">${formatMetric(mode.mrr)}</td>
            <td class="metric">${mode.totalQuestions ?? "—"}</td>
        </tr>
    `).join("");
    const interpretationHtml = interpretation.length
        ? interpretation.map(line => `<div>${line}</div>`).join("")
        : `<div>${summary.summary || "Benchmark artifact loaded."}</div>`;

    el.classList.remove("hidden");
    el.innerHTML = `
        <div><b>Retrieval benchmark summary</b></div>
        <div class="benchmark-summary-copy">${summary.summary || "Current evaluation artifact loaded."}</div>
        <div class="benchmark-meta">
            <div class="benchmark-stat"><div class="muted">Dataset size</div><div><b>${summary.datasetSize ?? "—"}</b></div></div>
            <div class="benchmark-stat"><div class="muted">Top-k</div><div><b>${summary.topK ?? "—"}</b></div></div>
            <div class="benchmark-stat"><div class="muted">Dataset</div><div><b>${summary.datasetPath || "—"}</b></div></div>
        </div>
        <table class="benchmark-table">
            <thead>
                <tr>
                    <th>Mode</th>
                    <th>Recall@5</th>
                    <th>MRR</th>
                    <th>Questions</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
        <div class="benchmark-summary-copy">${interpretationHtml}</div>
    `;
}

function kbStatusMeta(status){
    const normalized = (status || "").trim().toUpperCase();
    if(normalized === "SUCCESS") return { label: "SUCCESS", className: "ops-badge-success" };
    if(normalized === "FAILED") return { label: "FAILED", className: "ops-badge-failed" };
    if(normalized === "IN_PROGRESS" || normalized === "RUNNING") return { label: normalized, className: "ops-badge-progress" };
    if(!normalized) return { label: "UNKNOWN", className: "ops-badge-neutral" };
    return { label: normalized, className: "ops-badge-neutral" };
}

function renderKbStatusBadge(status){
    const meta = kbStatusMeta(status);
    return `<span class="ops-badge ${meta.className}">${meta.label}</span>`;
}

async function evictPlatformRuntime(tenantId){
    const params = new URLSearchParams({ tenantId });
    const res = await fetch(baseUrl() + `/api/ops/runtime/evict?${params.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(headersJson().Authorization ? { Authorization: headersJson().Authorization } : {}) }
    });
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
    // ✅ add "leads"
    ["tenants","members","chatbots","bindings","monitor","leads","purchase-requests","stats"].forEach(t=>{
        const el = $("tab-"+t);
        if(el) el.classList.toggle("hidden", t !== name);
    });

    // optional: auto load leads when open tab
    if(name === "leads"){
        refreshLeads().catch(()=>{});
    }
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

function getSelectedTenantIdForMembers(){
    return state.selectedTenant?.id || $("tenantId")?.value?.trim() || "";
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

function renderChatbotEditSelect(){
    const sel = $("chatbotSelectEdit");
    if(!sel) return;

    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "— create new chatbot —";
    sel.appendChild(opt0);

    for(const b of state.bots){
        const op = document.createElement("option");
        op.value = b.id;
        op.textContent = `${b.name} [${b.channel}]`;
        sel.appendChild(op);
    }

    sel.value = state.editingBotId || "";
}

function botPayloadFromForm(){
    const name = $("botName").value.trim();
    const channel = $("botChannel").value.trim();
    const personaJson = ($("botPersona").value || "").trim();
    const responseStyle = $("botResponseStyle").value.trim() || "natural";
    const provider = $("botProvider").value.trim() || "local";

    if(!name || !channel){
        throw new Error("Thiáº¿u bot name hoáº·c channel");
    }

    const payload = {
        name,
        channel,
        personaJson: personaJson || "{}",
        responseStyle,
        provider
    };

    // Only include API config fields if provider is claude and values are non-empty
    if(provider === "claude"){
        const apiModel = $("botApiModel").value.trim();
        const apiKey = $("botApiKey").value.trim();
        const apiBaseUrl = $("botApiBaseUrl").value.trim();

        if(apiModel) payload.apiModel = apiModel;
        if(apiKey) payload.apiKey = apiKey;
        if(apiBaseUrl) payload.apiBaseUrl = apiBaseUrl;
    }

    return payload;
}

function populateBotForm(bot){
    if(!bot){
        state.editingBotId = null;
        $("chatbotSelectEdit").value = "";
        $("botName").value = "";
        $("botChannel").value = "telegram";
        $("botPersona").value = "";
        $("botResponseStyle").value = "natural";
        $("botProvider").value = "local";
        $("botApiModel").value = "";
        $("botApiKey").value = "";
        $("botApiBaseUrl").value = "";
        toggleApiConfigFields();
        return;
    }

    state.editingBotId = bot.id;
    $("chatbotSelectEdit").value = bot.id;
    $("botName").value = bot.name || "";
    $("botChannel").value = bot.channel || "telegram";
    $("botPersona").value = bot.persona ? JSON.stringify(bot.persona) : "";
    $("botResponseStyle").value = bot.responseStyle || "natural";
    $("botProvider").value = bot.provider || "local";
    $("botApiModel").value = bot.apiModel || "";
    $("botApiKey").value = ""; // never populate real key for security
    $("botApiBaseUrl").value = bot.apiBaseUrl || "";
    toggleApiConfigFields();
}

/* ---------------- Helpers ---------------- */
function getCurrentTenantId(){
    return state.selectedTenant?.id || $("tenantId")?.value?.trim() || "";
}

async function loadPurchaseRequests(){
    const tenantId = getCurrentTenantId();
    if(!tenantId){
        showMsg("purchaseRequestsMsg", "Select a tenant first", 1800);
        renderPurchaseRequests([]);
        return;
    }

    const status = $("purchaseRequestStatusFilter")?.value?.trim();
    const params = new URLSearchParams();
    if(status) params.set("status", status);

    const path = params.toString()
        ? `/api/purchase-requests?${params.toString()}`
        : "/api/purchase-requests";
    const r = await req("GET", path);
    if(!r.ok){
        throw new Error(`Failed to load purchase requests (${r.status})`);
    }

    const items = Array.isArray(r.data) ? r.data : [];
    renderPurchaseRequests(items);
    showMsg("purchaseRequestsMsg", `Loaded ${items.length} request(s)`, 1600);
}

async function updatePurchaseRequestStatus(id, status){
    const r = await req("PUT", `/api/purchase-requests/${encodeURIComponent(id)}/status`, { status });
    if(!r.ok){
        throw new Error(r?.data?.message || `Failed to update purchase request (${r.status})`);
    }
    return r.data;
}

function renderPurchaseRequests(items){
    const tbody = document.querySelector("#purchase-requests-table tbody");
    if(!tbody) return;
    tbody.innerHTML = "";

    if(!Array.isArray(items) || items.length === 0){
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 7;
        td.className = "muted purchase-request-empty";
        td.textContent = "No purchase requests found. Choose a tenant, keep or change the filter, then click Load purchase requests.";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    for(const item of items){
        const tr = document.createElement("tr");
        tr.dataset.requestId = item.id || "";
        tr.dataset.currentStatus = item.status || "NEW";

        const values = [
            item.customer_name || "",
            item.phone || "",
            item.shipping_address || "",
            item.status || "",
            item.assigned_to_display_name || item.assigned_to_member_id || "Unassigned",
            fmtDateTime(item.created_at)
        ];

        values.forEach((value, index)=>{
            const td = document.createElement("td");
            if(index === 3){
                td.dataset.role = "status-text";
                td.innerHTML = `<span class="status-badge ${statusBadgeClass(value)}">${value || "NEW"}</span>`;
            } else {
                td.textContent = value;
            }
            tr.appendChild(td);
        });

        const actionsTd = document.createElement("td");
        actionsTd.innerHTML = `
            <div class="status-inline">
                <select data-role="status-select">
                    <option value="NEW">NEW</option>
                    <option value="CONTACTED">CONTACTED</option>
                    <option value="COMPLETED">COMPLETED</option>
                </select>
                <span class="inline-feedback" data-role="status-feedback"></span>
            </div>
        `;
        actionsTd.querySelector('[data-role="status-select"]').value = item.status || "NEW";
        tr.appendChild(actionsTd);

        tbody.appendChild(tr);
    }
}

async function handlePurchaseRequestStatusChange(selectEl){
    const tr = selectEl.closest("tr");
    if(!tr) return;

    const nextStatus = selectEl.value;
    const previousStatus = tr.dataset.currentStatus || "";
    const requestId = tr.dataset.requestId;
    const statusText = tr.querySelector('[data-role="status-text"]');
    const feedback = tr.querySelector('[data-role="status-feedback"]');

    if(!requestId || nextStatus === previousStatus){
        if(feedback) feedback.textContent = "";
        return;
    }

    if(feedback){
        feedback.classList.remove("error");
        feedback.textContent = "Saving...";
    }
    selectEl.disabled = true;

    try{
        const updated = await updatePurchaseRequestStatus(requestId, nextStatus);
        const savedStatus = updated?.status || nextStatus;
        tr.dataset.currentStatus = savedStatus;
        if(statusText) statusText.innerHTML = `<span class="status-badge ${statusBadgeClass(savedStatus)}">${savedStatus}</span>`;
        selectEl.value = savedStatus;
        if(feedback){
            feedback.classList.remove("error");
            feedback.textContent = "Saved";
        }
        showMsg("purchaseRequestsMsg", `Request #${requestId} updated to ${savedStatus}`, 1600);
    } catch(err){
        console.error(err);
        selectEl.value = previousStatus;
        if(feedback){
            feedback.classList.add("error");
            feedback.textContent = err.message || "Update failed";
        }
        showMsg("purchaseRequestsMsg", "Update purchase request FAIL", 1800);
    } finally {
        selectEl.disabled = false;
    }
}

function statusBadgeClass(status){
    const normalized = (status || "NEW").toUpperCase();
    if(normalized === "CONTACTED") return "status-contacted";
    if(normalized === "COMPLETED") return "status-completed";
    return "status-new";
}

/* ---------------- Health ---------------- */
$("pingHealth").addEventListener("click", async ()=>{
    $("healthMsg").innerText = "";
    const r = await req("GET", "/actuator/health", undefined, { tenantHeaders:false });
    $("healthMsg").innerText = r.ok ? "health: OK" : `health: FAIL (${r.status})`;
});

$("btn-admin-logout")?.addEventListener("click", async ()=>{
    try {
        await fetch("/api/login/logout", { method: "POST" });
    } catch (err) {
        console.error(err);
    } finally {
        localStorage.removeItem("tenant_id");
        localStorage.removeItem("tenant_name");
        window.location.href = "/login";
    }
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

    try{
        const payload = botPayloadFromForm();
        const r = await req("POST", "/api/chatbots", payload);
        $("botsOut").innerText = JSON.stringify(r, null, 2);

        await loadBots(false);
        if(r.ok && r.data){
            populateBotForm(r.data);
            showMsg("botsMsg", "Chatbot created");
        }
    }catch(err){
        $("botsMsg").innerText = err.message;
    }
});

$("saveBot").addEventListener("click", async ()=>{
    $("botsMsg").innerText = "";

    if(!state.selectedTenant){
        $("botsMsg").innerText = "Chưa chọn tenant";
        return;
    }
    if(!state.editingBotId){
        $("botsMsg").innerText = "Load a chatbot first";
        return;
    }

    try{
        const payload = botPayloadFromForm();
        const r = await req("PUT", `/api/chatbots/${state.editingBotId}`, payload);
        $("botsOut").innerText = JSON.stringify(r, null, 2);

        await loadBots(true);
        if(r.ok && r.data){
            populateBotForm(r.data);
            showMsg("botsMsg", "Chatbot saved");
        }
    }catch(err){
        $("botsMsg").innerText = err.message;
    }
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
    renderChatbotEditSelect();

    if(state.editingBotId){
        const editingBot = state.bots.find(x => x.id === state.editingBotId);
        populateBotForm(editingBot || null);
    }
}

$("loadBots").addEventListener("click", ()=> loadBots(false));
$("clearBotsOut").addEventListener("click", ()=> $("botsOut").innerText = "");
$("loadSelectedBot").addEventListener("click", ()=>{
    const botId = $("chatbotSelectEdit").value;
    if(!botId){
        populateBotForm(null);
        showMsg("botsMsg", "Form reset for new chatbot");
        return;
    }

    const bot = state.bots.find(x => x.id === botId);
    if(!bot){
        showMsg("botsMsg", "Load chatbots first");
        return;
    }

    populateBotForm(bot);
    showMsg("botsMsg", "Chatbot loaded into form");
});

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

// Provider toggle for API config fields
const providerSelect = $("botProvider");
if(providerSelect){
    providerSelect.addEventListener("change", toggleApiConfigFields);
}

function toggleApiConfigFields(){
    const provider = $("botProvider")?.value;
    const show = provider === "claude";
    const note = $("apiConfigNote");
    const fields = $("apiConfigFields");
    if(note) note.style.display = show ? "block" : "none";
    if(fields) fields.style.display = show ? "grid" : "none";
}

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

/* =========================================================
   ✅ LEADS (5.3) — fetch + render + status update + drawer
   ========================================================= */

async function fetchLeads(tenantId){
    // Prefer your API host + tenant headers, so use req()
    // Path expected by guide: /admin/api/leads?tenantId=...
    const r = await req("GET", `/admin/api/leads?tenantId=${encodeURIComponent(tenantId)}`, undefined, { tenantHeaders: true });
    if(!r.ok) throw new Error("Failed to load leads");
    return r.data;
}

function renderLeads(leads){
    const tbody = document.querySelector("#leads-table tbody");
    if(!tbody) return;
    tbody.innerHTML = "";

    if(!Array.isArray(leads) || leads.length === 0){
        const tr = document.createElement("tr");
        tr.innerHTML = `<td colspan="6" class="muted">No leads yet.</td>`;
        tbody.appendChild(tr);
        return;
    }

    for(const l of leads){
        const tr = document.createElement("tr");

        const created = l.createdAt ? new Date(l.createdAt).toLocaleString() : "";
        tr.innerHTML = `
          <td>${created}</td>
          <td>${l.status ?? ""}</td>
          <td>${l.channel ?? ""}</td>
          <td>${l.customerHandle || ""}</td>
          <td>${l.conversationId || ""}</td>
          <td>
            <button class="btn secondary" data-action="view" data-id="${l.id}">View</button>
            <button class="btn secondary" data-action="contacted" data-id="${l.id}">Mark Contacted</button>
            <button class="btn secondary" data-action="closed" data-id="${l.id}">Mark Closed</button>
          </td>
        `;

        tr.dataset.slots = l.slotsJson || "{}";
        tr.dataset.transcript = l.transcript || "";
        tr.dataset.leadId = l.id;

        tbody.appendChild(tr);
    }
}

async function updateLeadStatus(id, status){
    const r = await req("POST", `/admin/api/leads/${encodeURIComponent(id)}/status?status=${encodeURIComponent(status)}`, undefined, { tenantHeaders: true });
    if(!r.ok) throw new Error("Failed to update status");
    return r.data;
}

function openLeadDetails(slotsJson, transcript){
    const slotsEl = document.querySelector("#lead-slots");
    const trEl = document.querySelector("#lead-transcript");
    if(slotsEl) slotsEl.textContent = `Slots:\n${slotsJson || "{}"}`;
    if(trEl) trEl.textContent = `Transcript:\n${transcript || ""}`;
    document.querySelector("#lead-details")?.classList.remove("hidden");
}

function closeLeadDetails(){
    document.querySelector("#lead-details")?.classList.add("hidden");
}

async function refreshLeads(){
    const tenantId = getCurrentTenantId();
    if(!tenantId){
        showMsg("cfgMsg", "Chọn tenant trước (Use tenant)", 1800);
        renderLeads([]); // clear table
        return;
    }
    const leads = await fetchLeads(tenantId);
    renderLeads(leads);
}

// Hook UI
document.querySelector("#btn-refresh-leads")?.addEventListener("click", async ()=>{
    try{
        await refreshLeads();
    } catch(e){
        console.error(e);
        showMsg("cfgMsg", "Load leads FAIL", 1800);
    }
});

document.querySelector("#leads-table")?.addEventListener("click", async (e)=>{
    const btn = e.target.closest("button");
    if(!btn) return;

    const action = btn.dataset.action;
    const tr = btn.closest("tr");
    const id = btn.dataset.id;

    try{
        if(action === "view"){
            openLeadDetails(tr?.dataset?.slots, tr?.dataset?.transcript);
            return;
        }

        if(action === "contacted"){
            await updateLeadStatus(id, "CONTACTED");
        } else if(action === "closed"){
            await updateLeadStatus(id, "CLOSED");
        }

        await refreshLeads();
    } catch(err){
        console.error(err);
        showMsg("cfgMsg", "Update lead FAIL", 1800);
    }
});

document.querySelector("#btn-close-lead")?.addEventListener("click", closeLeadDetails);
document.querySelector("#loadPurchaseRequests")?.addEventListener("click", ()=>{
    loadPurchaseRequests().catch(err=>{
        console.error(err);
        showMsg("purchaseRequestsMsg", "Load purchase requests FAIL", 1800);
        renderPurchaseRequests([]);
    });
});
document.querySelector("#purchase-requests-table")?.addEventListener("change", (e)=>{
    const selectEl = e.target.closest('[data-role="status-select"]');
    if(!selectEl) return;
    handlePurchaseRequestStatusChange(selectEl);
});

function replaceElementWithClone(id){
    const existing = $(id);
    if(!existing) return null;
    const clone = existing.cloneNode(true);
    existing.replaceWith(clone);
    return clone;
}

async function loadTenants(autoPickFirst=false, preferredTenantId=""){
    const r = await req("GET", "/api/admin/tenants", undefined, { tenantHeaders:false });
    $("tenantsOut").innerText = JSON.stringify(r, null, 2);

    if(r.ok && Array.isArray(r.data)){
        state.tenants = r.data;
        renderTenantSelect("tenantSelectBots");
        renderTenantSelect("tenantSelectBindings");

        const tenantToSelect =
            (preferredTenantId && state.tenants.find(t => t.id === preferredTenantId))
            || (autoPickFirst ? state.tenants[0] : null);

        if(tenantToSelect){
            applyTenantById(tenantToSelect.id);
            $("tenantSelectBots").value = tenantToSelect.id;
            $("tenantSelectBindings").value = tenantToSelect.id;
        }
    }
}

function wireTenantProvisioningUi(){
    const createTenantButton = replaceElementWithClone("createTenant");
    const loadTenantsButton = replaceElementWithClone("loadTenants");
    const clearTenantsButton = replaceElementWithClone("clearTenantsOut");

    createTenantButton?.addEventListener("click", async ()=>{
        $("tenantsMsg").innerText = "";
        const code = $("tenantCode").value.trim();
        const name = $("tenantName").value.trim();
        const apiKey = $("tenantApiKey").value.trim();
        const kbDir = $("tenantKbDir").value.trim();
        const status = $("tenantStatus").value.trim();

        if(!code || !name){
            $("tenantsMsg").innerText = "Missing code or name";
            return;
        }

        const body = { code, name, status };
        if(apiKey) body.apiKey = apiKey;
        if(kbDir) body.kbDir = kbDir;

        const r = await req("POST", "/api/admin/tenants", body, { tenantHeaders:false });
        $("tenantsOut").innerText = JSON.stringify(r, null, 2);

        if(r.ok && r.data?.id){
            $("tenantApiKey").value = "";
            $("tenantKbDir").value = "";
            $("tenantStatus").value = r.data.status || "ACTIVE";
            await loadTenants(false, r.data.id);
            showMsg("tenantsMsg", `Created tenant ${r.data.code || code}`, 1800);
            return;
        }

        if(r.data?.message){
            $("tenantsMsg").innerText = r.data.message;
        }
    });

    loadTenantsButton?.addEventListener("click", ()=> loadTenants(false));
    clearTenantsButton?.addEventListener("click", ()=> $("tenantsOut").innerText = "");
}

function wireMemberManagementUi(){
    $("createMember")?.addEventListener("click", async ()=>{
        const tenantId = getSelectedTenantIdForMembers();
        if(!tenantId){
            $("membersMsg").innerText = "Select a tenant first";
            return;
        }

        const body = {
            email: $("memberEmail").value.trim(),
            displayName: $("memberDisplayName").value.trim(),
            role: $("memberRole").value.trim(),
            status: $("memberStatus").value.trim(),
            password: $("memberPassword").value.trim()
        };
        if(!body.email || !body.password){
            $("membersMsg").innerText = "Missing email or password";
            return;
        }

        const r = await req("POST", `/api/admin/tenant-members?tenantId=${encodeURIComponent(tenantId)}`, body, { tenantHeaders:false });
        $("membersOut").innerText = JSON.stringify(r, null, 2);
        if(r.ok){
            $("memberPassword").value = "";
            showMsg("membersMsg", `Created member ${body.email}`, 1800);
            await loadMembersForSelectedTenant();
            return;
        }
        $("membersMsg").innerText = r.data?.message || `Create member failed (${r.status})`;
    });

    $("loadMembers")?.addEventListener("click", ()=> {
        loadMembersForSelectedTenant().catch(err=>{
            console.error(err);
            $("membersMsg").innerText = err.message || "Load members failed";
        });
    });

    $("clearMembersOut")?.addEventListener("click", ()=> $("membersOut").innerText = "");
}

async function loadMembersForSelectedTenant(){
    const tenantId = getSelectedTenantIdForMembers();
    if(!tenantId){
        $("membersMsg").innerText = "Select a tenant first";
        $("membersOut").innerText = "";
        return;
    }

    const r = await req("GET", `/api/admin/tenant-members?tenantId=${encodeURIComponent(tenantId)}`, undefined, { tenantHeaders:false });
    $("membersOut").innerText = JSON.stringify(r, null, 2);
    if(r.ok){
        showMsg("membersMsg", `Loaded ${(Array.isArray(r.data) ? r.data.length : 0)} member(s)`, 1600);
        return;
    }
    $("membersMsg").innerText = r.data?.message || `Load members failed (${r.status})`;
}

/* ---------------- Init ---------------- */
$("saveCfg").addEventListener("click", saveCfg);
loadCfg();
wireTenantProvisioningUi();
wireMemberManagementUi();

$("loadRuntime").addEventListener("click", async ()=>{
    $("runtimeMsg").innerText = "";
    $("runtimeOut").innerText = "";

    // Nếu bạn làm Hướng A/B (exclude runtime) => KHÔNG cần tenant headers
    const [platformRes, benchmarkRes] = await Promise.all([
        req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
        req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
    ]);
    renderPlatformOpsSummary(platformRes.ok ? platformRes.data : null);
    renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
    $("runtimeOut").innerText = JSON.stringify({
        platform: platformRes,
        benchmark: benchmarkRes
    }, null, 2);
    $("runtimeMsg").innerText = (platformRes.ok && benchmarkRes.ok)
        ? "Platform ops and benchmark summary loaded"
        : `FAIL (platform=${platformRes.status}, benchmark=${benchmarkRes.status})`;
});

$("clearRuntimeOut").addEventListener("click", ()=>{
    $("runtimeOut").innerText = "";
    $("runtimeMsg").innerText = "";
    if($("runtimeSummary")){
        $("runtimeSummary").classList.add("hidden");
        $("runtimeSummary").innerHTML = "";
    }
    if($("benchmarkSummary")){
        $("benchmarkSummary").classList.add("hidden");
        $("benchmarkSummary").innerHTML = "";
    }
});

$("evictRuntime")?.addEventListener("click", async ()=>{
    const tenantId = $("runtimeEvictTenantId")?.value?.trim();
    if(!tenantId){
        $("runtimeMsg").innerText = "Enter a tenant UUID";
        return;
    }

    $("runtimeMsg").innerText = "Evicting runtime...";
    const r = await evictPlatformRuntime(tenantId);
    $("runtimeOut").innerText = JSON.stringify(r, null, 2);
    $("runtimeMsg").innerText = r.ok ? "Runtime evicted" : (r.data?.message || `FAIL (${r.status})`);
    if(r.ok){
        const [refreshed, benchmarkRes] = await Promise.all([
            req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
            req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
        ]);
        renderPlatformOpsSummary(refreshed.ok ? refreshed.data : null);
        renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
    }
});

async function loadStats(days){
    const ov = await req("GET", `/admin/api/stats/overview?days=${days}`, undefined, { tenantHeaders:false });
    if(ov.ok){
        $("st_totalConv").innerText = ov.data.totalConversations;
        $("st_totalLeads").innerText = ov.data.totalLeads;
        $("st_posRate").innerText = ((ov.data.feedbackPositiveRate || 0) * 100).toFixed(1) + "%";
    }

    const bt = await req("GET", `/admin/api/stats/by-tenant?days=${days}`, undefined, { tenantHeaders:false });
    $("statsByTenantOut").innerText = JSON.stringify(bt.data, null, 2);

    const ts = await req("GET", `/admin/api/stats/timeseries?days=${days}`, undefined, { tenantHeaders:false });
    $("statsTimeseriesOut").innerText = JSON.stringify(ts.data, null, 2);
}

$("loadStats7") && ($("loadStats7").onclick = ()=> loadStats(7).catch(e=>alert(e.message)));
$("loadStats30") && ($("loadStats30").onclick = ()=> loadStats(30).catch(e=>alert(e.message)));

async function bootstrapAdminUi(){
    try {
        await loadCurrentPrincipal();
        setTab("tenants");
        await loadTenants(false);
        // Initialize provider field visibility
        toggleApiConfigFields();
    } catch (err) {
        console.error(err);
    }
}

bootstrapAdminUi();
