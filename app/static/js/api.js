/**
 * Thin client for the Galactic Auction REST + WebSocket API.
 * Every failed call throws { status, detail } where detail is a readable string.
 */
const Api = (() => {
  const TOKEN_KEY = "ga_token";
  let token = localStorage.getItem(TOKEN_KEY);

  const getToken = () => token;
  const setToken = (value) => {
    token = value;
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  };

  // FastAPI returns detail as a string (HTTPException) or a list (422 validation).
  function normalizeDetail(detail, status) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
    return `Помилка сервера (${status})`;
  }

  async function request(path, { method = "GET", json, form, query } = {}) {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    let body;
    if (json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(json);
    } else if (form) {
      body = new URLSearchParams(form);
    }

    const url = query ? `${path}?${new URLSearchParams(query)}` : path;
    let res;
    try {
      res = await fetch(url, { method, headers, body });
    } catch {
      throw { status: 0, detail: "Немає зв'язку з сервером" };
    }

    if (res.status === 204) return null;
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* empty or non-JSON body */
    }
    if (!res.ok) throw { status: res.status, detail: normalizeDetail(data && data.detail, res.status) };
    return data;
  }

  return {
    getToken,
    setToken,

    // auth
    login: (username, password) => request("/auth/login", { method: "POST", form: { username, password } }),
    register: (username, email, password) =>
      request("/auth/register", { method: "POST", json: { username, email, password } }),
    me: () => request("/users/me"),

    // auctions & bids
    listAuctions: () => request("/auctions", { query: { limit: 100 } }),
    getAuction: (id) => request(`/auctions/${id}`),
    listBids: (id) => request(`/auctions/${id}/bids`, { query: { limit: 50 } }),
    placeBid: (id, amount) => request(`/auctions/${id}/bids`, { method: "POST", json: { amount: String(amount) } }),
    closeAuction: (id) => request(`/auctions/${id}/close`, { method: "POST" }),
    createAuction: (payload) => request("/auctions", { method: "POST", json: payload }),

    // artifacts
    listArtifacts: () => request("/artifacts", { query: { limit: 100 } }),
    createArtifact: (payload) => request("/artifacts", { method: "POST", json: payload }),

    // users
    deposit: (userId, amount) => request(`/users/${userId}/deposit`, { method: "POST", json: { amount: String(amount) } }),
    myBids: (userId) => request(`/users/${userId}/bids`),

    // admin
    adminStats: () => request("/admin/stats"),
    adminListUsers: () => request("/admin/users", { query: { limit: 100 } }),
    adminUpdateUser: (userId, payload) => request(`/admin/users/${userId}`, { method: "PATCH", json: payload }),

    // websocket (token goes in the query string, the server requires it)
    wsUrl: (auctionId) => {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${location.host}/ws/auctions/${auctionId}?token=${encodeURIComponent(token || "")}`;
    },
  };
})();
