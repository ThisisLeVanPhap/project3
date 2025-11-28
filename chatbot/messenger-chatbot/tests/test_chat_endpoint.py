import json
from fastapi.testclient import TestClient
from app.server import app


client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200


def test_chat_smoke(monkeypatch):
    # mock the pipeline to avoid heavy model in CI
    from app import server


    class Dummy:
        tokenizer = type("T", (), {"eos_token_id": 0})
        def __call__(self, *args, **kwargs):
            return [{"generated_text": "### Response:\nXin chào!"}]


    monkeypatch.setattr(server, "pipe", Dummy())
    r = client.post("/chat", json={"message": "Hi"})
    assert r.status_code == 200
    assert "reply" in r.json()