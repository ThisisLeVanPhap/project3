function $(id){ return document.getElementById(id); }

let TENANT_ID = "";
let TENANT_NAME = "";
let CURRENT_PRINCIPAL = null;

/* ===============================
   Tenant id persistence
   =============================== */
const params = new URLSearchParams(window.location.search);
const tidFromUrl = params.get("tid");
const nameFromUrl = params.get("name");

if (tidFromUrl) {
    localStorage.setItem("tenant_id", tidFromUrl);
    if (nameFromUrl) localStorage.setItem("tenant_name", nameFromUrl);

    // Clean URL: remove ?tid=...&name=...
    window.history.replaceState({}, document.title, "/tenant");
}

TENANT_ID = localStorage.getItem("tenant_id") || "";
TENANT_NAME = localStorage.getItem("tenant_name") || "";

/* ===============================
   UI header
   =============================== */
if ($("tenantLabel")) {
    $("tenantLabel").innerText = TENANT_NAME || TENANT_ID || "-";
}

if (!TENANT_ID) {
    console.warn("Missing tenant id in local storage, trying session principal.");
}

/* ===============================
   API
   =============================== */
async function fetchLeads(){
    const res = await fetch(`/tenant/api/leads?tid=${encodeURIComponent(TENANT_ID)}`);
    if (!res.ok) throw new Error("Failed to load leads");
    return await res.json();
}

async function updateStatus(id, status){
    const res = await fetch(
        `/tenant/api/leads/${id}/status?status=${encodeURIComponent(status)}&tid=${encodeURIComponent(TENANT_ID)}`,
        { method: "POST" }
    );
    if (!res.ok) throw new Error("Failed to update");
    return await res.json();
}

async function sendReply(leadId, message){
    const res = await fetch(`/tenant/api/reply?tid=${encodeURIComponent(TENANT_ID)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadId, message })
    });
    return res;
}

async function saveOrderInfo(leadId, orderInfo){
    const res = await fetch(`/tenant/api/leads-ops/order-info?tid=${encodeURIComponent(TENANT_ID)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadId, orderInfo })
    });
    return res;
}

async function markShipped(leadId){
    const res = await fetch(`/tenant/api/leads-ops/${leadId}/ship?tid=${encodeURIComponent(TENANT_ID)}`, {
        method: "POST"
    });
    return res;
}

