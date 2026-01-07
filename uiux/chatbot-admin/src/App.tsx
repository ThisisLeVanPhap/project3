import React, { useEffect, useState } from "react";
import { bindMessenger, createChatbot, createTenant, listChatbots } from "./api";
import { storage } from "./storage";

type Chatbot = { id: string; name?: string; channel?: string };

export default function App() {
  const [adminBasic, setAdminBasic] = useState(storage.adminBasic || "Basic YWRtaW46YWRtaW4xMjM=");
  const [tenantId, setTenantId] = useState(storage.tenantId);
  const [tenantApiKey, setTenantApiKey] = useState(storage.tenantApiKey);

  // Step 1
  const [tenantCode, setTenantCode] = useState("demo_gk");
  const [tenantName, setTenantName] = useState("demo_gk");

  // Step 2
  const [botPayload, setBotPayload] = useState(JSON.stringify({
    name: "Bot A",
    channel: "web",
    personaJson: "{\"tone\":\"am ap\"}",
    baseModel: "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    adapterPath: "out/lora_adapter",
    tokenizerPath: "out/tokenizer",
    systemPrompt: "Bạn là trợ lý bán hàng đồ gỗ. Trả lời ngắn gọn 3-5 câu.",
    maxNewTokens: 256,
    temperature: 0.7,
    topP: 0.9,
    topK: 50
  }, null, 2));

  // Step 3
  const [pageId, setPageId] = useState("888907290975630");
  const [pageAccessToken, setPageAccessToken] = useState("");
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [selectedBotId, setSelectedBotId] = useState("");

  const [log, setLog] = useState<string>("");

  function append(s: string) {
    setLog((prev) => prev + (prev ? "\n" : "") + s);
  }

  useEffect(() => {
    storage.adminBasic = adminBasic;
  }, [adminBasic]);

  useEffect(() => {
    storage.tenantId = tenantId;
  }, [tenantId]);

  useEffect(() => {
    storage.tenantApiKey = tenantApiKey;
  }, [tenantApiKey]);

  async function refreshBots() {
    try {
      // ưu tiên theo cURL của bạn
      const list = await listChatbots({ tenantId, adminBasic });
      const normalized = (list || []).map((x: any) => ({ id: x.id, name: x.name, channel: x.channel }));
      setChatbots(normalized);
      if (!selectedBotId && normalized[0]?.id) setSelectedBotId(normalized[0].id);
      append(`✅ Loaded ${normalized.length} chatbots`);
    } catch (e: any) {
      // fallback: thử bằng apiKey (nếu endpoint cho phép)
      try {
        const list2 = await listChatbots({ apiKey: tenantApiKey });
        const normalized2 = (list2 || []).map((x: any) => ({ id: x.id, name: x.name, channel: x.channel }));
        setChatbots(normalized2);
        if (!selectedBotId && normalized2[0]?.id) setSelectedBotId(normalized2[0].id);
        append(`✅ Loaded ${normalized2.length} chatbots (fallback by X-API-Key)`);
      } catch (e2: any) {
        append(`❌ Load chatbots failed: ${e.message}`);
      }
    }
  }

  async function onCreateTenant() {
    try {
      const res = await createTenant({ adminBasic, code: tenantCode, name: tenantName });
      append("✅ Create tenant OK:");
      append(JSON.stringify(res, null, 2));

      // cố gắng auto set tenantId/apiKey nếu backend trả về
      if (res?.id) setTenantId(res.id);
      if (res?.apiKey) setTenantApiKey(res.apiKey);
    } catch (e: any) {
      append(`❌ Create tenant failed: ${e.message}`);
    }
  }

  async function onCreateChatbot() {
    try {
      const payload = JSON.parse(botPayload);
      const res = await createChatbot({ apiKey: tenantApiKey, payload });
      append("✅ Create chatbot OK:");
      append(JSON.stringify(res, null, 2));
      await refreshBots();
    } catch (e: any) {
      append(`❌ Create chatbot failed: ${e.message}`);
    }
  }

  async function onBind() {
    try {
      const res = await bindMessenger({
        apiKey: tenantApiKey,
        pageId,
        chatbotId: selectedBotId,
        pageAccessToken,
      });
      append("✅ Bind OK:");
      append(JSON.stringify(res, null, 2));
    } catch (e: any) {
      append(`❌ Bind failed: ${e.message}`);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui", padding: 16, maxWidth: 980, margin: "0 auto" }}>
      <h2>Chatbot Admin Console</h2>
      <p style={{ color: "#666" }}>
        3 bước: Create Tenant → Create Chatbot → Bind Messenger Page
      </p>

      <div style={{ display: "grid", gap: 12 }}>
        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <h3>Global Settings</h3>
          <label style={{ display: "block", marginBottom: 6 }}>Admin Basic Auth</label>
          <input style={{ width: "100%" }} value={adminBasic} onChange={(e) => setAdminBasic(e.target.value)} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 8 }}>
            <div>
              <label style={{ display: "block", marginBottom: 6 }}>Tenant ID (UUID)</label>
              <input style={{ width: "100%" }} value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 6 }}>Tenant API Key</label>
              <input style={{ width: "100%" }} value={tenantApiKey} onChange={(e) => setTenantApiKey(e.target.value)} />
            </div>
          </div>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <h3>Step 1 — Create Tenant</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 12, alignItems: "end" }}>
            <div>
              <label style={{ display: "block", marginBottom: 6 }}>code</label>
              <input style={{ width: "100%" }} value={tenantCode} onChange={(e) => setTenantCode(e.target.value)} />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 6 }}>name</label>
              <input style={{ width: "100%" }} value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
            </div>
            <button onClick={onCreateTenant}>Create</button>
          </div>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <h3>Step 2 — Create Chatbot</h3>
          <p style={{ color: "#666", marginTop: 0 }}>
            Header: <code>X-API-Key</code>
          </p>
          <textarea style={{ width: "100%", height: 180 }} value={botPayload} onChange={(e) => setBotPayload(e.target.value)} />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={onCreateChatbot}>Create Chatbot</button>
            <button onClick={refreshBots}>Refresh Chatbots</button>
          </div>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <h3>Step 3 — Bind Messenger Page</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ display: "block", marginBottom: 6 }}>pageId</label>
              <input style={{ width: "100%" }} value={pageId} onChange={(e) => setPageId(e.target.value)} />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: 6 }}>chatbotId</label>
              <select style={{ width: "100%" }} value={selectedBotId} onChange={(e) => setSelectedBotId(e.target.value)}>
                <option value="">-- Select chatbot --</option>
                {chatbots.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name || b.id} {b.channel ? `(${b.channel})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ display: "block", marginBottom: 6 }}>pageAccessToken</label>
            <input style={{ width: "100%" }} value={pageAccessToken} onChange={(e) => setPageAccessToken(e.target.value)} />
          </div>

          <div style={{ marginTop: 8 }}>
            <button onClick={onBind} disabled={!selectedBotId || !pageId || !pageAccessToken}>
              Bind
            </button>
          </div>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <h3>Logs</h3>
          <pre style={{ whiteSpace: "pre-wrap" }}>{log || "..."}</pre>
        </section>
      </div>
    </div>
  );
}
