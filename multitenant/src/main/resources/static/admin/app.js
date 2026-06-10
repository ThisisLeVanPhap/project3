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
    currentPrincipal: null,
    onboardingRequests: [],
    selectedOnboardingRequestId: null,
    messengerBindings: [],
    productDatasets: [],
    selectedProductDataset: null,
    activeKbDirectory: null,
    kbVersions: [],
    selectedKbVersion: null,
    kbSourceUrls: null,
    kbRuntimeStatus: null,
    currentTab: "overview"
};

const PRIMARY_GROUPS = {
    dashboard: ["overview", "monitor", "stats"],
    tenantManagement: ["tenants", "members", "onboarding"],
    chatbotChannels: ["chatbots", "bindings", "messenger-status", "telegram-status"],
    knowledgeBase: ["kb-dirs", "kb-versions", "kb-rebuild", "product-datasets"],
    businessData: ["leads", "purchase-requests"],
    operations: ["runtime", "health", "benchmark", "dev-debug"]
};

const DEFAULT_SUB_TABS = {
    dashboard: "overview",
    tenantManagement: "tenants",
    chatbotChannels: "chatbots",
    knowledgeBase: "product-datasets",
    businessData: "leads",
    operations: "runtime"
};

const ALL_ADMIN_TABS = Object.values(PRIMARY_GROUPS).flat();

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

function displayValue(value){
    if(value === null || value === undefined || value === "") return "-";
    return String(value);
}