async function fetchTenantAdminJson(path){
    const res = await fetch(path);
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function fetchTenantMembers(){
    const res = await fetch("/api/tenant-members");
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function createTenantMember(payload){
    const res = await fetch("/api/tenant-members", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function fetchKbSourceUrls(){
    const res = await fetch("/api/kb/source-urls");
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function addKbSourceUrl(url){
    const res = await fetch("/api/kb/source-urls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function removeKbSourceUrl(url){
    const res = await fetch("/api/kb/source-urls", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function rebuildKb(){
    const res = await fetch("/api/kb/rebuild", {
        method: "POST"
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function fetchTenantOps(){
    const res = await fetch("/api/ops/tenant");
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

async function evictTenantRuntime(){
    const res = await fetch("/api/ops/runtime/evict", {
        method: "POST"
    });
    const text = await res.text();
    let data = text;
    try { data = JSON.parse(text); } catch (e) {}
    if (!res.ok) {
        throw new Error(data?.message || text || `Request failed (${res.status})`);
    }
    return data;
}

/* ===============================
   State
   =============================== */
const leadMap = new Map();
let currentLeadId = null;

function renderKbSourceUrls(items){
    const tbody = document.querySelector("#kb-sources-table tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!Array.isArray(items) || !items.length) {
        tbody.innerHTML = `<tr><td colspan="2" class="muted">No source URLs configured</td></tr>`;
        return;
    }

    for (const url of items) {
        const tr = document.createElement("tr");
        tr.dataset.url = url;
        tr.innerHTML = `
            <td>${url}</td>
            <td><button class="secondary" data-act="remove-kb-source">Remove</button></td>
        `;
        tbody.appendChild(tr);
    }
}

function renderTenantOpsSummary(snapshot){
    const el = $("tenantOpsSummary");
    if (!el) return;
    if (!snapshot) {
        el.classList.add("hidden");
        el.innerHTML = "";
        return;
    }

    const runtime = snapshot.runtime || {};
    const kb = snapshot.knowledgeBase || {};
    const botCount = Array.isArray(snapshot.bots) ? snapshot.bots.length : 0;
    const purchaseRequests = snapshot.purchaseRequests || {};
    const rebuildBits = [
        `status ${renderKbStatusBadge(kb.lastRebuildStatus)}`,
        kb.lastRebuildStartedAt ? `started ${new Date(kb.lastRebuildStartedAt).toLocaleString()}` : "",
        kb.lastRebuildFinishedAt ? `finished ${new Date(kb.lastRebuildFinishedAt).toLocaleString()}` : ""
    ].filter(Boolean).join(", ");
    el.classList.remove("hidden");
    el.innerHTML = `
        <div><b>Tenant ops snapshot</b></div>
        <div>Runtime: ${runtime.status || "UNKNOWN"}${runtime.lastActivityAt ? `, last activity ${new Date(runtime.lastActivityAt).toLocaleString()}` : ""}</div>
        <div>KB: ${kb.status || "UNKNOWN"}${kb.lastRebuildAt ? `, last rebuild ${new Date(kb.lastRebuildAt).toLocaleString()}` : ""}</div>
        <div>KB rebuild tracking: ${rebuildBits || "No tracked rebuild yet"}</div>
        <div>${kb.lastRebuildMessage || ""}</div>
        <div>Chatbots tracked: ${botCount}</div>
        <div class="ops-stats-grid">
            <div class="ops-stat-card"><div class="muted">Purchase requests</div><div><b>${purchaseRequests.totalRequests ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">NEW</div><div><b>${purchaseRequests.newCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">CONTACTED</div><div><b>${purchaseRequests.contactedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">COMPLETED</div><div><b>${purchaseRequests.completedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Assigned</div><div><b>${purchaseRequests.assignedCount ?? 0}</b></div></div>
            <div class="ops-stat-card"><div class="muted">Unassigned</div><div><b>${purchaseRequests.unassignedCount ?? 0}</b></div></div>
        </div>
        <div class="ops-summary-copy"><b>Recent KB rebuild history</b></div>
        ${renderKbRebuildHistory(kb.rebuildHistory)}
    `;
}

function renderKbRebuildHistory(history){
    if (!Array.isArray(history) || history.length === 0) {
        return `<div class="ops-summary-copy">No recent KB rebuild history.</div>`;
    }
    return `
        <div class="kb-history-list">
            ${history.map(item => `
                <div class="kb-history-item">
                    <div>${renderKbStatusBadge(item.status)}</div>
                    <div>Started: ${item.startedAt ? new Date(item.startedAt).toLocaleString() : "—"}</div>
                    <div>Finished: ${item.finishedAt ? new Date(item.finishedAt).toLocaleString() : "—"}</div>
                    <div>${item.message || ""}</div>
                </div>
            `).join("")}
        </div>
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

/* ===============================
   Drawer
   =============================== */
function openLeadDetails(lead){
    if (!lead) return;

    currentLeadId = lead.id;

    $("lead-slots").textContent = "Slots:\n" + (lead.slotsJson || "{}");
    $("lead-transcript").textContent = "Transcript:\n" + (lead.transcript || "");

    if ($("replyText")) $("replyText").value = "";
    if ($("replyStatus")) $("replyStatus").textContent = "";

    if ($("orderInfo")) $("orderInfo").value = (lead.orderInfo || "");
    if ($("orderStatus")) {
        const st = (lead.shippingStatus || "NEW").toUpperCase();
        $("orderStatus").textContent = `Shipping status: ${st}`;
    }

    if ($("btn-mark-shipped")) {
        const st = (lead.shippingStatus || "NEW").toUpperCase();
        $("btn-mark-shipped").disabled = (st !== "READY");
        $("btn-mark-shipped").title = (st !== "READY")
            ? "Save delivery info first to set READY"
            : "";
    }

    $("lead-details").classList.remove("hidden");
}

$("btn-close") && ($("btn-close").onclick = ()=> $("lead-details").classList.add("hidden"));

/* ===============================
   Render
   =============================== */
function render(leads){
    const table = $("leads-table");
    if (!table) return;

    const tb = table.querySelector("tbody");
    tb.innerHTML = "";
    leadMap.clear();

    if (!Array.isArray(leads) || !leads.length){
        tb.innerHTML = `<tr><td colspan="6" class="muted">No leads yet</td></tr>`;
        return;
    }

    for (const l of leads){
        leadMap.set(String(l.id), l);

        const tr = document.createElement("tr");
        const created = l.createdAt ? new Date(l.createdAt).toLocaleString() : "";

        tr.dataset.id = l.id;

        tr.innerHTML = `
          <td>${created}</td>
          <td>${l.status || ""}</td>
          <td>${l.channel || ""}</td>
          <td>${l.customerHandle || ""}</td>
          <td>${l.conversationId || ""}</td>
          <td>
            <button data-act="view">View</button>
            <button data-act="contacted">Contacted</button>
            <button data-act="closed">Closed</button>
          </td>
        `;

        tb.appendChild(tr);
    }
}

async function refresh(){
    if (!TENANT_ID) return;
    const leads = await fetchLeads();
    render(leads);

    if (currentLeadId && !$("lead-details")?.classList.contains("hidden")) {
        const latest = leadMap.get(String(currentLeadId));
        if (latest) openLeadDetails(latest);
    }
}

/* ===============================
   Events
   =============================== */
$("btn-refresh") && ($("btn-refresh").onclick = () => refresh().catch(e => alert(e.message)));

$("leads-table") && ($("leads-table").onclick = async (e)=>{
    const btn = e.target.closest("button");
    if (!btn) return;

    const tr = btn.closest("tr");
    if (!tr) return;

    const id = tr.dataset.id;
    const act = btn.dataset.act;

    if (act === "view"){
        openLeadDetails(leadMap.get(String(id)));
        return;
    }

    try{
        if (act === "contacted") await updateStatus(id, "CONTACTED");
        if (act === "closed") await updateStatus(id, "CLOSED");
        await refresh();
    } catch(err){
        alert(err.message);
    }
});

/* ===============================
   Reply button
   =============================== */
$("btn-send-reply") && ($("btn-send-reply").onclick = async () => {
    const msg = ($("replyText")?.value || "").trim();
    if (!msg || !currentLeadId) return;

    if ($("replyStatus")) $("replyStatus").textContent = "Sending...";

    try{
        const res = await sendReply(currentLeadId, msg);

        if (!res.ok){
            if ($("replyStatus")) $("replyStatus").textContent = "Failed to send";
            return;
        }

        if ($("replyStatus")) $("replyStatus").textContent = "Sent";
        if ($("replyText")) $("replyText").value = "";
    } catch(e){
        if ($("replyStatus")) $("replyStatus").textContent = "Failed to send";
    }
});

/* ===============================
   Order info + shipping ops
   =============================== */
$("btn-save-order") && ($("btn-save-order").onclick = async () => {
    if (!currentLeadId) return;

    const info = ($("orderInfo")?.value || "").trim();
    if ($("orderStatus")) $("orderStatus").textContent = "Saving...";

    try{
        const res = await saveOrderInfo(currentLeadId, info);
        if (!res.ok) {
            if ($("orderStatus")) $("orderStatus").textContent = "Failed";
            return;
        }

        if ($("orderStatus")) $("orderStatus").textContent = "Saved (READY)";
        await refresh();
    } catch(e){
        if ($("orderStatus")) $("orderStatus").textContent = "Failed";
    }
});

$("btn-mark-shipped") && ($("btn-mark-shipped").onclick = async () => {
    if (!currentLeadId) return;

    if ($("btn-mark-shipped").disabled) return;

    if ($("orderStatus")) $("orderStatus").textContent = "Marking as shipped...";

    try{
        const res = await markShipped(currentLeadId);
        if (!res.ok) {
            if ($("orderStatus")) $("orderStatus").textContent = "Failed";
            return;
        }

        if ($("orderStatus")) $("orderStatus").textContent = "Marked as SHIPPED (Customer notified)";
        await refresh();
    } catch(e){
        if ($("orderStatus")) $("orderStatus").textContent = "Failed";
    }
});

/* ===============================
   Init
   =============================== */
async function loadSessionPrincipal(){
    const res = await fetch("/api/me");
    if (!res.ok) throw new Error("Failed to load current session");

    const principal = await res.json();
    CURRENT_PRINCIPAL = principal;
    if (principal.role === "PLATFORM_ADMIN") {
        window.location.href = "/admin";
        throw new Error("Redirecting to platform admin");
    }

    TENANT_ID = principal.tenantId || TENANT_ID;
    TENANT_NAME = principal.displayName || TENANT_NAME;

    if (TENANT_ID) localStorage.setItem("tenant_id", TENANT_ID);
    if (TENANT_NAME) localStorage.setItem("tenant_name", TENANT_NAME);
    if ($("tenantLabel")) $("tenantLabel").innerText = TENANT_NAME || TENANT_ID || "-";
    if ($("identityLabel")) $("identityLabel").innerText = principal.displayName || principal.email || principal.userId || "-";
    if ($("roleLabel")) $("roleLabel").innerText = principal.role || "-";

    const tenantAdminTools = $("tenantAdminTools");
    if (tenantAdminTools) {
        tenantAdminTools.classList.toggle("hidden", principal.role !== "TENANT_ADMIN");
    }
}

$("btn-load-chatbots")?.addEventListener("click", async () => {
    try {
        const data = await fetchTenantAdminJson("/api/chatbots");
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ chatbots: data }, null, 2);
    } catch (err) {
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = err.message || "Failed to load chatbots";
    }
});

$("btn-load-telegram-bindings")?.addEventListener("click", async () => {
    try {
        const data = await fetchTenantAdminJson("/api/telegram/bindings");
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ telegramBindings: data }, null, 2);
    } catch (err) {
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = err.message || "Failed to load Telegram bindings";
    }
});

$("btn-load-messenger-bindings")?.addEventListener("click", async () => {
    try {
        const data = await fetchTenantAdminJson("/api/messenger/bindings");
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ messengerBindings: data }, null, 2);
    } catch (err) {
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = err.message || "Failed to load Messenger bindings";
    }
});

$("btn-load-members")?.addEventListener("click", async () => {
    try {
        const data = await fetchTenantMembers();
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ tenantMembers: data }, null, 2);
        if ($("tenantMembersMsg")) $("tenantMembersMsg").textContent = `Loaded ${Array.isArray(data) ? data.length : 0} member(s)`;
    } catch (err) {
        if ($("tenantMembersMsg")) $("tenantMembersMsg").textContent = err.message || "Failed to load tenant members";
    }
});

$("btn-create-member")?.addEventListener("click", async () => {
    const email = ($("tenantMemberEmail")?.value || "").trim();
    const password = ($("tenantMemberPassword")?.value || "").trim();
    const payload = {
        email,
        displayName: ($("tenantMemberDisplayName")?.value || "").trim(),
        role: ($("tenantMemberRole")?.value || "TENANT_MEMBER").trim(),
        status: ($("tenantMemberStatus")?.value || "ACTIVE").trim(),
        password
    };

    if (!email || !password) {
        if ($("tenantMembersMsg")) $("tenantMembersMsg").textContent = "Missing email or password";
        return;
    }

    try {
        const created = await createTenantMember(payload);
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ createdTenantMember: created }, null, 2);
        if ($("tenantMembersMsg")) $("tenantMembersMsg").textContent = `Created member ${created.email || email}`;
        if ($("tenantMemberPassword")) $("tenantMemberPassword").value = "";
    } catch (err) {
        if ($("tenantMembersMsg")) $("tenantMembersMsg").textContent = err.message || "Failed to create tenant member";
    }
});

$("btn-load-kb-sources")?.addEventListener("click", async () => {
    try {
        const data = await fetchKbSourceUrls();
        renderKbSourceUrls(data.urls || []);
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ kbSourceUrls: data }, null, 2);
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = `Loaded ${Array.isArray(data.urls) ? data.urls.length : 0} source URL(s)`;
    } catch (err) {
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = err.message || "Failed to load source URLs";
    }
});

$("btn-add-kb-source")?.addEventListener("click", async () => {
    const url = ($("kbSourceUrl")?.value || "").trim();
    if (!url) {
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = "Missing source URL";
        return;
    }

    try {
        const data = await addKbSourceUrl(url);
        renderKbSourceUrls(data.urls || []);
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ kbSourceUrls: data }, null, 2);
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = `Added source URL ${url}`;
        if ($("kbSourceUrl")) $("kbSourceUrl").value = "";
    } catch (err) {
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = err.message || "Failed to add source URL";
    }
});

document.querySelector("#kb-sources-table")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn || btn.dataset.act !== "remove-kb-source") return;
    const tr = btn.closest("tr");
    const url = tr?.dataset?.url || "";
    if (!url) return;

    try {
        const data = await removeKbSourceUrl(url);
        renderKbSourceUrls(data.urls || []);
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ kbSourceUrls: data }, null, 2);
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = `Removed source URL ${url}`;
    } catch (err) {
        if ($("kbSourcesMsg")) $("kbSourcesMsg").textContent = err.message || "Failed to remove source URL";
    }
});

$("btn-rebuild-kb")?.addEventListener("click", async () => {
    if ($("kbRebuildMsg")) $("kbRebuildMsg").textContent = "Rebuilding KB...";
    try {
        const data = await rebuildKb();
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ kbRebuild: data }, null, 2);
        if ($("kbRebuildMsg")) $("kbRebuildMsg").textContent = data.message || "KB rebuild completed";
        try {
            const ops = await fetchTenantOps();
            renderTenantOpsSummary(ops);
        } catch (ignored) {
        }
    } catch (err) {
        if ($("kbRebuildMsg")) $("kbRebuildMsg").textContent = err.message || "KB rebuild failed";
    }
});

$("btn-load-tenant-ops")?.addEventListener("click", async () => {
    if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = "Loading operations snapshot...";
    try {
        const data = await fetchTenantOps();
        renderTenantOpsSummary(data);
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ tenantOps: data }, null, 2);
        if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = "Tenant ops loaded";
    } catch (err) {
        renderTenantOpsSummary(null);
        if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = err.message || "Failed to load tenant ops";
    }
});

$("btn-evict-tenant-runtime")?.addEventListener("click", async () => {
    if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = "Evicting runtime...";
    try {
        const data = await evictTenantRuntime();
        if ($("tenantAdminToolsOut")) $("tenantAdminToolsOut").textContent = JSON.stringify({ evictRuntime: data }, null, 2);
        if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = data.message || "Runtime evicted";
        try {
            const ops = await fetchTenantOps();
            renderTenantOpsSummary(ops);
        } catch (ignored) {
        }
    } catch (err) {
        if ($("tenantOpsMsg")) $("tenantOpsMsg").textContent = err.message || "Failed to evict runtime";
    }
});

loadSessionPrincipal()
    .then(async () => {
        await refresh();
        if (CURRENT_PRINCIPAL?.role === "TENANT_ADMIN") {
            try {
                const data = await fetchTenantOps();
                renderTenantOpsSummary(data);
            } catch (ignored) {
            }
        }
    })
    .catch(e => alert(e.message));
