import json
import sys
from pathlib import Path

import requests

BASE = "http://localhost:8080"
TENANT_CODE = "datn_demo_moho"
DATASET_ID = "gotrangtri-20260610"
ARTIFACT_ID = "767a5866-ff31-4ae6-a33f-45601395512e"
OUT_DIR = Path("tmp")
LOGIN_PAYLOAD = {"name": "admin", "code": "admin123"}
MESSAGES = [
    ("new", "/new"),
    ("tu_quan_ao", "Tôi muốn mua tủ quần áo"),
    ("ban_lam_viec", "Có bàn làm việc nào phù hợp phòng nhỏ không?"),
    ("sofa", "Tư vấn sofa cho phòng khách nhỏ ngân sách 5 triệu"),
]

session = requests.Session()


def request_json(method, path, *, json_body=None, headers=None, timeout=180):
    response = session.request(method, BASE + path, json=json_body, headers=headers, timeout=timeout)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    return response.status_code, payload


def require_ok(status, payload, label):
    if status >= 400:
        raise RuntimeError(f"{label} failed: {status} {json.dumps(payload, ensure_ascii=False)[:600]}")


def write_json(name, data):
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def main():
    status, login = request_json("POST", "/api/login/admin", json_body=LOGIN_PAYLOAD)
    require_ok(status, login, "admin login")

    status, datasets = request_json("GET", "/api/admin/product-datasets")
    require_ok(status, datasets, "list datasets")
    dataset = next((item for item in datasets if item.get("datasetId") == DATASET_ID or item.get("dataset_id") == DATASET_ID), None)
    if not dataset:
        raise RuntimeError(f"dataset {DATASET_ID} not found")
    dataset_record_id = dataset.get("id")

    status, artifacts = request_json("GET", f"/api/admin/product-datasets/{dataset_record_id}/artifacts")
    require_ok(status, artifacts, "list artifacts")
    artifact = next((item for item in artifacts if item.get("id") == ARTIFACT_ID), None) or (artifacts[0] if artifacts else None)

    product_dataset_evidence = {
        "surface": "admin Product Dataset Registry APIs used by UI",
        "dataset": dataset,
        "artifacts": artifacts,
        "checks": {
            "dataset_present": dataset is not None,
            "artifact_present": artifact is not None,
            "artifact_6070": bool(artifact and (artifact.get("artifactCount") == 6070 or artifact.get("artifact_count") == 6070)),
            "build_action_endpoint": f"POST /api/admin/product-datasets/{dataset_record_id}/artifacts/build",
            "bind_action_endpoint": "POST /api/admin/product-datasets/kb-bindings/bind",
        },
    }
    write_json("ui_product_dataset_registry_verify.json", product_dataset_evidence)

    status, tenants = request_json("GET", "/api/admin/tenants")
    require_ok(status, tenants, "list tenants")
    tenant = next((item for item in tenants if item.get("code") == TENANT_CODE), None)
    if not tenant:
        raise RuntimeError(f"tenant {TENANT_CODE} not found")
    headers = {"X-Tenant-Id": tenant["id"]}
    if tenant.get("apiKey"):
        headers["X-API-Key"] = tenant["apiKey"]

    active_version_id = tenant.get("activeKbVersionId") or tenant.get("active_kb_version_id")
    active_version_tag = tenant.get("activeKbVersionTag") or tenant.get("active_kb_version_tag")
    active_kb_dir = tenant.get("activeKbDir") or tenant.get("active_kb_dir") or ""
    tenant_evidence = {
        "surface": "admin Tenant Management API used by UI",
        "tenant": tenant,
        "checks": {
            "tenant_present": True,
            "active_kb_version_present": bool(active_version_id or active_version_tag),
            "active_kb_dir_points_to_dataset_artifact": DATASET_ID in active_kb_dir,
            "fallback_kb_dir_legacy": tenant.get("kbDir") == "/opt/app/chatbot/kb/datn_demo_moho",
            "unbind_action_endpoint": "POST /api/admin/product-datasets/kb-bindings/unbind",
        },
    }
    write_json("ui_tenant_management_verify.json", tenant_evidence)

    status, runtime_before = request_json("GET", "/api/kb/runtime-status", headers=headers)
    require_ok(status, runtime_before, "runtime before chat")

    status, chatbots = request_json("GET", "/api/chatbots", headers=headers)
    require_ok(status, chatbots, "list chatbots")
    if not chatbots:
        raise RuntimeError("No chatbot available")
    chatbot = chatbots[0]

    user_external_id = "phase-polish-utf8"
    status, started = request_json(
        "POST",
        "/api/chat/start",
        json_body={"chatbotId": chatbot["id"], "userExternalId": user_external_id},
        headers=headers,
    )
    require_ok(status, started, "start chat")
    conversation_id = started["conversationId"]

    smoke = {
        "tenant": {"id": tenant["id"], "code": tenant.get("code")},
        "chatbot": chatbot,
        "conversationId": conversation_id,
        "runtime_before": runtime_before,
        "messages": [],
    }

    retrieval_files = {
        "tu_quan_ao": "chat_retrieval_debug_tu_quan_ao.json",
        "ban_lam_viec": "chat_retrieval_debug_ban_lam_viec.json",
        "sofa": "chat_retrieval_debug_sofa.json",
    }

    for key, message in MESSAGES:
        status, payload = request_json(
            "POST",
            "/api/chat/send",
            json_body={
                "conversationId": conversation_id,
                "userExternalId": user_external_id,
                "message": message,
            },
            headers=headers,
            timeout=240,
        )
        entry = {"key": key, "message": message, "status": status, "response": payload}
        smoke["messages"].append(entry)
        if key in retrieval_files:
            write_json(retrieval_files[key], entry)

    status, runtime_after = request_json("GET", "/api/kb/runtime-status", headers=headers)
    require_ok(status, runtime_after, "runtime after chat")
    smoke["runtime_after"] = runtime_after
    write_json("chat_smoke_after_fix.json", smoke)
    write_json("runtime_status_after_chat_fix.json", runtime_after)

    summary = {
        "product_dataset_registry": product_dataset_evidence["checks"],
        "tenant_management": tenant_evidence["checks"],
        "runtime_before": runtime_before,
        "runtime_after": runtime_after,
        "chat_messages": [
            {
                "key": item["key"],
                "status": item["status"],
                "answer_preview": str(item["response"].get("message") or item["response"].get("answer") or item["response"])[:600],
            }
            for item in smoke["messages"]
        ],
    }
    write_json("phase_polish_summary.json", summary)
    sys.stdout.buffer.write((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