function escapeHtml(value){
    return displayValue(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function boolLabel(value){
    if(value === true) return "Yes";
    if(value === false) return "No";
    return "-";
}

function sanitizeSensitive(value){
    if(Array.isArray(value)){
        return value.map(sanitizeSensitive);
    }
    if(value && typeof value === "object"){
        const out = {};
        for(const [key, child] of Object.entries(value)){
            const normalizedKey = key.toLowerCase();
            if(
                normalizedKey === "pageaccesstoken" ||
                normalizedKey === "page_access_token" ||
                normalizedKey === "pagetoken" ||
                normalizedKey === "page_token" ||
                normalizedKey === "apikey" ||
                normalizedKey === "api_key" ||
                normalizedKey === "bottoken" ||
                normalizedKey === "bot_token" ||
                normalizedKey === "token" ||
                normalizedKey === "password" ||
                normalizedKey === "basicauth" ||
                normalizedKey === "basic_auth" ||
                normalizedKey === "authorization"
            ){
                out[key] = "[redacted]";
            } else {
                out[key] = sanitizeSensitive(child);
            }
        }
        return out;
    }
    return value;
}

function setJsonOutput(id, value, sanitize=false){
    const el = $(id);
    if(!el) return;
    el.innerText = JSON.stringify(sanitize ? sanitizeSensitive(value) : value, null, 2);
}

function setButtonLoading(button, loading, loadingText="Loading..."){
    if(!button) return;
    if(loading){
        button.dataset.originalText = button.dataset.originalText || button.textContent;
        button.textContent = loadingText;
        button.disabled = true;
        button.classList.add("is-loading");
        return;
    }
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
    button.classList.remove("is-loading");
    delete button.dataset.originalText;
}

async function withButtonLoading(button, loadingText, task){
    setButtonLoading(button, true, loadingText);
    try{
        return await task();
    } finally {
        setButtonLoading(button, false);
    }
}

function renderPanelState(panelId, message, kind="empty"){
    const panel = $(panelId);
    if(!panel) return;
    panel.classList.remove("hidden");
    panel.innerHTML = `<div class="panel-state ${kind}">${escapeHtml(message)}</div>`;
}

function wireRawOutputToggle(buttonId, outputId){
    const button = $(buttonId);
    const output = $(outputId);
    if(!button || !output) return;
    button.addEventListener("click", ()=>{
        const willShow = output.classList.contains("hidden");
        output.classList.toggle("hidden", !willShow);
        button.textContent = willShow ? "Hide raw response" : "Show raw response";
    });
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
    const selectedApiKey = state.selectedTenant?.apiKey || "";
    const selectedTenantId = state.selectedTenant?.id || "";
    const apiKey = selectedApiKey || $("apiKey").value.trim();
    const tenantId = selectedTenantId || $("tenantId").value.trim();

    if(auth) h["Authorization"] = auth;

    // TenantResolver: ưu tiên apiKey, nếu không có thì tenantId
    if(apiKey) h["X-API-Key"] = apiKey;
    else if(tenantId) h["X-Tenant-Id"] = tenantId;

    return h;
}

async function req(method, path, body, opts = { tenantHeaders: true }){
    const url = opts.sameOrigin === false ? baseUrl() + path : path;
    const headers = { "Content-Type": "application/json" };

    // tenant headers ON/OFF
    if(opts.tenantHeaders !== false){
        Object.assign(headers, headersJson());
    } else {
        // chỉ giữ Authorization nếu có
        const auth = $("basicAuth").value.trim();
        if(auth) headers["Authorization"] = auth;
    }

    const opt = { method, headers, credentials: "same-origin" };
    if(body !== undefined) opt.body = JSON.stringify(body);

    const res = await fetch(url, opt);
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch(e) {}
    return { ok: res.ok, status: res.status, data };
}

function renderSystemStatusSummary(statusResult){
    const el = $("systemStatusSummary");
    if(!el) return;

    el.classList.remove("hidden");
    if(!statusResult?.ok){
        el.innerHTML = `
            <div><b>System status</b></div>
            <div class="panel-state error">Unable to load system status (${statusResult?.status || "-"})</div>
        `;
        return;
    }

    const s = statusResult.data || {};
    const messenger = s.messenger_bindings || {};
    const kb = s.kb || {};
    const runtime = s.runtime || {};
    const purchase = s.purchase_requests || {};
    const cards = [
        ["Tenants", s.tenants?.total],
        ["Chatbots", s.chatbots?.total],
        ["Messenger total", messenger.total],
        ["Messenger active", messenger.active],
        ["Messenger inactive", messenger.inactive],
        ["Token configured", messenger.token_configured],
        ["KB versions", kb.versions_total],
        ["KB ready", kb.ready],
        ["KB failed", kb.failed],
        ["KB building", kb.building],
        ["KB archived", kb.archived],
        ["Java runtimes", runtime.java_spawned_running],
        ["External runtime", boolLabel(runtime.external_mode)],
        ["Purchase requests", purchase.total],
        ["PR new", purchase.new],
        ["PR contacted", purchase.contacted],
        ["PR completed", purchase.completed]
    ];

    el.innerHTML = `
        <div><b>System status</b></div>
        <div class="ops-stats-grid">
            ${cards.map(([label, value]) => `
                <div class="ops-stat-card">
                    <div class="muted">${escapeHtml(label)}</div>
                    <div><b>${escapeHtml(displayValue(value))}</b></div>
                </div>
            `).join("")}
        </div>
    `;
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

function maskSecret(value){
    if(!value) return "-";
    const text = String(value);
    if(text.length <= 8) return "********";
    return `${text.slice(0, 4)}...${text.slice(-4)}`;
}

function shortPreview(value, maxLength=80){
    if(value === null || value === undefined || value === "") return "-";
    const text = typeof value === "string" ? value : JSON.stringify(value);
    if(text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1)}...`;
}

function normalizedSearchText(values){
    return values
        .map(value => value === null || value === undefined ? "" : String(value).toLowerCase())
        .join(" ");
}

function tenantMatchesFilter(tenant, filter){
    if(!filter) return true;
    return normalizedSearchText([
        tenant.id,
        tenant.code,
        tenant.name,
        tenant.status,
        tenant.kbDir || tenant.kb_dir,
        tenant.activeKbVersionId || tenant.active_kb_version_id
    ]).includes(filter);
}

function botMatchesFilter(bot, filter){
    if(!filter) return true;
    return normalizedSearchText([
        bot.id,
        bot.name,
        bot.tenantId || bot.tenant_id,
        bot.channel,
        bot.provider,
        bot.mode,
        bot.status,
        bot.persona
    ]).includes(filter);
}

function renderStatusBadge(status){
    const normalized = (status || "").toUpperCase();
    if(normalized === "ACTIVE") return '<span class="status-badge status-completed">ACTIVE</span>';
    if(normalized === "INACTIVE") return '<span class="status-badge status-new">INACTIVE</span>';
    if(normalized) return renderKbStatusBadge(normalized);
    return "-";
}

function renderDatasetStatusBadge(status){
    const normalized = (status || "").toUpperCase();
    if(normalized === "READY" || normalized === "REGISTERED" || normalized === "ACTIVE"){
        return `<span class="status-badge status-completed">${escapeHtml(normalized)}</span>`;
    }
    if(normalized === "FAILED" || normalized === "ERROR"){
        return `<span class="ops-badge ops-badge-failed">${escapeHtml(normalized)}</span>`;
    }
    if(normalized === "PROCESSING" || normalized === "BUILDING"){
        return `<span class="ops-badge ops-badge-progress">${escapeHtml(normalized)}</span>`;
    }
    return normalized ? `<span class="ops-badge ops-badge-neutral">${escapeHtml(normalized)}</span>` : "-";
}

function productDatasetRowId(dataset){
    return dataset?.id || dataset?.dataset_id || dataset?.datasetId || "";
}

function productDatasetBusinessId(dataset){
    return dataset?.dataset_id || dataset?.datasetId || dataset?.id || "";
}

function renderProductDatasetsTable(emptyMessage="Click Load datasets to refresh product dataset registry."){
    const panel = $("productDatasetsTablePanel");
    if(!panel) return;

    const datasets = Array.isArray(state.productDatasets) ? state.productDatasets : [];
    if(datasets.length === 0){
        renderPanelState("productDatasetsTablePanel", emptyMessage, "empty");
        return;
    }

    panel.classList.remove("hidden");
    panel.innerHTML = `
        <table class="table" id="product-datasets-table">
            <thead>
                <tr>
                    <th>Dataset ID</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Products</th>
                    <th>RAG chunks</th>
                    <th>Crawled/Created at</th>
                    <th>Path preview</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${datasets.map(dataset => {
                    const rowId = productDatasetRowId(dataset);
                    const datasetId = productDatasetBusinessId(dataset);
                    const createdAt = dataset.created_at || dataset.createdAt || dataset.registered_at || dataset.registeredAt;
                    return `
                        <tr data-dataset-id="${escapeHtml(rowId)}">
                            <td><b>${escapeHtml(datasetId)}</b><div class="muted">${escapeHtml(dataset.version || "")}</div></td>
                            <td>${escapeHtml(dataset.source)}</td>
                            <td>${renderDatasetStatusBadge(dataset.status)}</td>
                            <td>${escapeHtml(displayValue(dataset.product_count ?? dataset.productCount))}</td>
                            <td>${escapeHtml(displayValue(dataset.rag_chunk_count ?? dataset.ragChunkCount))}</td>
                            <td>${escapeHtml(fmtDateTime(createdAt) || "-")}</td>
                            <td class="table-preview dataset-path-preview" title="${escapeHtml(dataset.path || "")}">${escapeHtml(shortPreview(dataset.path, 72))}</td>
                            <td>
                                <div class="table-actions dataset-actions">
                                    <button class="secondary" data-action="dataset-view">View</button>
                                    <button class="secondary" data-action="dataset-assign">Assign to selected tenant</button>
                                    <button class="danger" data-action="dataset-delete">Delete record</button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}

function renderProductDatasetDetail(dataset){
    const panel = $("productDatasetDetailPanel");
    if(!panel) return;
    if(!dataset){
        panel.classList.add("hidden");
        panel.innerHTML = "";
        return;
    }

    state.selectedProductDataset = dataset;
    const rows = [
        ["Dataset id", productDatasetBusinessId(dataset)],
        ["Source", dataset.source],
        ["Source url", dataset.source_url || dataset.sourceUrl],
        ["Path", dataset.path],
        ["Manifest path", dataset.manifest_path || dataset.manifestPath],
        ["Product count", dataset.product_count ?? dataset.productCount],
        ["RAG chunk count", dataset.rag_chunk_count ?? dataset.ragChunkCount],
        ["Content hash", dataset.content_hash || dataset.contentHash],
        ["Status", dataset.status],
        ["Registered at", fmtDateTime(dataset.registered_at || dataset.registeredAt)],
        ["Last assigned tenant", dataset.last_assigned_tenant_id || dataset.lastAssignedTenantId],
        ["Last assigned at", fmtDateTime(dataset.last_assigned_at || dataset.lastAssignedAt)]
    ];

    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="card2 dataset-detail-card">
            <div class="drawer-header">
                <h3>Dataset metadata</h3>
                <button class="secondary" id="closeProductDatasetDetail">Close</button>
            </div>
            <div class="dataset-detail-grid">
                ${rows.map(([label, value]) => `
                    <div class="dataset-detail-row">
                        <div class="muted">${escapeHtml(label)}</div>
                        <div class="dataset-detail-value">${escapeHtml(displayValue(value))}</div>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
    $("closeProductDatasetDetail")?.addEventListener("click", ()=>{
        panel.classList.add("hidden");
        panel.innerHTML = "";
        state.selectedProductDataset = null;
    });
}

function renderProductDatasetAssignResult(result, datasetId){
    const panel = $("productDatasetAssignPanel");
    if(!panel) return;
    const tenant = state.selectedTenant;
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="card2 assign-result-card">
            <h3>Assign result</h3>
            <div class="dataset-detail-grid">
                <div class="dataset-detail-row"><div class="muted">Selected tenant</div><div class="dataset-detail-value">${escapeHtml(selectedTenantLabel() || result?.tenant_code || result?.tenantId || "-")}</div></div>
                <div class="dataset-detail-row"><div class="muted">Tenant code</div><div class="dataset-detail-value">${escapeHtml(result?.tenant_code || tenant?.code || "-")}</div></div>
                <div class="dataset-detail-row"><div class="muted">Dataset id</div><div class="dataset-detail-value">${escapeHtml(result?.dataset_id || result?.datasetId || datasetId)}</div></div>
                <div class="dataset-detail-row"><div class="muted">KB dir</div><div class="dataset-detail-value">${escapeHtml(result?.kb_dir || result?.kbDir)}</div></div>
                <div class="dataset-detail-row"><div class="muted">Chunk count</div><div class="dataset-detail-value">${escapeHtml(displayValue(result?.chunk_count ?? result?.chunkCount))}</div></div>
                <div class="dataset-detail-row"><div class="muted">Tenant KB version</div><div class="dataset-detail-value">${escapeHtml(result?.version_tag || result?.versionTag || result?.kb_version_id || result?.kbVersionId)}</div></div>
                <div class="dataset-detail-row"><div class="muted">Message</div><div class="dataset-detail-value">${escapeHtml(result?.message || (result?.success ? "Assigned successfully" : "-"))}</div></div>
            </div>
        </div>
    `;
}

function clearProductDatasetForm(){
    ["datasetIdInput", "datasetPathInput", "datasetSourceInput", "datasetVersionInput"].forEach(id=>{
        const el = $(id);
        if(el) el.value = "";
    });
    $("productDatasetsMsg").innerText = "";
}

async function loadProductDatasets(){
    $("productDatasetsMsg").innerText = "Loading datasets...";
    renderPanelState("productDatasetsTablePanel", "Loading product dataset registry...", "loading");
    try{
        const r = await req("GET", "/api/admin/product-datasets", undefined, { tenantHeaders: false });
        setJsonOutput("productDatasetsOut", r, true);
        if(r.ok && Array.isArray(r.data)){
            state.productDatasets = r.data;
            renderProductDatasetsTable("No product datasets registered yet.");
            $("productDatasetsMsg").innerText = `Loaded ${state.productDatasets.length} dataset(s)`;
            return r;
        }
        state.productDatasets = [];
        renderPanelState("productDatasetsTablePanel", r.data?.message || `Load datasets failed (${r.status})`, "error");
        $("productDatasetsMsg").innerText = r.data?.message || `Load datasets failed (${r.status})`;
        return r;
    }catch(err){
        state.productDatasets = [];
        renderPanelState("productDatasetsTablePanel", err.message || "Load datasets failed", "error");
        $("productDatasetsMsg").innerText = err.message || "Load datasets failed";
        throw err;
    }
}

async function registerProductDataset(){
    const datasetId = $("datasetIdInput")?.value?.trim();
    const path = $("datasetPathInput")?.value?.trim();
    const source = $("datasetSourceInput")?.value?.trim();
    const version = $("datasetVersionInput")?.value?.trim();

    if(!datasetId || !path){
        $("productDatasetsMsg").innerText = "Dataset ID and path are required";
        return null;
    }

    const body = { dataset_id: datasetId, path };
    if(source) body.source = source;
    if(version) body.version = version;

    const r = await req("POST", "/api/admin/product-datasets/register", body, { tenantHeaders: false });
    setJsonOutput("productDatasetsOut", r, true);
    if(r.ok){
        $("productDatasetsMsg").innerText = `Registered dataset ${datasetId}`;
        await loadProductDatasets();
        return r;
    }
    $("productDatasetsMsg").innerText = r.data?.message || `Register dataset failed (${r.status})`;
    return r;
}

async function viewProductDataset(id){
    if(!id){
        $("productDatasetsMsg").innerText = "Missing dataset id";
        return null;
    }

    const existing = state.productDatasets.find(dataset => productDatasetRowId(dataset) === id);
    const hasDetail = existing && (existing.manifest_path || existing.manifestPath || existing.content_hash || existing.contentHash);
    if(hasDetail){
        renderProductDatasetDetail(existing);
        return existing;
    }

    const r = await req("GET", `/api/admin/product-datasets/${encodeURIComponent(id)}`, undefined, { tenantHeaders: false });
    setJsonOutput("productDatasetsOut", r, true);
    if(r.ok){
        renderProductDatasetDetail(r.data);
        return r.data;
    }
    $("productDatasetsMsg").innerText = r.data?.message || `Load dataset detail failed (${r.status})`;
    return null;
}

async function assignProductDataset(id){
    if(!state.selectedTenant){
        $("productDatasetsMsg").innerText = "No tenant selected. Go to Tenant Management -> Tenants and click Select/Use tenant before assigning a dataset.";
        renderSelectedTenantNotice("productDatasetsTenantNotice");
        return null;
    }

    const dataset = state.productDatasets.find(item => productDatasetRowId(item) === id) || state.selectedProductDataset;
    const datasetId = productDatasetBusinessId(dataset) || id;
    if(!window.confirm(`Assign dataset ${datasetId} to tenant ${selectedTenantLabel()}?`)){
        return null;
    }

    const body = state.selectedTenant.code
        ? { tenant_code: state.selectedTenant.code }
        : { tenantId: state.selectedTenant.id };
    const r = await req("POST", `/api/admin/product-datasets/${encodeURIComponent(id)}/assign`, body, { tenantHeaders: false });
    setJsonOutput("productDatasetsOut", r, true);
    if(r.ok){
        renderProductDatasetAssignResult(r.data, datasetId);
        $("productDatasetsMsg").innerText = r.data?.message || `Assigned dataset ${datasetId}. Open KB Versions / Runtime Status to verify active KB.`;
        await loadProductDatasets();
        await Promise.allSettled([loadKbVersions(), loadActiveKbDirectory(), loadKbRuntimeStatus()]);
        return r;
    }
    $("productDatasetsMsg").innerText = r.data?.message || `Assign dataset failed (${r.status})`;
    return r;
}

async function deleteProductDataset(id){
    const dataset = state.productDatasets.find(item => productDatasetRowId(item) === id);
    const datasetId = productDatasetBusinessId(dataset) || id;
    if(!window.confirm(`Delete registry record for dataset ${datasetId}? Dataset files will not be deleted.`)){
        return null;
    }

    const r = await req("DELETE", `/api/admin/product-datasets/${encodeURIComponent(id)}`, undefined, { tenantHeaders: false });
    setJsonOutput("productDatasetsOut", r, true);
    if(r.ok){
        $("productDatasetsMsg").innerText = `Deleted registry record for ${datasetId}`;
        renderProductDatasetDetail(null);
        $("productDatasetAssignPanel")?.classList.add("hidden");
        await loadProductDatasets();
        return r;
    }
    $("productDatasetsMsg").innerText = r.data?.message || `Delete dataset record failed (${r.status})`;
    return r;
}

async function evictPlatformRuntime(tenantId){
    const params = new URLSearchParams({ tenantId });
    return req("POST", `/api/ops/runtime/evict?${params.toString()}`, undefined, { tenantHeaders: false });
}

/* ---------------- Knowledge Base ---------------- */
function requireSelectedTenant(messageId, panelId){
    if(state.selectedTenant){
        return state.selectedTenant;
    }
    const message = "No tenant selected. Go to Tenant Management -> Tenants and click Select/Use tenant.";
    if(messageId && $(messageId)) $(messageId).innerText = message;
    if(panelId) renderPanelState(panelId, message, "error");
    renderSelectedTenantNotices();
    return null;
}

function kbTenantField(name){
    const tenant = state.selectedTenant || {};
    return tenant[name] || tenant[name.replace(/_([a-z])/g, (_, c)=>c.toUpperCase())] || "";
}

function versionStatusBadge(status, active=false){
    if(active){
        return `<span class="status-badge status-completed">ACTIVE</span>`;
    }
    return renderDatasetStatusBadge(status);
}

function renderActiveKbDirectory(directory){
    const panel = $("activeKbDirectoryPanel");
    if(!panel) return;
    if(!directory){
        renderPanelState("activeKbDirectoryPanel", "Click Load active KB directory to inspect the selected tenant.", "empty");
        return;
    }

    const tenantKbDir = kbTenantField("kbDir") || kbTenantField("kb_dir");
    const tenantActiveVersion = kbTenantField("activeKbVersionId") || kbTenantField("active_kb_version_id");
    const rows = [
        ["Resolved KB dir", directory.kb_dir || directory.kbDir],
        ["Source", directory.source],
        ["Tenant kbDir", tenantKbDir],
        ["Active KB version ID", tenantActiveVersion || directory.version_id || directory.versionId],
        ["Resolved version ID", directory.version_id || directory.versionId],
        ["Resolved version tag", directory.version_tag || directory.versionTag],
        ["Fallback warning", directory.fallback_reason || directory.fallbackReason]
    ];

    const warning = directory.fallback_reason || directory.fallbackReason;
    panel.classList.remove("hidden");
    panel.innerHTML = `
        ${warning ? `<div class="inline-feedback error">Warning: ${escapeHtml(warning)}</div>` : ""}
        <div class="dataset-detail-grid kb-detail-grid">
            ${rows.map(([label, value]) => `
                <div class="dataset-detail-row">
                    <div class="muted">${escapeHtml(label)}</div>
                    <div class="dataset-detail-value">${escapeHtml(displayValue(value))}</div>
                </div>
            `).join("")}
        </div>
    `;
}

async function loadActiveKbDirectory(){
    if(!requireSelectedTenant("kbDirsMsg", "activeKbDirectoryPanel")) return null;
    $("kbDirsMsg").innerText = "Loading active KB directory...";
    renderPanelState("activeKbDirectoryPanel", "Loading active KB directory...", "loading");
    try{
        const r = await req("GET", "/api/kb/active-directory");
        if(r.ok){
            state.activeKbDirectory = r.data;
            renderActiveKbDirectory(r.data);
            $("kbDirsMsg").innerText = "Active KB directory loaded";
            return r;
        }
        renderPanelState("activeKbDirectoryPanel", r.data?.message || `Load active KB directory failed (${r.status})`, "error");
        $("kbDirsMsg").innerText = r.data?.message || `Load active KB directory failed (${r.status})`;
        return r;
    }catch(err){
        renderPanelState("activeKbDirectoryPanel", err.message || "Load active KB directory failed", "error");
        $("kbDirsMsg").innerText = err.message || "Load active KB directory failed";
        throw err;
    }
}

function renderKbVersionsTable(emptyMessage="Click Load KB versions to refresh this tenant."){
    const panel = $("kbVersionsTablePanel");
    if(!panel) return;
    const versions = Array.isArray(state.kbVersions) ? state.kbVersions : [];
    if(versions.length === 0){
        renderPanelState("kbVersionsTablePanel", emptyMessage, "empty");
        return;
    }
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <table class="table" id="kb-versions-table">
            <thead>
                <tr>
                    <th>Version</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Dataset</th>
                    <th>KB dir</th>
                    <th>Artifacts</th>
                    <th>Built at</th>
                    <th>Message</th>
                    <th>Active</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${versions.map(version => {
                    const id = version.id || "";
                    const active = Boolean(version.active);
                    const status = version.status || "-";
                    return `
                        <tr data-kb-version-id="${escapeHtml(id)}">
                            <td><b>${escapeHtml(version.version_tag || version.versionTag || "-")}</b><div class="muted">${escapeHtml(id)}</div></td>
                            <td>${versionStatusBadge(status)}</td>
                            <td>${escapeHtml(version.source_type || version.sourceType)}</td>
                            <td class="table-preview" title="${escapeHtml(version.dataset_id || version.datasetId || "")}">${escapeHtml(version.dataset_id || version.datasetId)}</td>
                            <td class="table-preview dataset-path-preview" title="${escapeHtml(version.kb_dir || version.kbDir || "")}">${escapeHtml(shortPreview(version.kb_dir || version.kbDir, 72))}</td>
                            <td>${escapeHtml(displayValue(version.artifact_count ?? version.artifactCount))}</td>
                            <td>${escapeHtml(fmtDateTime(version.built_at || version.builtAt) || "-")}</td>
                            <td class="table-preview" title="${escapeHtml(version.build_message || version.buildMessage || "")}">${escapeHtml(shortPreview(version.build_message || version.buildMessage, 64))}</td>
                            <td>${versionStatusBadge(status, active)}</td>
                            <td>
                                <div class="table-actions">
                                    <button class="secondary" data-action="kb-version-view">View</button>
                                    <button class="secondary" data-action="kb-version-publish" ${active || status !== "READY" ? "disabled" : ""}>Publish</button>
                                    <button class="danger" data-action="kb-version-archive" ${active || status === "BUILDING" || status === "ARCHIVED" ? "disabled" : ""}>Archive</button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}

function renderKbVersionDetail(version){
    const panel = $("kbVersionDetailPanel");
    if(!panel) return;
    if(!version){
        panel.classList.add("hidden");
        panel.innerHTML = "";
        return;
    }
    state.selectedKbVersion = version;
    const rows = [
        ["Version tag", version.version_tag || version.versionTag],
        ["Status", version.status],
        ["Source type", version.source_type || version.sourceType],
        ["Dataset ID", version.dataset_id || version.datasetId],
        ["KB dir", version.kb_dir || version.kbDir],
        ["Artifact count", version.artifact_count ?? version.artifactCount],
        ["Built at", fmtDateTime(version.built_at || version.builtAt)],
        ["Published at", fmtDateTime(version.published_at || version.publishedAt)],
        ["Created at", fmtDateTime(version.created_at || version.createdAt)],
        ["Active", boolLabel(Boolean(version.active))],
        ["Message", version.build_message || version.buildMessage]
    ];
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="card2 dataset-detail-card">
            <div class="drawer-header">
                <h3>KB version detail</h3>
                <button class="secondary" id="closeKbVersionDetail">Close</button>
            </div>
            <div class="dataset-detail-grid">
                ${rows.map(([label, value]) => `
                    <div class="dataset-detail-row">
                        <div class="muted">${escapeHtml(label)}</div>
                        <div class="dataset-detail-value">${escapeHtml(displayValue(value))}</div>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
    $("closeKbVersionDetail")?.addEventListener("click", ()=>{
        renderKbVersionDetail(null);
    });
}

async function loadKbVersions(){
    if(!requireSelectedTenant("kbVersionsMsg", "kbVersionsTablePanel")) return null;
    $("kbVersionsMsg").innerText = "Loading KB versions...";
    renderPanelState("kbVersionsTablePanel", "Loading KB versions...", "loading");
    try{
        const r = await req("GET", "/api/kb/versions");
        if(r.ok && Array.isArray(r.data)){
            state.kbVersions = r.data;
            renderKbVersionsTable("No KB versions found for this tenant.");
            $("kbVersionsMsg").innerText = `Loaded ${state.kbVersions.length} KB version(s)`;
            return r;
        }
        state.kbVersions = [];
        renderPanelState("kbVersionsTablePanel", r.data?.message || `Load KB versions failed (${r.status})`, "error");
        $("kbVersionsMsg").innerText = r.data?.message || `Load KB versions failed (${r.status})`;
        return r;
    }catch(err){
        state.kbVersions = [];
        renderPanelState("kbVersionsTablePanel", err.message || "Load KB versions failed", "error");
        $("kbVersionsMsg").innerText = err.message || "Load KB versions failed";
        throw err;
    }
}

async function publishKbVersion(id){
    if(!id || !requireSelectedTenant("kbVersionsMsg", "kbVersionsTablePanel")) return null;
    const version = state.kbVersions.find(item => item.id === id);
    const label = version?.version_tag || version?.versionTag || id;
    if(!window.confirm(`Publish KB version ${label} for tenant ${selectedTenantLabel()}?`)){
        return null;
    }
    $("kbVersionsMsg").innerText = "Publishing KB version...";
    const r = await req("POST", `/api/kb/versions/${encodeURIComponent(id)}/publish`);
    if(r.ok){
        $("kbVersionsMsg").innerText = "KB version published. Runtime was evicted by backend.";
        await Promise.allSettled([loadKbVersions(), loadActiveKbDirectory(), loadKbRuntimeStatus()]);
        return r;
    }
    $("kbVersionsMsg").innerText = r.data?.message || `Publish failed (${r.status})`;
    return r;
}

async function archiveKbVersion(id){
    if(!id || !requireSelectedTenant("kbVersionsMsg", "kbVersionsTablePanel")) return null;
    const version = state.kbVersions.find(item => item.id === id);
    const label = version?.version_tag || version?.versionTag || id;
    if(!window.confirm(`Archive KB version ${label}? Active and BUILDING versions cannot be archived.`)){
        return null;
    }
    $("kbVersionsMsg").innerText = "Archiving KB version...";
    const r = await req("POST", `/api/kb/versions/${encodeURIComponent(id)}/archive`);
    if(r.ok){
        $("kbVersionsMsg").innerText = "KB version archived";
        await loadKbVersions();
        return r;
    }
    $("kbVersionsMsg").innerText = r.data?.message || `Archive failed (${r.status})`;
    return r;
}

function renderKbSourceUrls(data){
    const panel = $("kbSourceUrlsPanel");
    if(!panel) return;
    if(!data){
        renderPanelState("kbSourceUrlsPanel", "Click Load source URLs to read raw_urls.txt for the selected tenant.", "empty");
        return;
    }
    const urls = Array.isArray(data.urls) ? data.urls : [];
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="card2 dataset-detail-card">
            <div><b>Source URLs</b></div>
            <div class="muted">Tenant: ${escapeHtml(data.tenantId || data.tenant_id || state.selectedTenant?.id)}</div>
            ${urls.length
                ? `<ul class="kb-url-list">${urls.map(url => `<li>${escapeHtml(url)}</li>`).join("")}</ul>`
                : `<div class="panel-state empty">No source URLs found in raw_urls.txt.</div>`}
        </div>
    `;
}

async function loadKbSourceUrls(){
    if(!requireSelectedTenant("kbRebuildMsg", "kbSourceUrlsPanel")) return null;
    $("kbRebuildMsg").innerText = "Loading source URLs...";
    renderPanelState("kbSourceUrlsPanel", "Loading source URLs...", "loading");
    try{
        const r = await req("GET", "/api/kb/source-urls");
        if(r.ok){
            state.kbSourceUrls = r.data;
            renderKbSourceUrls(r.data);
            $("kbRebuildMsg").innerText = `Loaded ${(r.data?.urls || []).length} source URL(s)`;
            return r;
        }
        renderPanelState("kbSourceUrlsPanel", r.data?.message || `Load source URLs failed (${r.status})`, "error");
        $("kbRebuildMsg").innerText = r.data?.message || `Load source URLs failed (${r.status})`;
        return r;
    }catch(err){
        renderPanelState("kbSourceUrlsPanel", err.message || "Load source URLs failed", "error");
        $("kbRebuildMsg").innerText = err.message || "Load source URLs failed";
        throw err;
    }
}

function renderKbRebuildResponse(data){
    const panel = $("kbRebuildStatusPanel");
    if(!panel) return;
    if(!data){
        renderPanelState("kbRebuildStatusPanel", "No standalone rebuild status endpoint exists. Use Rebuild KB to see the latest command response, or Monitoring for snapshot history.", "empty");
        return;
    }
    const rows = [
        ["Success", boolLabel(data.success)],
        ["Status", data.lastRebuildStatus],
        ["Started at", fmtDateTime(data.lastRebuildStartedAt)],
        ["Finished at", fmtDateTime(data.lastRebuildFinishedAt || data.rebuiltAt)],
        ["Message", data.lastRebuildMessage || data.message]
    ];
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="dataset-detail-grid kb-detail-grid">
            ${rows.map(([label, value]) => `
                <div class="dataset-detail-row">
                    <div class="muted">${escapeHtml(label)}</div>
                    <div class="dataset-detail-value">${escapeHtml(displayValue(value))}</div>
                </div>
            `).join("")}
        </div>
    `;
}

async function rebuildKb(){
    if(!requireSelectedTenant("kbRebuildMsg", "kbRebuildStatusPanel")) return null;
    if(!window.confirm(`Rebuild KB for tenant ${selectedTenantLabel()}? This can run crawler/build tooling and may take a while.`)){
        return null;
    }
    $("kbRebuildMsg").innerText = "Rebuilding KB...";
    renderPanelState("kbRebuildStatusPanel", "Rebuild request is running...", "loading");
    try{
        const r = await req("POST", "/api/kb/rebuild");
        if(r.ok){
            renderKbRebuildResponse(r.data);
            $("kbRebuildMsg").innerText = r.data?.message || "KB rebuild finished";
            await Promise.allSettled([loadKbVersions(), loadActiveKbDirectory(), loadKbRuntimeStatus()]);
            return r;
        }
        renderPanelState("kbRebuildStatusPanel", r.data?.message || `Rebuild failed (${r.status})`, "error");
        $("kbRebuildMsg").innerText = r.data?.message || `Rebuild failed (${r.status})`;
        return r;
    }catch(err){
        renderPanelState("kbRebuildStatusPanel", err.message || "Rebuild failed", "error");
        $("kbRebuildMsg").innerText = err.message || "Rebuild failed";
        throw err;
    }
}

function renderKbRuntimeStatus(status){
    const panel = $("kbRuntimeStatusPanel");
    if(!panel) return;
    if(!status){
        renderPanelState("kbRuntimeStatusPanel", "Click Load runtime status to inspect the selected tenant runtime.", "empty");
        return;
    }
    const desired = status.desired || {};
    const running = status.running || {};
    const inSync = status.in_sync ?? status.inSync;
    const syncBadge = inSync === true
        ? '<span class="ops-badge ops-badge-success">IN SYNC</span>'
        : (inSync === false ? '<span class="ops-badge ops-badge-progress">OUT OF SYNC / NOT RUNNING</span>' : '<span class="ops-badge ops-badge-neutral">UNKNOWN</span>');
    const rows = [
        ["Desired KB dir", desired.kb_dir || desired.kbDir],
        ["Desired source", desired.source],
        ["Desired version", desired.version_tag || desired.versionTag],
        ["Desired fallback", desired.fallback_reason || desired.fallbackReason],
        ["Runtime mode", running.mode],
        ["Runtime KB dir", running.kb_dir || running.kbDir],
        ["Runtime source", running.source],
        ["Runtime version", running.version_tag || running.versionTag],
        ["Process alive", boolLabel(running.process_alive ?? running.processAlive)],
        ["PID", running.pid],
        ["Started at", fmtDateTime(running.started_at || running.startedAt)],
        ["Runtime in sync", boolLabel(inSync)],
        ["Note", running.note]
    ];
    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div class="ops-summary-copy">${syncBadge}</div>
        ${inSync === false ? `<div class="inline-feedback error">Runtime is not using the selected tenant's desired KB yet. Evict runtime or make a tenant chat request to reload.</div>` : ""}
        <div class="dataset-detail-grid kb-detail-grid">
            ${rows.map(([label, value]) => `
                <div class="dataset-detail-row">
                    <div class="muted">${escapeHtml(label)}</div>
                    <div class="dataset-detail-value">${escapeHtml(displayValue(value))}</div>
                </div>
            `).join("")}
        </div>
    `;
}

async function loadKbRuntimeStatus(){
    if(!requireSelectedTenant("kbRuntimeMsg", "kbRuntimeStatusPanel")) return null;
    $("kbRuntimeMsg").innerText = "Loading runtime status...";
    renderPanelState("kbRuntimeStatusPanel", "Loading runtime status...", "loading");
    try{
        const r = await req("GET", "/api/kb/runtime-status");
        if(r.ok){
            state.kbRuntimeStatus = r.data;
            renderKbRuntimeStatus(r.data);
            $("kbRuntimeMsg").innerText = "Runtime status loaded";
            return r;
        }
        renderPanelState("kbRuntimeStatusPanel", r.data?.message || `Load runtime status failed (${r.status})`, "error");
        $("kbRuntimeMsg").innerText = r.data?.message || `Load runtime status failed (${r.status})`;
        return r;
    }catch(err){
        renderPanelState("kbRuntimeStatusPanel", err.message || "Load runtime status failed", "error");
        $("kbRuntimeMsg").innerText = err.message || "Load runtime status failed";
        throw err;
    }
}

async function evictSelectedTenantRuntime(){
    const tenant = requireSelectedTenant("kbRuntimeMsg", "kbRuntimeStatusPanel");
    if(!tenant) return null;
    if(!window.confirm(`Evict runtime for tenant ${selectedTenantLabel()}?`)){
        return null;
    }
    $("kbRuntimeMsg").innerText = "Evicting runtime...";
    const r = await evictPlatformRuntime(tenant.id);
    if(r.ok){
        $("kbRuntimeMsg").innerText = "Runtime evicted";
        await loadKbRuntimeStatus();
        return r;
    }
    $("kbRuntimeMsg").innerText = r.data?.message || `Evict runtime failed (${r.status})`;
    return r;
}

function clearTenantScopedKbState(){
    state.activeKbDirectory = null;
    state.kbVersions = [];
    state.selectedKbVersion = null;
    state.kbSourceUrls = null;
    state.kbRuntimeStatus = null;
    renderActiveKbDirectory(null);
    renderKbVersionsTable();
    renderKbVersionDetail(null);
    renderKbSourceUrls(null);
    renderKbRebuildResponse(null);
    renderKbRuntimeStatus(null);
}

/* ---------------- Tabs ---------------- */
function findPrimaryGroupForTab(tabName){
    return Object.keys(PRIMARY_GROUPS).find(groupKey => PRIMARY_GROUPS[groupKey].includes(tabName)) || "dashboard";
}

function updateOverview(){
    const selectedTenant = $("overviewSelectedTenant");
    if(!selectedTenant) return;
    const tenant = state.selectedTenant;
    selectedTenant.innerText = tenant ? (tenant.name || tenant.code || tenant.id) : "No tenant selected";
}

function selectedTenantLabel(){
    const tenant = state.selectedTenant;
    if(!tenant) return "";
    return tenant.name || tenant.code || tenant.id;
}

function renderSelectedTenantNotice(containerId){
    const el = $(containerId);
    if(!el) return;
    const label = selectedTenantLabel();
    el.classList.toggle("warning", !label);
    const noTenantMessage = containerId === "productDatasetsTenantNotice"
        ? `No tenant selected. Go to Tenant Management &rarr; Tenants and click Select/Use tenant before assigning a dataset.`
        : `No tenant selected. Go to Tenant Management &rarr; Tenants and click Select/Use tenant.`;
    el.innerHTML = label
        ? `Using selected tenant: <b>${escapeHtml(label)}</b>`
        : noTenantMessage;
}

function renderSelectedTenantNotices(){
    [
        "membersTenantNotice",
        "botsTenantNotice",
        "bindingsTenantNotice",
        "leadsTenantNotice",
        "purchaseRequestsTenantNotice",
        "kbDirsTenantNotice",
        "kbVersionsTenantNotice",
        "kbRebuildTenantNotice",
        "kbRuntimeTenantNotice",
        "productDatasetsTenantNotice"
    ].forEach(renderSelectedTenantNotice);
    updateOverview();
}

function clearTenantScopedBotState(){
    state.bots = [];
    state.selectedBot = null;
    state.editingBotId = null;
    renderBotSelect();
    renderChatbotEditSelect();
    renderChatbotsTable();
    populateBotForm(null);
}

function setPrimaryTab(groupKey, preferredSubTab){
    const groupTabs = PRIMARY_GROUPS[groupKey] || PRIMARY_GROUPS.dashboard;
    const target = preferredSubTab && groupTabs.includes(preferredSubTab)
        ? preferredSubTab
        : (groupTabs.includes(state.currentTab) ? state.currentTab : DEFAULT_SUB_TABS[groupKey]);

    document.querySelectorAll(".primary-tab").forEach(b=>{
        b.classList.toggle("active", b.dataset.group === groupKey);
    });
    document.querySelectorAll(".sub-tab").forEach(b=>{
        const visible = b.dataset.group === groupKey;
        b.classList.toggle("hidden", !visible);
        b.classList.toggle("active", visible && b.dataset.tab === target);
    });

    if(target && state.currentTab !== target){
        setTab(target, { syncPrimary: false });
    }
}

function setTab(name, opts = {}){
    state.currentTab = name;
    renderSelectedTenantNotices();
    if(name === "overview"){
        updateOverview();
    }

    document.querySelectorAll(".sub-tab").forEach(b=>{
        b.classList.toggle("active", b.dataset.tab === name);
    });
    // ✅ add "leads"
    ALL_ADMIN_TABS.forEach(t=>{
        const el = $("tab-"+t);
        if(el) el.classList.toggle("hidden", t !== name);
    });

    if(opts.syncPrimary !== false){
        setPrimaryTab(findPrimaryGroupForTab(name), name);
    }

    if(name === "onboarding"){
        loadOnboardingRequests().catch(()=>{});
    }
    // optional: auto load leads when open tab
    if(name === "leads"){
        if(state.selectedTenant){
            refreshLeads().catch(()=>{});
        } else {
            renderLeads([]);
        }
    }
    if(name === "monitor" && $("systemStatusSummary") && !$("systemStatusSummary").innerHTML.trim()){
        renderPanelState("systemStatusSummary", "Click Load platform ops to refresh status.", "empty");
    }
    if(name === "kb-dirs" && $("activeKbDirectoryPanel") && !$("activeKbDirectoryPanel").innerHTML.trim()){
        renderActiveKbDirectory(null);
    }
    if(name === "kb-versions" && $("kbVersionsTablePanel") && !$("kbVersionsTablePanel").innerHTML.trim()){
        renderKbVersionsTable();
    }
    if(name === "kb-rebuild"){
        if($("kbSourceUrlsPanel") && !$("kbSourceUrlsPanel").innerHTML.trim()){
            renderKbSourceUrls(null);
        }
        if($("kbRebuildStatusPanel") && !$("kbRebuildStatusPanel").innerHTML.trim()){
            renderKbRebuildResponse(null);
        }
    }
    if(name === "runtime" && $("kbRuntimeStatusPanel") && !$("kbRuntimeStatusPanel").innerHTML.trim()){
        renderKbRuntimeStatus(null);
    }
    if(name === "product-datasets" && $("productDatasetsTablePanel") && !$("productDatasetsTablePanel").innerHTML.trim()){
        renderPanelState("productDatasetsTablePanel", "Click Load datasets to refresh product dataset registry.", "empty");
    }
}
document.querySelectorAll(".primary-tab").forEach(b=>{
    b.addEventListener("click", ()=> setPrimaryTab(b.dataset.group));
});
document.querySelectorAll(".sub-tab").forEach(b=>{
    b.addEventListener("click", ()=> setTab(b.dataset.tab));
});
document.querySelectorAll("[data-nav-tab]").forEach(b=>{
    b.addEventListener("click", ()=> setTab(b.dataset.navTab));
});

/* ---------------- Onboarding requests ---------------- */
function onboardingStatusBadge(status){
    const normalized = (status || "NEW").toUpperCase();
    return `<span class="ops-badge ops-badge-neutral">${normalized}</span>`;
}

function slugifyTenantCode(value){
    return (value || "tenant")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        || `tenant_${Math.random().toString(16).slice(2, 8)}`;
}

function generatedTemporaryPassword(){
    return `Temp@${Math.random().toString(36).slice(2, 8)}${Math.floor(100 + Math.random() * 900)}`;
}

async function loadOnboardingRequests(){
    const status = $("onboardingStatusFilter")?.value || "";
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const r = await req("GET", `/api/admin/onboarding-requests${query}`, undefined, { tenantHeaders:false });
    setJsonOutput("onboardingOut", r, true);
    if(!r.ok){
        $("onboardingMsg").innerText = r.status === 401
            ? "Phiên đăng nhập đã hết hạn. Đăng nhập lại rồi bấm Load requests."
            : (r.data?.message || `Load failed (${r.status})`);
        return;
    }
    state.onboardingRequests = Array.isArray(r.data) ? r.data : [];
    renderOnboardingRequests(state.onboardingRequests);
    $("onboardingMsg").innerText = `Loaded ${state.onboardingRequests.length} request(s)`;
}

function renderOnboardingRequests(items){
    const tbody = document.querySelector("#onboarding-table tbody");
    if(!tbody) return;
    tbody.innerHTML = "";
    if(!Array.isArray(items) || items.length === 0){
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 5;
        td.className = "muted";
        td.textContent = "No onboarding requests found.";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    for(const item of items){
        const tr = document.createElement("tr");
        tr.dataset.id = item.id;

        const storeTd = document.createElement("td");
        storeTd.innerHTML = `<b></b><div class="muted"></div>`;
        storeTd.querySelector("b").textContent = item.storeName || "-";
        storeTd.querySelector(".muted").textContent = item.websiteUrl || item.note || "";

        const contactTd = document.createElement("td");
        contactTd.innerHTML = `<b></b><div class="muted"></div><div class="muted"></div>`;
        contactTd.querySelector("b").textContent = item.contactName || "-";
        contactTd.querySelectorAll(".muted")[0].textContent = item.email || "";
        contactTd.querySelectorAll(".muted")[1].textContent = item.phone || "";

        const statusTd = document.createElement("td");
        statusTd.innerHTML = onboardingStatusBadge(item.status);

        const createdTd = document.createElement("td");
        createdTd.textContent = fmtDateTime(item.createdAt);

        const actionsTd = document.createElement("td");
        const canProvision = (item.status || "").toUpperCase() === "APPROVED";
        actionsTd.innerHTML = `
            <button class="secondary" data-action="contacted">Contacted</button>
            <button class="secondary" data-action="approved">Approve</button>
            <button class="secondary" data-action="rejected">Reject</button>
            <button data-action="select-provision" ${canProvision ? "" : "disabled"} title="${canProvision ? "Create tenant and owner account" : "Approve this request before provisioning"}">Provision</button>
        `;

        tr.append(storeTd, contactTd, statusTd, createdTd, actionsTd);
        tbody.appendChild(tr);
    }
}

async function updateOnboardingStatus(requestId, status){
    const current = state.onboardingRequests.find(item => item.id === requestId);
    $("onboardingMsg").innerText = `Updating request to ${status}...`;
    const r = await req(
        "PATCH",
        `/api/admin/onboarding-requests/${encodeURIComponent(requestId)}/status`,
        { status, adminNote: current?.adminNote || "" },
        { tenantHeaders:false }
    );
    setJsonOutput("onboardingOut", r, true);
    if(!r.ok){
        $("onboardingMsg").innerText = r.data?.message || `Update failed (${r.status})`;
        return;
    }
    $("onboardingMsg").innerText = `Request marked ${status}`;
    await loadOnboardingRequests();
}

function selectOnboardingForProvision(requestId){
    const item = state.onboardingRequests.find(r => r.id === requestId);
    if(!item){
        $("onboardingMsg").innerText = "Request not found. Reload requests first.";
        return;
    }
    state.selectedOnboardingRequestId = requestId;
    $("onboardingProvisionPanel")?.classList.remove("hidden");
    $("onboardingSelectedSummary").textContent =
        `${item.storeName || "-"} | ${item.contactName || "-"} | ${item.email || "-"} | status ${item.status || "NEW"}`;
    $("onboardingTenantCode").value = slugifyTenantCode(item.storeName);
    $("onboardingTenantName").value = item.storeName || "";
    $("onboardingOwnerEmail").value = item.email || "";
    $("onboardingOwnerDisplayName").value = item.contactName || "";
    $("onboardingOwnerPassword").value = generatedTemporaryPassword();
    $("onboardingAdminNote").value = item.adminNote || "";
    $("onboardingProvisionMsg").innerText = item.status === "APPROVED"
        ? "Ready to provision."
        : "Approve this request before provisioning.";
}

async function provisionSelectedOnboardingRequest(){
    const requestId = state.selectedOnboardingRequestId;
    if(!requestId){
        $("onboardingProvisionMsg").innerText = "Select a request first.";
        return;
    }
    const body = {
        tenantCode: $("onboardingTenantCode").value.trim(),
        tenantName: $("onboardingTenantName").value.trim(),
        kbDir: $("onboardingKbDir").value.trim(),
        ownerEmail: $("onboardingOwnerEmail").value.trim(),
        ownerDisplayName: $("onboardingOwnerDisplayName").value.trim(),
        ownerPassword: $("onboardingOwnerPassword").value.trim(),
        adminNote: $("onboardingAdminNote").value.trim()
    };
    if(!body.tenantCode || !body.tenantName || !body.ownerEmail || !body.ownerPassword){
        $("onboardingProvisionMsg").innerText = "Tenant code, tenant name, owner email and temporary password are required.";
        return;
    }

    $("onboardingProvisionMsg").innerText = "Provisioning...";
    const r = await req(
        "POST",
        `/api/admin/onboarding-requests/${encodeURIComponent(requestId)}/provision`,
        body,
        { tenantHeaders:false }
    );
    setJsonOutput("onboardingOut", r, true);
    if(!r.ok){
        $("onboardingProvisionMsg").innerText = r.data?.message || `Provision failed (${r.status})`;
        return;
    }
    $("onboardingProvisionMsg").innerText = "Tenant and owner account created. Share the temporary password with the owner through your trusted channel.";
    await loadOnboardingRequests();
    await loadTenants(false, r.data?.tenantId || "");
}

document.querySelector("#onboarding-table")?.addEventListener("click", async (e)=>{
    const btn = e.target.closest("button");
    if(!btn) return;
    const requestId = btn.closest("tr")?.dataset?.id;
    if(!requestId) return;
    const action = btn.dataset.action;
    if(action === "select-provision"){
        selectOnboardingForProvision(requestId);
        return;
    }
    const statusByAction = {
        contacted: "CONTACTED",
        approved: "APPROVED",
        rejected: "REJECTED"
    };
    if(statusByAction[action]){
        try {
            await updateOnboardingStatus(requestId, statusByAction[action]);
        } catch (err) {
            console.error(err);
            $("onboardingMsg").innerText = err.message || "Update failed";
        }
    }
});

$("loadOnboardingRequests")?.addEventListener("click", () => loadOnboardingRequests().catch(err => {
    console.error(err);
    $("onboardingMsg").innerText = err.message || "Load failed";
}));
$("clearOnboardingOut")?.addEventListener("click", () => $("onboardingOut").innerText = "");
$("closeOnboardingProvision")?.addEventListener("click", () => $("onboardingProvisionPanel").classList.add("hidden"));
$("provisionOnboardingRequest")?.addEventListener("click", () => provisionSelectedOnboardingRequest().catch(err => {
    console.error(err);
    $("onboardingProvisionMsg").innerText = err.message || "Provision failed";
}));

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
    const previousTenantId = state.selectedTenant?.id || "";
    const t = state.tenants.find(x => x.id === tenantId);
    if(!t){
        state.selectedTenant = null;
        clearTenantScopedBotState();
        clearTenantScopedKbState();
        renderSelectedTenantNotices();
        $("selectedTenantName").innerText = "—";
        return;
    }
    state.selectedTenant = t;

    // auto-fill headers (ưu tiên apiKey)
    $("apiKey").value = t.apiKey || "";
    $("tenantId").value = t.id;

    $("selectedTenantName").innerText = t.name || t.code || t.id;
    if(previousTenantId && previousTenantId !== t.id){
        clearTenantScopedBotState();
        clearTenantScopedKbState();
    }
    renderSelectedTenantNotices();
    saveCfg();
    showMsg("tenantsMsg", `Da chon tenant ${t.name || t.code || t.id} cho cac tab tiep theo`, 2200);
}

function getSelectedTenantIdForMembers(){
    return state.selectedTenant?.id || "";
}

function renderTenantsTable(){
    const panel = $("tenantsTablePanel");
    if(!panel) return;

    const filter = ($("tenantFilter")?.value || "").trim().toLowerCase();
    const rows = (Array.isArray(state.tenants) ? state.tenants : [])
        .filter(tenant => tenantMatchesFilter(tenant, filter));

    if(rows.length === 0){
        panel.innerHTML = `
            <table class="table" id="tenants-table">
                <tbody>
                    <tr><td><div class="panel-state empty">No tenants found.</div></td></tr>
                </tbody>
            </table>
        `;
        renderSelectedTenantNotices();
        return;
    }

    panel.innerHTML = `
        <table class="table" id="tenants-table">
            <thead>
                <tr>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>API key</th>
                    <th>KB dir</th>
                    <th>Active KB version</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(tenant => {
                    const activeKbVersionId = tenant.activeKbVersionId || tenant.active_kb_version_id;
                    const createdAt = tenant.createdAt || tenant.created_at;
                    return `
                        <tr data-tenant-id="${escapeHtml(tenant.id)}">
                            <td><b>${escapeHtml(tenant.code)}</b><div class="muted">${escapeHtml(tenant.id)}</div></td>
                            <td>${escapeHtml(tenant.name)}</td>
                            <td>${renderStatusBadge(tenant.status)}</td>
                            <td>${escapeHtml(maskSecret(tenant.apiKey || tenant.api_key))}</td>
                            <td class="table-preview" title="${escapeHtml(tenant.kbDir || tenant.kb_dir || "")}">${escapeHtml(tenant.kbDir || tenant.kb_dir)}</td>
                            <td class="table-preview" title="${escapeHtml(activeKbVersionId || "")}">${escapeHtml(activeKbVersionId)}</td>
                            <td>${escapeHtml(fmtDateTime(createdAt) || "-")}</td>
                            <td>
                                <div class="table-actions">
                                    <button class="secondary" data-action="tenant-use">Select/Use tenant</button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}

function renderChatbotsTable(){
    const panel = $("botsTablePanel");
    if(!panel) return;

    const filter = ($("botFilter")?.value || "").trim().toLowerCase();
    const rows = (Array.isArray(state.bots) ? state.bots : [])
        .filter(bot => botMatchesFilter(bot, filter));

    if(rows.length === 0){
        panel.innerHTML = `
            <table class="table" id="chatbots-table">
                <tbody>
                    <tr><td><div class="panel-state empty">No chatbots for selected tenant.</div></td></tr>
                </tbody>
            </table>
        `;
        return;
    }

    panel.innerHTML = `
        <table class="table" id="chatbots-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Tenant</th>
                    <th>Channel</th>
                    <th>Provider</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Persona</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(bot => {
                    const tenantId = bot.tenantId || bot.tenant_id || state.selectedTenant?.id;
                    return `
                        <tr data-bot-id="${escapeHtml(bot.id)}">
                            <td class="table-preview" title="${escapeHtml(bot.id)}">${escapeHtml(bot.id)}</td>
                            <td><b>${escapeHtml(bot.name)}</b></td>
                            <td>${escapeHtml(findTenantLabel(tenantId))}</td>
                            <td>${escapeHtml(bot.channel)}</td>
                            <td>${escapeHtml(bot.provider)}</td>
                            <td>${escapeHtml(bot.mode)}</td>
                            <td>${renderStatusBadge(bot.status || "ACTIVE")}</td>
                            <td class="table-preview" title="${escapeHtml(shortPreview(bot.persona, 240))}">${escapeHtml(shortPreview(bot.persona))}</td>
                            <td>
                                <div class="table-actions">
                                    <button class="secondary" data-action="bot-edit">Edit</button>
                                    <button class="danger" data-action="bot-delete">Delete</button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
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

function normalizePersonaInput(value){
    const raw = (value || "").trim();
    if(!raw) return "{}";

    if(raw.startsWith("{") || raw.startsWith("[")){
        try{
            JSON.parse(raw);
            return raw;
        }catch(e){
            throw new Error("Persona must be valid JSON, or enter plain text without { }.");
        }
    }

    return JSON.stringify({ note: raw });
}

function botPayloadFromForm(){
    const name = $("botName").value.trim();
    const channel = $("botChannel").value.trim();
    const personaJson = normalizePersonaInput($("botPersona").value);
    const responseStyle = $("botResponseStyle").value.trim() || "natural";
    const provider = $("botProvider").value.trim() || "local";

    if(!name || !channel){
        throw new Error("Thiáº¿u bot name hoáº·c channel");
    }

    if(!provider){
        throw new Error("Provider is required");
    }

    // Provider is system-level for Claude, no per-chatbot config fields
    return {
        name,
        channel,
        personaJson,
        responseStyle,
        provider
    };
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
        return;
    }

    state.editingBotId = bot.id;
    $("chatbotSelectEdit").value = bot.id;
    $("botName").value = bot.name || "";
    $("botChannel").value = bot.channel || "telegram";
    $("botPersona").value = bot.persona ? JSON.stringify(bot.persona) : "";
    $("botResponseStyle").value = bot.responseStyle || "natural";
    $("botProvider").value = bot.provider || "local";
}

/* ---------------- Helpers ---------------- */
function getCurrentTenantId(){
    return state.selectedTenant?.id || "";
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
    const apiKey = $("tenantApiKey")?.value?.trim();
    const kbDir = $("tenantKbDir")?.value?.trim();
    const status = $("tenantStatus")?.value?.trim();
    if(!code || !name){
        $("tenantsMsg").innerText = "Thiếu code hoặc name";
        return;
    }

    // Endpoint đúng theo code bạn gửi: /api/admin/tenants (WebConfig exclude)
    const r = await req("POST", "/api/admin/tenants", { code, name, apiKey, kbDir, status }, { tenantHeaders:false });
    setJsonOutput("tenantsOut", r, true);

    // refresh list ngay để chọn tenant
    await loadTenants(true);
});

async function loadTenants(autoPickFirst=false){
    $("tenantsMsg").innerText = "Loading tenants...";
    renderTenantsTable();
    const r = await req("GET", "/api/admin/tenants", undefined, { tenantHeaders:false });
    setJsonOutput("tenantsOut", r, true);

    if(r.ok && Array.isArray(r.data)){
        state.tenants = r.data;
        renderTenantsTable();

        if(autoPickFirst && state.tenants.length){
            applyTenantById(state.tenants[0].id);
        }
        $("tenantsMsg").innerText = `Loaded ${state.tenants.length} tenant(s)`;
    } else {
        state.tenants = [];
        renderTenantsTable();
        $("tenantsMsg").innerText = r.data?.message || `Load tenants failed (${r.status})`;
    }
}
$("loadTenants").addEventListener("click", ()=> loadTenants(false));
$("clearTenantsOut").addEventListener("click", ()=> $("tenantsOut").innerText = "");
$("tenantFilter")?.addEventListener("input", renderTenantsTable);
$("tenantsTablePanel")?.addEventListener("click", (e)=>{
    const btn = e.target.closest("button");
    if(!btn || btn.dataset.action !== "tenant-use") return;
    const tenantId = btn.closest("tr")?.dataset?.tenantId;
    if(!tenantId) return;
    applyTenantById(tenantId);
});

/* ---------------- Chatbots ---------------- */
$("useTenantBots")?.addEventListener("click", async ()=>{
    const id = state.selectedTenant?.id || "";
    if(!id){ showMsg("botsMsg", "Chọn tenant trước"); return; }
    applyTenantById(id);
    showMsg("botsMsg", "Tenant applied");
});

$("createBot").addEventListener("click", async (event)=>{
    $("botsMsg").innerText = "";

    if(!state.selectedTenant){
        $("botsMsg").innerText = "Chưa chọn tenant";
        return;
    }

    setButtonLoading(event.currentTarget, true, "Creating...");
    try{
        const payload = botPayloadFromForm();
        const r = await req("POST", "/api/chatbots", payload);
        setJsonOutput("botsOut", r, true);

        if(!r.ok){
            showMsg("botsMsg", r.data?.message || `Create failed (${r.status})`);
            return;
        }

        await loadBots(true);
        populateBotForm(r.data);
        showMsg("botsMsg", "Chatbot created");
    }catch(err){
        $("botsMsg").innerText = err.message;
    }finally{
        setButtonLoading(event.currentTarget, false);
    }
});

$("saveBot").addEventListener("click", async (event)=>{
    $("botsMsg").innerText = "";

    if(!state.selectedTenant){
        $("botsMsg").innerText = "Chưa chọn tenant";
        return;
    }
    if(!state.editingBotId){
        $("botsMsg").innerText = "Load a chatbot first";
        return;
    }

    setButtonLoading(event.currentTarget, true, "Saving...");
    try{
        const payload = botPayloadFromForm();
        const r = await req("PUT", `/api/chatbots/${state.editingBotId}`, payload);
        setJsonOutput("botsOut", r, true);

        if(!r.ok){
            showMsg("botsMsg", r.data?.message || `Save failed (${r.status})`);
            return;
        }

        await loadBots(true);
        populateBotForm(r.data);
        showMsg("botsMsg", "Chatbot saved");
    }catch(err){
        $("botsMsg").innerText = err.message;
    }finally{
        setButtonLoading(event.currentTarget, false);
    }
});

async function deleteBotById(botId, button=null){
    $("botsMsg").innerText = "";

    if(!state.selectedTenant){
        clearTenantScopedBotState();
        renderSelectedTenantNotices();
        $("botsMsg").innerText = "Chua chon tenant";
        return;
    }

    if(!botId){
        $("botsMsg").innerText = "Select a chatbot first";
        return;
    }

    const bot = state.bots.find(x => x.id === botId);
    const label = bot ? `${bot.name} [${bot.channel}]` : botId;
    if(!window.confirm(`Delete chatbot "${label}"? This also removes its bindings and conversations.`)){
        return;
    }

    setButtonLoading(button, true, "Deleting...");
    try{
        const r = await req("DELETE", `/api/chatbots/${botId}`);
        setJsonOutput("botsOut", r, true);

        if(r.ok){
            populateBotForm(null);
            await loadBots(true);
            showMsg("botsMsg", "Chatbot deleted");
        } else {
            showMsg("botsMsg", r.data?.message || `Delete failed (${r.status})`);
        }
    }catch(err){
        $("botsMsg").innerText = err.message;
    }finally{
        setButtonLoading(button, false);
    }
}

$("deleteBot").addEventListener("click", async (event)=>{
    const botId = state.editingBotId || $("chatbotSelectEdit").value;
    await deleteBotById(botId, event.currentTarget);
});

async function loadBots(silent=false){
    $("botsMsg").innerText = "";
    if(!state.selectedTenant){
        clearTenantScopedBotState();
        renderSelectedTenantNotices();
        if(!silent) $("botsMsg").innerText = "Chưa chọn tenant (Use tenant)";
        return;
    }

    state.bots = [];
    if(!silent) $("botsMsg").innerText = "Loading chatbots...";
    renderChatbotsTable();
    let r;
    try{
        r = await req("GET", "/api/chatbots");
        setJsonOutput("botsOut", r, true);
    }catch(err){
        state.bots = [];
        renderChatbotsTable();
        if(!silent) $("botsMsg").innerText = err.message || "Load chatbots failed";
        return null;
    }

    if(r.ok && Array.isArray(r.data)){
        state.bots = r.data;
        if(!silent) $("botsMsg").innerText = `Loaded ${state.bots.length} chatbot(s)`;
    } else {
        state.bots = [];
        if(!silent) $("botsMsg").innerText = r.data?.message || `Load chatbots failed (${r.status})`;
    }

    // Also refresh bot dropdown in Bindings
    renderBotSelect();
    renderChatbotEditSelect();
    renderChatbotsTable();

    if(state.editingBotId){
        const editingBot = state.bots.find(x => x.id === state.editingBotId);
        populateBotForm(editingBot || null);
    }
    return r;
}

$("loadBots").addEventListener("click", (event)=> withButtonLoading(event.currentTarget, "Loading...", ()=> loadBots(false)));
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
$("botFilter")?.addEventListener("input", renderChatbotsTable);
$("botsTablePanel")?.addEventListener("click", async (e)=>{
    const btn = e.target.closest("button");
    if(!btn) return;
    const botId = btn.closest("tr")?.dataset?.botId;
    if(!botId) return;
    const bot = state.bots.find(x => String(x.id) === String(botId));
    if(!bot){
        showMsg("botsMsg", "Load chatbots first");
        return;
    }
    if(btn.dataset.action === "bot-edit"){
        populateBotForm(bot);
        showMsg("botsMsg", "Chatbot loaded into form");
        return;
    }
    if(btn.dataset.action === "bot-delete"){
        populateBotForm(bot);
        await deleteBotById(botId, btn);
    }
});

function findTenantLabel(tenantId){
    const tenant = state.tenants.find(t => String(t.id) === String(tenantId));
    if(!tenant) return displayValue(tenantId);
    return `${tenant.name || tenant.code || tenant.id}`;
}

function findBotLabel(botId){
    const bot = state.bots.find(b => String(b.id) === String(botId));
    if(!bot) return displayValue(botId);
    return `${bot.name || bot.id}${bot.channel ? " [" + bot.channel + "]" : ""}`;
}

function renderTokenState(binding){
    if(binding?.token_preview){
        return escapeHtml(binding.token_preview);
    }
    if(binding?.token_configured === true || binding?.tokenConfigured === true){
        return "Configured";
    }
    return "Not configured";
}

function renderMessengerBindings(bindings){
    const panel = $("messengerBindingsPanel");
    if(!panel) return;

    const rows = Array.isArray(bindings) ? bindings : [];
    state.messengerBindings = rows;
    panel.classList.remove("hidden");

    if(rows.length === 0){
        panel.innerHTML = `
            <div><b>Messenger bindings</b></div>
            <div class="panel-state empty">No Messenger bindings found for the selected tenant.</div>
        `;
        return;
    }

    panel.innerHTML = `
        <div><b>Messenger bindings</b></div>
        <div class="table-wrap">
            <table class="table" id="messenger-bindings-table">
                <thead>
                    <tr>
                        <th>Page ID</th>
                        <th>Tenant</th>
                        <th>Chatbot</th>
                        <th>Status</th>
                        <th>Token</th>
                        <th>Preview</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.map(row => {
                        const configured = row.token_configured ?? row.tokenConfigured;
                        return `
                            <tr data-binding-id="${escapeHtml(row.id)}" data-page-id="${escapeHtml(row.page_id || row.pageId)}">
                                <td>${escapeHtml(row.page_id || row.pageId)}</td>
                                <td>${escapeHtml(findTenantLabel(row.tenant_id || row.tenantId))}</td>
                                <td>${escapeHtml(findBotLabel(row.chatbot_id || row.chatbotId))}</td>
                                <td>${renderKbStatusBadge(row.status || "-")}</td>
                                <td>${configured ? '<span class="status-badge status-completed">Configured</span>' : '<span class="status-badge status-new">Not configured</span>'}</td>
                                <td>${renderTokenState(row)}</td>
                                <td>${escapeHtml(fmtDateTime(row.created_at || row.createdAt) || "-")}</td>
                                <td>
                                    <div class="table-actions">
                                        <button class="secondary" data-action="messenger-status">Check Status</button>
                                        <button class="danger" data-action="messenger-delete">Delete/Deactivate</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join("")}
                </tbody>
            </table>
        </div>
    `;
}

async function loadMessengerBindings(){
    if(!state.selectedTenant){
        showMsg("cfgMsg", "Chua chon tenant");
        return null;
    }
    renderPanelState("messengerBindingsPanel", "Loading Messenger bindings...", "loading");
    let r;
    try{
        r = await req("GET", "/api/messenger/bindings");
    }catch(err){
        renderPanelState("messengerBindingsPanel", err.message || "Load Messenger bindings failed", "error");
        showMsg("cfgMsg", err.message || "Load Messenger bindings failed", 2200);
        return null;
    }
    if(r.ok && Array.isArray(r.data)){
        renderMessengerBindings(r.data);
        setJsonOutput("bindingsOut", r, true);
        showMsg("cfgMsg", `Loaded ${r.data.length} Messenger binding(s)`, 1800);
    } else {
        renderPanelState("messengerBindingsPanel", r.data?.message || `Load Messenger bindings failed (${r.status})`, "error");
        setJsonOutput("bindingsOut", r, true);
        showMsg("cfgMsg", r.data?.message || `Load Messenger bindings FAIL (${r.status})`, 2200);
    }
    return r;
}

async function checkMessengerBindingStatus(pageId){
    if(!pageId){
        showMsg("cfgMsg", "Missing page ID", 1800);
        return;
    }
    renderPanelState("messengerBindingStatusPanel", "Checking Messenger binding status...", "loading");
    let r;
    try{
        r = await req("GET", `/api/messenger/bindings/${encodeURIComponent(pageId)}/status`);
    }catch(err){
        renderPanelState("messengerBindingStatusPanel", err.message || "Check Messenger binding status failed", "error");
        showMsg("cfgMsg", err.message || "Check Messenger binding status failed", 2200);
        return;
    }
    if(r.ok){
        renderBindingStatusPanel(r.data);
        showMsg("cfgMsg", "Messenger binding status loaded", 1600);
    } else {
        renderBindingStatusPanel({ page_id: pageId, binding_active: false, reason: r.data?.message || `STATUS_FAIL_${r.status}` });
        showMsg("cfgMsg", "Check Messenger binding status FAIL", 1800);
    }
}

function renderBindingStatusPanel(status){
    const panel = $("messengerBindingStatusPanel");
    if(!panel) return;

    const runtime = status?.runtime || {};
    const desiredKb = status?.desired_kb || status?.desiredKb || {};
    const active = status?.binding_active ?? status?.bindingActive;
    const inSync = status?.runtime_in_sync ?? status?.runtimeInSync;
    const externalMode = runtime.mode === "external";
    const activeBadge = active
        ? '<span class="ops-badge ops-badge-success">ACTIVE</span>'
        : '<span class="ops-badge ops-badge-failed">INACTIVE</span>';
    const syncBadge = inSync === true
        ? '<span class="ops-badge ops-badge-success">IN SYNC</span>'
        : (inSync === false ? '<span class="ops-badge ops-badge-progress">CHECK REQUIRED</span>' : '<span class="ops-badge ops-badge-neutral">UNKNOWN</span>');
    const externalNote = externalMode
        ? '<div class="inline-feedback">External runtime mode: Java cannot verify the actual KB_DIR used by the external process.</div>'
        : "";

    panel.classList.remove("hidden");
    panel.innerHTML = `
        <div><b>Messenger binding status</b></div>
        <div class="ops-summary-copy">${activeBadge} ${syncBadge}</div>
        ${active === false ? `<div class="inline-feedback error">Binding inactive: ${escapeHtml(status?.reason || "-")}</div>` : ""}
        ${inSync === false ? `<div class="inline-feedback error">Runtime is not in sync with desired KB.</div>` : ""}
        ${externalNote}
        <div class="ops-stats-grid">
            <div class="ops-stat-card"><div class="muted">Page ID</div><div><b>${escapeHtml(status?.page_id || status?.pageId)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Tenant ID</div><div><b>${escapeHtml(status?.tenant_id || status?.tenantId)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Chatbot ID</div><div><b>${escapeHtml(status?.chatbot_id || status?.chatbotId)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Binding status</div><div><b>${escapeHtml(status?.binding_status || status?.bindingStatus)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Token configured</div><div><b>${escapeHtml(boolLabel(status?.token_configured ?? status?.tokenConfigured))}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Token preview</div><div><b>${escapeHtml(status?.token_preview || status?.tokenPreview)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Desired KB dir</div><div><b>${escapeHtml(desiredKb.kb_dir || desiredKb.kbDir)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Desired source</div><div><b>${escapeHtml(desiredKb.source)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Desired version</div><div><b>${escapeHtml(desiredKb.version_tag || desiredKb.versionTag)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Runtime mode</div><div><b>${escapeHtml(runtime.mode)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Runtime KB dir</div><div><b>${escapeHtml(runtime.kb_dir || runtime.kbDir)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Runtime version</div><div><b>${escapeHtml(runtime.version_tag || runtime.versionTag)}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Process alive</div><div><b>${escapeHtml(boolLabel(runtime.process_alive ?? runtime.processAlive))}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Runtime in sync</div><div><b>${escapeHtml(boolLabel(inSync))}</b></div></div>
        </div>
    `;
}

async function deactivateMessengerBinding(bindingId, button=null){
    if(!bindingId){
        showMsg("cfgMsg", "Missing binding ID", 1800);
        return;
    }
    if(!window.confirm("Delete/deactivate this Messenger binding?")){
        return;
    }
    await withButtonLoading(button, "Deleting...", async ()=>{
        try{
        const r = await req("DELETE", `/api/messenger/bindings/${encodeURIComponent(bindingId)}`);
        setJsonOutput("bindingsOut", r, true);
        if(r.ok){
            showMsg("cfgMsg", "Messenger binding deactivated", 1800);
            await loadMessengerBindings();
            $("messengerBindingStatusPanel")?.classList.add("hidden");
        } else {
            showMsg("cfgMsg", r.data?.message || `Delete/deactivate FAIL (${r.status})`, 2200);
        }
        }catch(err){
            showMsg("cfgMsg", err.message || "Delete/deactivate FAIL", 2200);
        }
    });
}

/* ---------------- Bindings ---------------- */
$("useTenantBindings")?.addEventListener("click", async ()=>{
    const id = state.selectedTenant?.id || "";
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

// Provider toggle removed - Claude uses system-level env only

$("createTgBinding").addEventListener("click", async ()=>{
    $("bindingsOut").innerText = "";

    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    if(!state.selectedBot){ showMsg("cfgMsg", "Chưa chọn chatbot"); return; }

    const botToken = $("tgToken").value.trim();
    if(!botToken){ showMsg("cfgMsg", "Thiếu bot token"); return; }

    const payload = { chatbotId: state.selectedBot.id, botToken };
    const r = await req("POST", "/api/telegram/bindings", payload);

    // Always show binding result first
    setJsonOutput("bindingsOut", r, true);

    // Auto setWebhook if ngrok base URL is provided
    const publicBase = ($("tgPublicBase")?.value || "").trim().replace(/\/+$/,"");
    const secretPath = r?.data?.secretPath; // <-- đúng theo response bạn gửi

    if(!r.ok){
        showMsg("cfgMsg", "Create binding FAIL");
        return;
    }

    if(!publicBase){
        $("tgToken").value = "";
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

    setJsonOutput("bindingsOut", merged, true);

    if(w.ok){
        $("tgToken").value = "";
        showMsg("cfgMsg", "Set Telegram webhook OK", 2500);
    } else {
        showMsg("cfgMsg", "Set Telegram webhook FAIL", 2500);
    }
});

$("loadTgBindings").addEventListener("click", async ()=>{
    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    const r = await req("GET", "/api/telegram/bindings");
    setJsonOutput("bindingsOut", r, true);
});

$("createMsgBinding").addEventListener("click", async (event)=>{
    $("bindingsOut").innerText = "";

    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    if(!state.selectedBot){ showMsg("cfgMsg", "Chưa chọn chatbot"); return; }

    const pageId = $("pageId").value.trim();
    const pageAccessToken = $("pageToken").value.trim();
    if(!pageId || !pageAccessToken){
        showMsg("cfgMsg", "Thiếu pageId hoặc page access token");
        return;
    }

    setButtonLoading(event.currentTarget, true, "Creating...");
    try{
        const payload = { pageId, chatbotId: state.selectedBot.id, pageAccessToken };
        const r = await req("POST", "/api/messenger/bindings", payload);
        setJsonOutput("bindingsOut", r, true);
        if(r.ok){
            $("pageToken").value = "";
            showMsg("cfgMsg", "Messenger binding created", 1800);
            await loadMessengerBindings();
        } else {
            showMsg("cfgMsg", r.data?.message || `Create Messenger binding FAIL (${r.status})`, 2200);
        }
    }catch(err){
        showMsg("cfgMsg", err.message || "Create Messenger binding FAIL", 2200);
    }finally{
        setButtonLoading(event.currentTarget, false);
    }
});

$("loadMsgBindings").addEventListener("click", async (event)=>{
    if(!state.selectedTenant){ showMsg("cfgMsg", "Chưa chọn tenant"); return; }
    await withButtonLoading(event.currentTarget, "Loading...", loadMessengerBindings);
});

$("messengerBindingsPanel")?.addEventListener("click", async (event)=>{
    const btn = event.target.closest("button[data-action]");
    if(!btn) return;
    const row = btn.closest("tr");
    const pageId = row?.dataset?.pageId || "";
    const bindingId = row?.dataset?.bindingId || "";
    if(btn.dataset.action === "messenger-status"){
        await withButtonLoading(btn, "Checking...", ()=> checkMessengerBindingStatus(pageId));
    }
    if(btn.dataset.action === "messenger-delete"){
        await deactivateMessengerBinding(bindingId, btn);
    }
});

$("clearBindingsOut").addEventListener("click", ()=>{
    $("bindingsOut").innerText = "";
    if($("messengerBindingsPanel")){
        $("messengerBindingsPanel").classList.add("hidden");
        $("messengerBindingsPanel").innerHTML = "";
    }
    if($("messengerBindingStatusPanel")){
        $("messengerBindingStatusPanel").classList.add("hidden");
        $("messengerBindingStatusPanel").innerHTML = "";
    }
});

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
    $("tenantsMsg").innerText = "Loading tenants...";
    renderTenantsTable();
    let r;
    try{
        r = await req("GET", "/api/admin/tenants", undefined, { tenantHeaders:false });
        setJsonOutput("tenantsOut", r, true);
    }catch(err){
        state.tenants = [];
        renderTenantsTable();
        $("tenantsMsg").innerText = err.message || "Load tenants failed";
        return null;
    }

    if(r.ok && Array.isArray(r.data)){
        state.tenants = r.data;
        renderTenantsTable();

        const tenantToSelect =
            (preferredTenantId && state.tenants.find(t => t.id === preferredTenantId))
            || (autoPickFirst ? state.tenants[0] : null);

        if(tenantToSelect){
            applyTenantById(tenantToSelect.id);
        }
        $("tenantsMsg").innerText = `Loaded ${state.tenants.length} tenant(s)`;
    } else {
        state.tenants = [];
        renderTenantsTable();
        $("tenantsMsg").innerText = r.data?.message || `Load tenants failed (${r.status})`;
    }
    return r;
}

function wireTenantProvisioningUi(){
    const createTenantButton = replaceElementWithClone("createTenant");
    const loadTenantsButton = replaceElementWithClone("loadTenants");
    const clearTenantsButton = replaceElementWithClone("clearTenantsOut");

    createTenantButton?.addEventListener("click", async (event)=>{
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

        setButtonLoading(event.currentTarget, true, "Creating...");
        let r;
        try{
            r = await req("POST", "/api/admin/tenants", body, { tenantHeaders:false });
            setJsonOutput("tenantsOut", r, true);
        }catch(err){
            $("tenantsMsg").innerText = err.message || "Create tenant failed";
            setButtonLoading(event.currentTarget, false);
            return;
        }

        if(r.ok && r.data?.id){
            $("tenantApiKey").value = "";
            $("tenantKbDir").value = "";
            $("tenantStatus").value = r.data.status || "ACTIVE";
            await loadTenants(false, r.data.id);
            setButtonLoading(event.currentTarget, false);
            showMsg("tenantsMsg", `Created tenant ${r.data.code || code}`, 1800);
            return;
        }

        if(r.data?.message){
            $("tenantsMsg").innerText = r.data.message;
        }
        setButtonLoading(event.currentTarget, false);
    });

    loadTenantsButton?.addEventListener("click", (event)=> withButtonLoading(event.currentTarget, "Loading...", ()=> loadTenants(false)));
    clearTenantsButton?.addEventListener("click", ()=> $("tenantsOut").innerText = "");
}

function wireMemberManagementUi(){
    $("useTenantMembers")?.addEventListener("click", async ()=>{
        const tenantId = state.selectedTenant?.id || "";
        if(!tenantId){
            $("membersMsg").innerText = "Select a tenant first";
            return;
        }
        applyTenantById(tenantId);
        $("membersMsg").innerText = "Tenant applied";
        await loadMembersForSelectedTenant();
    });

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
        if(!body.email.includes("@")){
            $("membersMsg").innerText = "Email must contain @";
            return;
        }
        if(!body.role){
            $("membersMsg").innerText = "Role is required";
            return;
        }

        const r = await req("POST", `/api/admin/tenant-members?tenantId=${encodeURIComponent(tenantId)}`, body, { tenantHeaders:false });
        setJsonOutput("membersOut", r, true);
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

function wireRawOutputToggles(){
    wireRawOutputToggle("toggleTenantsOut", "tenantsOut");
    wireRawOutputToggle("toggleOnboardingOut", "onboardingOut");
    wireRawOutputToggle("toggleMembersOut", "membersOut");
    wireRawOutputToggle("toggleBotsOut", "botsOut");
    wireRawOutputToggle("toggleBindingsOut", "bindingsOut");
    wireRawOutputToggle("toggleProductDatasetsOut", "productDatasetsOut");
}

function wireProductDatasetUi(){
    $("loadProductDatasets")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Loading...", () => loadProductDatasets().catch(err => {
            console.error(err);
        }))
    );
    $("registerProductDataset")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Registering...", () => registerProductDataset().catch(err => {
            console.error(err);
            $("productDatasetsMsg").innerText = err.message || "Register dataset failed";
        }))
    );
    $("clearProductDatasetForm")?.addEventListener("click", clearProductDatasetForm);
    $("productDatasetsTablePanel")?.addEventListener("click", event => {
        const button = event.target.closest("button");
        if(!button) return;
        const datasetId = button.closest("tr")?.dataset?.datasetId;
        if(!datasetId) return;

        const action = button.dataset.action;
        if(action === "dataset-view"){
            withButtonLoading(button, "Loading...", () => viewProductDataset(datasetId).catch(err => {
                console.error(err);
                $("productDatasetsMsg").innerText = err.message || "Load dataset detail failed";
            }));
        } else if(action === "dataset-assign"){
            withButtonLoading(button, "Assigning...", () => assignProductDataset(datasetId).catch(err => {
                console.error(err);
                $("productDatasetsMsg").innerText = err.message || "Assign dataset failed";
            }));
        } else if(action === "dataset-delete"){
            withButtonLoading(button, "Deleting...", () => deleteProductDataset(datasetId).catch(err => {
                console.error(err);
                $("productDatasetsMsg").innerText = err.message || "Delete dataset record failed";
            }));
        }
    });
}

function wireKbUi(){
    $("loadActiveKbDirectory")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Loading...", () => loadActiveKbDirectory().catch(err => {
            console.error(err);
        }))
    );
    $("loadKbVersions")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Loading...", () => loadKbVersions().catch(err => {
            console.error(err);
        }))
    );
    $("kbVersionsTablePanel")?.addEventListener("click", event => {
        const button = event.target.closest("button");
        if(!button) return;
        const id = button.closest("tr")?.dataset?.kbVersionId;
        if(!id) return;
        const action = button.dataset.action;
        if(action === "kb-version-view"){
            renderKbVersionDetail(state.kbVersions.find(item => item.id === id));
        } else if(action === "kb-version-publish"){
            withButtonLoading(button, "Publishing...", () => publishKbVersion(id).catch(err => {
                console.error(err);
                $("kbVersionsMsg").innerText = err.message || "Publish failed";
            }));
        } else if(action === "kb-version-archive"){
            withButtonLoading(button, "Archiving...", () => archiveKbVersion(id).catch(err => {
                console.error(err);
                $("kbVersionsMsg").innerText = err.message || "Archive failed";
            }));
        }
    });
    $("loadKbSourceUrls")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Loading...", () => loadKbSourceUrls().catch(err => {
            console.error(err);
        }))
    );
    $("rebuildKb")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Rebuilding...", () => rebuildKb().catch(err => {
            console.error(err);
            $("kbRebuildMsg").innerText = err.message || "Rebuild failed";
        }))
    );
    $("loadKbRebuildStatus")?.addEventListener("click", () => {
        if(!requireSelectedTenant("kbRebuildMsg", "kbRebuildStatusPanel")) return;
        renderKbRebuildResponse(null);
        $("kbRebuildMsg").innerText = "No standalone rebuild status endpoint exists. Use Monitoring for rebuild history.";
    });
    $("loadKbRuntimeStatus")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Loading...", () => loadKbRuntimeStatus().catch(err => {
            console.error(err);
        }))
    );
    $("evictSelectedTenantRuntime")?.addEventListener("click", event =>
        withButtonLoading(event.currentTarget, "Evicting...", () => evictSelectedTenantRuntime().catch(err => {
            console.error(err);
            $("kbRuntimeMsg").innerText = err.message || "Evict runtime failed";
        }))
    );
}

