function $(id){ return document.getElementById(id); }

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

const TENANT_ID = localStorage.getItem("tenant_id");
const TENANT_NAME = localStorage.getItem("tenant_name");

/* ===============================
   UI header
   =============================== */
if ($("tenantLabel")) {
    $("tenantLabel").innerText = TENANT_NAME || TENANT_ID || "—";
}

if (!TENANT_ID) {
    alert("Missing tenant id. Please login first (or open /tenant?tid=YOUR_TENANT_ID).");
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

// ✅ NEW: save delivery info (order_info) + set READY
async function saveOrderInfo(leadId, orderInfo){
    const res = await fetch(`/tenant/api/leads-ops/order-info?tid=${encodeURIComponent(TENANT_ID)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadId, orderInfo })
    });
    return res;
}

// ✅ NEW: mark shipped + auto notify customer
async function markShipped(leadId){
    const res = await fetch(`/tenant/api/leads-ops/${leadId}/ship?tid=${encodeURIComponent(TENANT_ID)}`, {
        method: "POST"
    });
    return res;
}

/* ===============================
   State
   =============================== */
const leadMap = new Map(); // id -> lead object
let currentLeadId = null;

/* ===============================
   Drawer
   =============================== */
function openLeadDetails(lead){
    if (!lead) return;

    currentLeadId = lead.id;

    $("lead-slots").textContent = "Slots:\n" + (lead.slotsJson || "{}");
    $("lead-transcript").textContent = "Transcript:\n" + (lead.transcript || "");

    // reset reply UI
    if ($("replyText")) $("replyText").value = "";
    if ($("replyStatus")) $("replyStatus").textContent = "";

    // ✅ NEW: fill delivery info + show shipping status
    if ($("orderInfo")) $("orderInfo").value = (lead.orderInfo || "");
    if ($("orderStatus")) {
        const st = (lead.shippingStatus || "NEW").toUpperCase();
        $("orderStatus").textContent = `Shipping status: ${st}`;
    }

    // ✅ Optional UX: only allow "Mark shipped" when READY
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

    // ✅ keep drawer info in sync if it's open
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

        if ($("replyStatus")) $("replyStatus").textContent = "Sent ✓";
        if ($("replyText")) $("replyText").value = "";
    } catch(e){
        if ($("replyStatus")) $("replyStatus").textContent = "Failed to send";
    }
});

/* ===============================
   ✅ NEW: Order info + shipping ops
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

        if ($("orderStatus")) $("orderStatus").textContent = "Saved ✓ (READY)";
        await refresh();
    } catch(e){
        if ($("orderStatus")) $("orderStatus").textContent = "Failed";
    }
});

$("btn-mark-shipped") && ($("btn-mark-shipped").onclick = async () => {
    if (!currentLeadId) return;

    // optional guard: if disabled, do nothing
    if ($("btn-mark-shipped").disabled) return;

    if ($("orderStatus")) $("orderStatus").textContent = "Marking as shipped...";

    try{
        const res = await markShipped(currentLeadId);
        if (!res.ok) {
            if ($("orderStatus")) $("orderStatus").textContent = "Failed";
            return;
        }

        if ($("orderStatus")) $("orderStatus").textContent =
            "Marked as SHIPPED ✓ (Customer notified)";
        await refresh();
    } catch(e){
        if ($("orderStatus")) $("orderStatus").textContent = "Failed";
    }
});

/* ===============================
   Init
   =============================== */
refresh().catch(e => alert(e.message));
