function $(id){ return document.getElementById(id); }

let TENANT_ID = "";
let TENANT_NAME = "";
let CURRENT_PRINCIPAL = null;
let TENANT_MEMBERS = [];

const params = new URLSearchParams(window.location.search);
const tidFromUrl = params.get("tid");
const nameFromUrl = params.get("name");

if (tidFromUrl) {
    localStorage.setItem("tenant_id", tidFromUrl);
    if (nameFromUrl) localStorage.setItem("tenant_name", nameFromUrl);
    window.history.replaceState({}, document.title, "/tenant/purchase-requests");
}

TENANT_ID = localStorage.getItem("tenant_id") || "";
TENANT_NAME = localStorage.getItem("tenant_name") || "";

if ($("tenantLabel")) {
    $("tenantLabel").innerText = TENANT_NAME || TENANT_ID || "-";
}

function updateJsonLink() {
    const status = $("statusFilter")?.value || "";
    const href = status
        ? `/api/purchase-requests?status=${encodeURIComponent(status)}`
        : "/api/purchase-requests";
    if ($("jsonLink")) $("jsonLink").setAttribute("href", href);
}

async function fetchPurchaseRequests(status) {
    const url = status
        ? `/api/purchase-requests?status=${encodeURIComponent(status)}`
        : "/api/purchase-requests";

    const res = await fetch(url, {
        headers: {
            "X-Tenant-Id": TENANT_ID
        }
    });

    if (!res.ok) {
        const message = await res.text();
        throw new Error(message || "Failed to load purchase requests");
    }
    return await res.json();
}

async function fetchTenantMembers() {
    const res = await fetch("/api/tenant-members", {
        headers: {
            "X-Tenant-Id": TENANT_ID
        }
    });

    if (res.status === 403) {
        return [];
    }
    if (!res.ok) {
        const message = await res.text();
        throw new Error(message || "Failed to load tenant members");
    }
    return await res.json();
}

async function claimPurchaseRequest(id) {
    const res = await fetch(`/api/purchase-requests/${encodeURIComponent(id)}/claim`, {
        method: "PUT",
        headers: {
            "X-Tenant-Id": TENANT_ID
        }
    });

    const text = await res.text();
    let data = null;
    try {
        data = text ? JSON.parse(text) : null;
    } catch (err) {
        data = { message: text };
    }
    if (!res.ok) {
        throw new Error(data?.message || "Failed to claim purchase request");
    }
    return data;
}

async function reassignPurchaseRequest(id, memberId) {
    const res = await fetch(`/api/purchase-requests/${encodeURIComponent(id)}/assign`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            "X-Tenant-Id": TENANT_ID
        },
        body: JSON.stringify({ member_id: memberId })
    });

    const text = await res.text();
    let data = null;
    try {
        data = text ? JSON.parse(text) : null;
    } catch (err) {
        data = { message: text };
    }
    if (!res.ok) {
        throw new Error(data?.message || "Failed to reassign purchase request");
    }
    return data;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

function isTenantAdmin() {
    return CURRENT_PRINCIPAL?.role === "TENANT_ADMIN";
}

function canClaim(row) {
    return !row.assigned_to_member_id;
}

function ownerLabel(row) {
    if (row.assigned_to_display_name) return row.assigned_to_display_name;
    if (row.assigned_to_member_id) return row.assigned_to_member_id;
    return "Unassigned";
}

function normalizeStatus(status) {
    const s = String(status || "NEW").toUpperCase();
    return s === "CONTACTED" ? "PROCESSING" : s;
}

function memberOptions(selectedMemberId) {
    const options = ['<option value="">Select member</option>'];
    for (const member of TENANT_MEMBERS) {
        const selected = member.id === selectedMemberId ? " selected" : "";
        const label = escapeHtml(member.displayName || member.email || member.id);
        options.push(`<option value="${escapeHtml(member.id)}"${selected}>${label}</option>`);
    }
    return options.join("");
}

