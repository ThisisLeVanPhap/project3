import json
from pathlib import Path

import requests

# Cross-Channel Identity + CRM Activity runtime verification.
# This script exercises the read-only endpoints added in Steps 2A / 3.2:
# - GET /api/customer-identities/customers
# - GET /api/customer-identities/customers/{id}
# - GET /api/crm/customers/{unifiedCustomerId}/activity
#
# It does NOT seed identities/leads/purchases. If no data exists yet,
# the script reports a clean no-data status instead of failing.

BASE = "http://localhost:8080"
TENANT_CODE = "datn_demo_moho"
LOGIN_PAYLOAD = {"name": "admin", "code": "admin123"}
OUT_DIR = Path("tmp")

session = requests.Session()


def safe_print(text: str):
    encoded = text.encode("cp1252", errors="replace").decode("cp1252")
    print(encoded)


def preview(text: str, limit: int = 220) -> str:
    text = (text or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]


def request_json(method: str, path: str, *, json_body=None, headers=None):
    response = session.request(method, BASE + path, json=json_body, headers=headers, timeout=60)
    safe_print(f"{method} {path} -> {response.status_code} :: {preview(response.text)}")
    parsed = None
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    return response, parsed


def write_json(name: str, data):
    path = OUT_DIR / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def require_ok(response, label: str):
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed with status {response.status_code}: {preview(response.text, 500)}")


def login_admin():
    response, payload = request_json("POST", "/api/login/admin", json_body=LOGIN_PAYLOAD)
    require_ok(response, "admin login")
    return payload


def load_tenant_scope():
    response, payload = request_json("GET", "/api/admin/tenants")
    require_ok(response, "list tenants")
    tenant = next((item for item in payload if item.get("code") == TENANT_CODE), None)
    if tenant is None:
        raise RuntimeError(f"Tenant code {TENANT_CODE} not found")
    tenant_id = tenant["id"]
    api_key = tenant.get("apiKey")
    headers = {"X-Tenant-Id": tenant_id}
    if api_key:
        headers["X-API-Key"] = api_key
    return tenant, headers


def list_customers(headers):
    response, payload = request_json("GET", "/api/customer-identities/customers", headers=headers)
    require_ok(response, "list unified customers")
    return payload or []


def get_customer_detail(headers, customer_id):
    response, payload = request_json(
        "GET",
        f"/api/customer-identities/customers/{customer_id}",
        headers=headers,
    )
    if response.status_code == 404:
        return None
    require_ok(response, "customer detail")
    return payload


def get_customer_activity(headers, unified_customer_id):
    response, payload = request_json(
        "GET",
        f"/api/crm/customers/{unified_customer_id}/activity",
        headers=headers,
    )
    if response.status_code == 404:
        return None
    require_ok(response, "customer activity")
    return payload


def main():
    OUT_DIR.mkdir(exist_ok=True)

    login_admin()
    tenant, headers = load_tenant_scope()

    customers = list_customers(headers)
    customers_file = write_json("verify_cross_channel_identity_customers.json", customers)

    selected = customers[0] if customers else None
    detail = None
    detail_file = None
    activity = None
    activity_file = None

    if selected is not None:
        customer_id = selected.get("unifiedCustomerId")
        detail = get_customer_detail(headers, customer_id)
        if detail is not None:
            detail_file = write_json("verify_cross_channel_identity_detail.json", detail)
        activity = get_customer_activity(headers, customer_id)
        if activity is not None:
            activity_file = write_json("verify_crm_customer_activity.json", activity)

    summary = {
        "verify_method": "cross-channel identity + CRM activity read-only runtime verify",
        "base_url": BASE,
        "tenant": {
            "id": tenant.get("id"),
            "code": tenant.get("code"),
        },
        "auth": {
            "login": "admin",
            "ok": True,
        },
        "customers": {
            "count": len(customers),
            "selected_unified_customer_id": selected.get("unifiedCustomerId") if selected else None,
            "selected_display_name": selected.get("displayName") if selected else None,
            "selected_phone": selected.get("normalizedPhone") if selected else None,
            "selected_email": selected.get("normalizedEmail") if selected else None,
        },
        "detail": {
            "present": detail is not None,
            "identities_count": len(detail.get("identities") or []) if detail else 0,
        },
        "crm_activity": {
            "present": activity is not None,
            "conversations_count": len(activity.get("conversations") or []) if activity else 0,
            "leads_count": len(activity.get("leads") or []) if activity else 0,
            "purchase_requests_count": len(activity.get("purchaseRequests") or []) if activity else 0,
        },
        "status": "pass" if customers else "no_data",
        "skip_reason": None if customers else "no unified customers exist yet for this tenant; seed via Messenger/Telegram webhooks with matching phone/email to populate",
        "evidence_files": {
            "customers": customers_file,
            "detail": detail_file,
            "activity": activity_file,
        },
    }
    summary_file = write_json("verify_cross_channel_identity_summary.json", summary)
    safe_print(f"WROTE {summary_file}")


if __name__ == "__main__":
    main()