async function loadMembersForSelectedTenant(){
    const tenantId = getSelectedTenantIdForMembers();
    if(!tenantId){
        $("membersMsg").innerText = "Select a tenant first";
        $("membersOut").innerText = "";
        return;
    }

    const r = await req("GET", `/api/admin/tenant-members?tenantId=${encodeURIComponent(tenantId)}`, undefined, { tenantHeaders:false });
    setJsonOutput("membersOut", r, true);
    if(r.ok){
        showMsg("membersMsg", `Loaded ${(Array.isArray(r.data) ? r.data.length : 0)} member(s)`, 1600);
        return;
    }
    $("membersMsg").innerText = r.data?.message || `Load members failed (${r.status})`;
}

/* ---------------- Init ---------------- */
$("saveCfg").addEventListener("click", saveCfg);
$("toggleDevDebug")?.addEventListener("click", ()=>{
    const panel = $("devDebugPanel");
    if(!panel) return;
    panel.classList.toggle("hidden");
});
loadCfg();
wireRawOutputToggles();
wireTenantProvisioningUi();
wireMemberManagementUi();
wireProductDatasetUi();
wireKbUi();

$("loadRuntime").addEventListener("click", async ()=>{
    $("runtimeMsg").innerText = "";
    $("runtimeOut").innerText = "";

    // Nếu bạn làm Hướng A/B (exclude runtime) => KHÔNG cần tenant headers
    const [systemStatusRes, platformRes, benchmarkRes] = await Promise.all([
        req("GET", "/api/admin/system-status", undefined, { tenantHeaders: false }),
        req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
        req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
    ]);
    renderSystemStatusSummary(systemStatusRes);
    renderPlatformOpsSummary(platformRes.ok ? platformRes.data : null);
    renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
    setJsonOutput("runtimeOut", {
        systemStatus: systemStatusRes,
        platform: platformRes,
        benchmark: benchmarkRes
    }, true);
    $("runtimeMsg").innerText = (systemStatusRes.ok && platformRes.ok && benchmarkRes.ok)
        ? "Platform ops and benchmark summary loaded"
        : `FAIL (system=${systemStatusRes.status}, platform=${platformRes.status}, benchmark=${benchmarkRes.status})`;
});

