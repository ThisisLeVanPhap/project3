import json
from pathlib import Path

import requests

# Lazy-load verification only:
# - publish/rebuild updates desired KB and evicts current runtime
# - a real chat request is required before running runtime reflects the new KB
# This script verifies that contract; it does not verify prewarm-after-publish behavior.

BASE = "http://localhost:8080"
TENANT_CODE = "datn_demo_moho"
LOGIN_PAYLOAD = {"name": "admin", "code": "admin123"}
PRODUCT_URL_PAYLOAD = {"url": "https://gotrangtri.vn/shop/ban-sofa-ghs-1/"}
CHAT_MESSAGE = "xin chao"
USER_EXTERNAL_ID = "kb-runtime-smoke"
OUT_DIR = Path("tmp")

session = requests.Session()


def safe_print(text: str):
    encoded = text.encode("cp1252", errors="replace").decode("cp1252")
    print(encoded)



def preview(text: str, limit: int = 220) -> str:
    text = (text or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]



def request_json(method: str, path: str, *, json_body=None, headers=None):
    response = session.request(method, BASE + path, json=json_body, headers=headers, timeout=180)
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



def get_or_set_source_urls(headers):
    response, payload = request_json("POST", "/api/kb/source-urls", json_body=PRODUCT_URL_PAYLOAD, headers=headers)
    require_ok(response, "set source urls")
    return payload



def rebuild(headers):
    response, payload = request_json("POST", "/api/kb/rebuild", headers=headers)
    require_ok(response, "rebuild kb")
    return payload



def list_versions(headers):
    response, payload = request_json("GET", "/api/kb/versions", headers=headers)
    require_ok(response, "list kb versions")
    return payload



def choose_publish_target(versions):
    ready_non_active = [item for item in versions if item.get("status") == "READY" and not item.get("active")]
    if not ready_non_active:
        raise RuntimeError("No READY non-active KB version found after rebuild")
    ready_non_active.sort(key=lambda item: (item.get("built_at") or "", item.get("created_at") or "", item.get("version_tag") or ""), reverse=True)
    return ready_non_active[0]



def publish(headers, version_id):
    response, payload = request_json("POST", f"/api/kb/versions/{version_id}/publish", headers=headers)
    require_ok(response, "publish kb version")
    return payload



def runtime_status(headers):
    response, payload = request_json("GET", "/api/kb/runtime-status", headers=headers)
    require_ok(response, "runtime status")
    return payload



def pick_chatbot(headers):
    response, payload = request_json("GET", "/api/chatbots", headers=headers)
    require_ok(response, "list chatbots")
    if not payload:
        raise RuntimeError("No chatbot available for tenant")
    return payload[0]



def start_chat(headers, chatbot_id):
    response, payload = request_json(
        "POST",
        "/api/chat/start",
        json_body={"chatbotId": chatbot_id, "userExternalId": USER_EXTERNAL_ID},
        headers=headers,
    )
    require_ok(response, "chat start")
    return payload



def send_chat(headers, conversation_id):
    response, payload = request_json(
        "POST",
        "/api/chat/send",
        json_body={
            "conversationId": conversation_id,
            "userExternalId": USER_EXTERNAL_ID,
            "message": CHAT_MESSAGE,
        },
        headers=headers,
    )
    require_ok(response, "chat send")
    return payload



def main():
    OUT_DIR.mkdir(exist_ok=True)

    login_admin()
    tenant, headers = load_tenant_scope()
    get_or_set_source_urls(headers)

    rebuild_payload = rebuild(headers)
    rebuild_file = write_json("kb_lazy_verify_rebuild_response.json", rebuild_payload)

    versions = list_versions(headers)
    publish_target = choose_publish_target(versions)
    publish_payload = publish(headers, publish_target["id"])
    publish_file = write_json("kb_lazy_verify_publish_response.json", publish_payload)

    runtime_after_publish = runtime_status(headers)
    runtime_after_publish_file = write_json(
        "kb_lazy_verify_runtime_status_after_publish.json",
        runtime_after_publish,
    )

    chatbot = pick_chatbot(headers)
    chat_start = start_chat(headers, chatbot["id"])
    chat_payload = send_chat(headers, chat_start["conversationId"])
    chat_file = write_json("kb_lazy_verify_chat_response.json", {
        "chatbotId": chatbot["id"],
        "conversationId": chat_start["conversationId"],
        "response": chat_payload,
    })

    runtime_after_chat = runtime_status(headers)
    runtime_after_chat_file = write_json(
        "kb_lazy_verify_runtime_status_after_chat.json",
        runtime_after_chat,
    )

    desired_after_publish = (runtime_after_publish or {}).get("desired") or {}
    running_after_publish = (runtime_after_publish or {}).get("running") or {}
    desired_after_chat = (runtime_after_chat or {}).get("desired") or {}
    running_after_chat = (runtime_after_chat or {}).get("running") or {}

    summary = {
        "verify_method": "lazy-load verification (publish -> desired, chat -> running)",
        "tenant": {
            "id": tenant.get("id"),
            "code": tenant.get("code"),
            "kbDir": tenant.get("kbDir"),
        },
        "rebuilt_version": {
            "version_id": publish_target.get("id"),
            "version_tag": publish_target.get("version_tag"),
            "kb_dir": publish_target.get("kb_dir"),
        },
        "phase_after_publish": {
            "desired_version_id": desired_after_publish.get("version_id"),
            "desired_version_tag": desired_after_publish.get("version_tag"),
            "running_present": runtime_after_publish.get("running") is not None,
            "running_version_id": running_after_publish.get("version_id"),
            "running_version_tag": running_after_publish.get("version_tag"),
            "in_sync": runtime_after_publish.get("in_sync"),
            "expected": "desired must point to new version; running may still be absent or stale until chat",
        },
        "phase_after_chat": {
            "chat_status": 200,
            "llm_base_url": (chat_payload or {}).get("llmBaseUrl"),
            "chat_model": (chat_payload or {}).get("model"),
            "desired_version_id": desired_after_chat.get("version_id"),
            "desired_version_tag": desired_after_chat.get("version_tag"),
            "running_present": runtime_after_chat.get("running") is not None,
            "running_version_id": running_after_chat.get("version_id"),
            "running_version_tag": running_after_chat.get("version_tag"),
            "running_kb_dir": running_after_chat.get("running", {}).get("kb_dir"),
            "running_mode": running_after_chat.get("running", {}).get("mode"),
            "running_process_alive": running_after_chat.get("running", {}).get("process_alive"),
            "in_sync": runtime_after_chat.get("in_sync"),
            "expected": "after real chat, running snapshot should exist and should be consistent with desired when fields are exposed",
        },
        "evidence_files": {
            "rebuild_response": rebuild_file,
            "publish_response": publish_file,
            "runtime_status_after_publish": runtime_after_publish_file,
            "chat_response": chat_file,
            "runtime_status_after_chat": runtime_after_chat_file,
        },
    }
    summary_file = write_json("kb_lazy_verify_summary.json", summary)
    safe_print(f"WROTE {summary_file}")


if __name__ == "__main__":
    main()