function render(rows) {
    const tbody = $("purchase-requests-table")?.querySelector("tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!Array.isArray(rows) || rows.length === 0) {
        tbody.innerHTML = "<tr><td colspan=\"7\" class=\"muted empty-state\">No purchase requests found for this tenant.</td></tr>";
        return;
    }

    for (const row of rows) {
        const tr = document.createElement("tr");
        tr.dataset.requestId = row.id || "";
        const created = row.created_at ? new Date(row.created_at).toLocaleString() : "";
        const claimedAt = row.claimed_at ? new Date(row.claimed_at).toLocaleString() : "";
        const claimButton = canClaim(row)
            ? `<button class="secondary" data-action="claim">Claim</button>`
            : `<span class="inline-note">${claimedAt ? `Claimed ${escapeHtml(claimedAt)}` : "Already assigned"}</span>`;
        const reassignControls = isTenantAdmin()
            ? `
                <select data-action="assign-member">
                    ${memberOptions(row.assigned_to_member_id || "")}
                </select>
                <button class="secondary" data-action="reassign">Reassign</button>
              `
            : "";

        tr.innerHTML = `
          <td>${created}</td>
          <td><span class="status-pill">${normalizeStatus(row.status)}</span></td>
          <td>${escapeHtml(row.customer_name || "")}</td>
          <td>${escapeHtml(row.phone || "")}</td>
          <td>${escapeHtml(row.shipping_address || "")}</td>
          <td class="assignment-cell">
            <div>${escapeHtml(ownerLabel(row))}</div>
            ${row.assigned_to_member_id ? `<div class="inline-note">${escapeHtml(row.assigned_to_member_id)}</div>` : ""}
          </td>
          <td>
            <div class="request-actions">
              ${claimButton}
              ${reassignControls}
            </div>
          </td>
        `;
        tbody.appendChild(tr);
    }
}

async function refresh() {
    if (!TENANT_ID) {
        if ($("pageStatus")) $("pageStatus").textContent = "Missing tenant session. Open this page after login or add ?tid=<tenant-id> once.";
        render([]);
        return;
    }

    const status = $("statusFilter")?.value || "";
    updateJsonLink();
    if ($("pageStatus")) $("pageStatus").textContent = "Loading purchase requests...";

    try {
        const rows = await fetchPurchaseRequests(status);
        render(rows);
        if ($("pageStatus")) $("pageStatus").textContent = `${rows.length} purchase request(s) loaded`;
    } catch (err) {
        render([]);
        if ($("pageStatus")) $("pageStatus").textContent = err.message || "Failed to load purchase requests";
    }
}

if ($("statusFilter")) {
    $("statusFilter").addEventListener("change", () => {
        refresh();
    });
}

if ($("btn-refresh")) {
    $("btn-refresh").addEventListener("click", () => {
        refresh();
    });
}

if ($("btn-logout")) {
    $("btn-logout").addEventListener("click", async () => {
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
}

async function loadSessionPrincipal() {
    const res = await fetch("/api/me");
    if (!res.ok) throw new Error("Failed to load current session");

    const principal = await res.json();
    CURRENT_PRINCIPAL = principal;
    TENANT_ID = principal.tenantId || TENANT_ID;
    TENANT_NAME = principal.displayName || TENANT_NAME;

    if (TENANT_ID) localStorage.setItem("tenant_id", TENANT_ID);
    if (TENANT_NAME) localStorage.setItem("tenant_name", TENANT_NAME);
    if ($("tenantLabel")) $("tenantLabel").innerText = TENANT_NAME || TENANT_ID || "-";
}

async function preparePageData() {
    await loadSessionPrincipal();
    TENANT_MEMBERS = isTenantAdmin() ? await fetchTenantMembers() : [];
}

document.querySelector("#purchase-requests-table")?.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const tr = button.closest("tr");
    const requestId = tr?.dataset?.requestId;
    if (!requestId) return;

    try {
        button.disabled = true;
        if (button.dataset.action === "claim") {
            await claimPurchaseRequest(requestId);
        }
        if (button.dataset.action === "reassign") {
            const select = tr.querySelector('select[data-action="assign-member"]');
            const memberId = select?.value || "";
            if (!memberId) {
                throw new Error("Choose a tenant member before reassigning");
            }
            await reassignPurchaseRequest(requestId, memberId);
        }
        await refresh();
    } catch (err) {
        if ($("pageStatus")) $("pageStatus").textContent = err.message || "Purchase request update failed";
    } finally {
        button.disabled = false;
    }
});

updateJsonLink();
preparePageData()
    .then(() => refresh())
    .catch(err => {
        if ($("pageStatus")) $("pageStatus").textContent = err.message || "Failed to load current session";
    });
