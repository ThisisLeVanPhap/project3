from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200

def test_chat_smoke(monkeypatch):
    from app import server

    class Dummy:
        tokenizer = type("T", (), {"eos_token_id": 0})
        def __call__(self, prompt, **kwargs):
            return [{"generated_text": "### Assistant:\nXin chào!"}]

    monkeypatch.setattr(server, "get_or_create_pipe", lambda *args, **kwargs: Dummy())

    r = client.post("/chat", json={"message": "Hi"})
    assert r.status_code == 200
    assert r.json()["reply"]