$("clearRuntimeOut").addEventListener("click", ()=>{
    $("runtimeOut").innerText = "";
    $("runtimeMsg").innerText = "";
    if($("runtimeSummary")){
        $("runtimeSummary").classList.add("hidden");
        $("runtimeSummary").innerHTML = "";
    }
    if($("systemStatusSummary")){
        $("systemStatusSummary").classList.add("hidden");
        $("systemStatusSummary").innerHTML = "";
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
    setJsonOutput("runtimeOut", r, true);
    $("runtimeMsg").innerText = r.ok ? "Runtime evicted" : (r.data?.message || `FAIL (${r.status})`);
    if(r.ok){
        const [systemStatusRes, refreshed, benchmarkRes] = await Promise.all([
            req("GET", "/api/admin/system-status", undefined, { tenantHeaders: false }),
            req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
            req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
        ]);
        renderSystemStatusSummary(systemStatusRes);
        renderPlatformOpsSummary(refreshed.ok ? refreshed.data : null);
        renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
    }
});

function wireMonitoringActions(){
    const loadRuntimeButton = replaceElementWithClone("loadRuntime");
    const evictRuntimeButton = replaceElementWithClone("evictRuntime");

    loadRuntimeButton?.addEventListener("click", async (event)=>{
        $("runtimeMsg").innerText = "";
        $("runtimeOut").innerText = "";
        renderPanelState("systemStatusSummary", "Loading system status...", "loading");
        renderPanelState("runtimeSummary", "Loading platform ops...", "loading");

        await withButtonLoading(event.currentTarget, "Loading...", async ()=>{
            try{
                const [systemStatusRes, platformRes, benchmarkRes] = await Promise.all([
                    req("GET", "/api/admin/system-status", undefined, { tenantHeaders: false }),
                    req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
                    req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
                ]);
                renderSystemStatusSummary(systemStatusRes);
                renderPlatformOpsSummary(platformRes.ok ? platformRes.data : null);
                renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
                setJsonOutput("runtimeOut", {
                    systemStatus: systemStatusRes,
                    platform: platformRes,
                    benchmark: benchmarkRes
                }, true);
                $("runtimeMsg").innerText = (systemStatusRes.ok && platformRes.ok && benchmarkRes.ok)
                    ? "Platform ops and benchmark summary loaded"
                    : `FAIL (system=${systemStatusRes.status}, platform=${platformRes.status}, benchmark=${benchmarkRes.status})`;
            }catch(err){
                renderPanelState("systemStatusSummary", err.message || "Load system status failed", "error");
                renderPlatformOpsSummary(null);
                $("runtimeMsg").innerText = err.message || "Load platform ops failed";
            }
        });
    });

    evictRuntimeButton?.addEventListener("click", async (event)=>{
        const tenantId = $("runtimeEvictTenantId")?.value?.trim();
        if(!tenantId){
            $("runtimeMsg").innerText = "Enter a tenant UUID";
            return;
        }
        if(!window.confirm(`Evict runtime for tenant ${tenantId}?`)){
            return;
        }

        await withButtonLoading(event.currentTarget, "Evicting...", async ()=>{
            $("runtimeMsg").innerText = "Evicting runtime...";
            try{
                const r = await evictPlatformRuntime(tenantId);
                setJsonOutput("runtimeOut", r, true);
                $("runtimeMsg").innerText = r.ok ? "Runtime evicted" : (r.data?.message || `FAIL (${r.status})`);
                if(r.ok){
                    renderPanelState("systemStatusSummary", "Refreshing status...", "loading");
                    renderPanelState("runtimeSummary", "Refreshing platform ops...", "loading");
                    const [systemStatusRes, refreshed, benchmarkRes] = await Promise.all([
                        req("GET", "/api/admin/system-status", undefined, { tenantHeaders: false }),
                        req("GET", "/api/ops/platform", undefined, { tenantHeaders: false }),
                        req("GET", "/api/ops/benchmark-summary", undefined, { tenantHeaders: false })
                    ]);
                    renderSystemStatusSummary(systemStatusRes);
                    renderPlatformOpsSummary(refreshed.ok ? refreshed.data : null);
                    renderBenchmarkSummary(benchmarkRes.ok ? benchmarkRes.data : null);
                }
            }catch(err){
                $("runtimeMsg").innerText = err.message || "Evict runtime failed";
            }
        });
    });
}

wireMonitoringActions();

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
        setPrimaryTab("dashboard", "overview");
        await loadTenants(false);
        // Initialize provider field visibility
        toggleApiConfigFields();
    } catch (err) {
        console.error(err);
    }
}

bootstrapAdminUi();
