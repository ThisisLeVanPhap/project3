export const storage = {
  get adminBasic() { return localStorage.getItem("adminBasic") || ""; },
  set adminBasic(v: string) { localStorage.setItem("adminBasic", v); },

  get tenantId() { return localStorage.getItem("tenantId") || ""; },
  set tenantId(v: string) { localStorage.setItem("tenantId", v); },

  get tenantApiKey() { return localStorage.getItem("tenantApiKey") || ""; },
  set tenantApiKey(v: string) { localStorage.setItem("tenantApiKey", v); },
};
