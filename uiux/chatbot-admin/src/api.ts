const BASE_URL = "http://localhost:8080";

type Json = Record<string, any>;

async function http<T>(
  path: string,
  opts: RequestInit & { headers?: Record<string, string> } = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
    },
  });

  // cố đọc JSON; nếu không có thì đọc text
  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;

  if (!res.ok) {
    const msg = typeof data === "string" ? data : JSON.stringify(data);
    throw new Error(`${res.status} ${res.statusText}: ${msg}`);
  }
  return data as T;
}

export function createTenant(params: {
  adminBasic: string; // "Basic xxx"
  code: string;
  name: string;
}) {
  return http<Json>("/api/admin/tenants", {
    method: "POST",
    headers: {
      "Authorization": params.adminBasic,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ code: params.code, name: params.name }),
  });
}

export function createChatbot(params: {
  apiKey: string;
  payload: Json;
}) {
  return http<Json>("/api/chatbots", {
    method: "POST",
    headers: {
      "X-API-Key": params.apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params.payload),
  });
}

export function bindMessenger(params: {
  apiKey: string;
  pageId: string;
  chatbotId: string;
  pageAccessToken: string;
}) {
  return http<Json>("/api/messenger/bindings", {
    method: "POST",
    headers: {
      "X-API-Key": params.apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      pageId: params.pageId,
      chatbotId: params.chatbotId,
      pageAccessToken: params.pageAccessToken,
    }),
  });
}

// List chatbots - ưu tiên đúng theo cURL bạn đưa (Basic + X-Tenant-Id),
// có fallback dùng X-API-Key nếu bạn muốn
export function listChatbots(params: {
  tenantId?: string;
  adminBasic?: string;
  apiKey?: string;
}) {
  const headers: Record<string, string> = {};
  if (params.tenantId) headers["X-Tenant-Id"] = params.tenantId;
  if (params.adminBasic) headers["Authorization"] = params.adminBasic;
  if (params.apiKey) headers["X-API-Key"] = params.apiKey;

  return http<Json[]>("/api/chatbots", { method: "GET", headers });
}
