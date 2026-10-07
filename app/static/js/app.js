/**
 * Galactic Auction — frontend application logic.
 * No framework: plain DOM manipulation over a small state object.
 */
(() => {
  const state = {
    me: null,
    auctions: [],
    selectedAuctionId: null,
    ws: null,
  };

  const el = (id) => document.getElementById(id);
  const qs = (sel, root = document) => root.querySelector(sel);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const STATUS_LABEL = { active: "Триває", scheduled: "Заплановано", finished: "Завершено" };

  // ---------------------------------------------------------------- toast
  let toastTimer = null;
  function toast(message, kind = "info") {
    const node = el("toast");
    node.textContent = message;
    node.className = `toast is-visible${kind === "error" ? " is-error" : ""}${kind === "success" ? " is-success" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("is-visible"), 3200);
  }

  function showFormError(name, error) {
    const node = qs(`[data-error="${name}"]`);
    if (!node) return;
    node.textContent = error ? (error.detail ?? String(error)) : "";
  }

  // ---------------------------------------------------------------- auth screen
  function initAuthScreen() {
    qsa(".auth-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        qsa(".auth-tab").forEach((t) => t.classList.toggle("is-active", t === tab));
        el("login-form").classList.toggle("is-hidden", tab.dataset.tab !== "login");
        el("register-form").classList.toggle("is-hidden", tab.dataset.tab !== "register");
      });
    });

    el("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      showFormError("login", null);
      const data = new FormData(event.target);
      try {
        const { access_token } = await Api.login(data.get("username"), data.get("password"));
        Api.setToken(access_token);
        await enterApp();
      } catch (err) {
        showFormError("login", err);
      }
    });

    el("register-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      showFormError("register", null);
      const data = new FormData(event.target);
      try {
        await Api.register(data.get("username"), data.get("email"), data.get("password"));
        toast("Акаунт створено, тепер увійдіть", "success");
        qs('[data-tab="login"]').click();
        event.target.reset();
      } catch (err) {
        showFormError("register", err);
      }
    });
  }

  function showAuthScreen() {
    el("auth-screen").classList.remove("is-hidden");
    el("app-screen").classList.add("is-hidden");
    closeSocket();
  }

  // ---------------------------------------------------------------- app shell / nav
  function initNav() {
    qsa(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.dataset.view));
    });
    el("logout-btn").addEventListener("click", () => {
      Api.setToken(null);
      state.me = null;
      showAuthScreen();
    });
  }

  function switchView(view) {
    qsa(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === view));
    qsa(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${view}`));
    if (view === "profile") loadProfile();
    if (view === "admin") loadAdmin();
  }

  function renderMe() {
    el("me-username").textContent = state.me.username;
    el("me-role").textContent = state.me.role;
    el("me-balance").textContent = formatMoney(state.me.balance);
    el("nav-admin").classList.toggle("is-hidden", state.me.role !== "admin");
  }

  async function enterApp() {
    try {
      state.me = await Api.me();
    } catch (err) {
      Api.setToken(null);
      showAuthScreen();
      toast("Сесія недійсна, увійдіть знову", "error");
      return;
    }
    renderMe();
    el("auth-screen").classList.add("is-hidden");
    el("app-screen").classList.remove("is-hidden");
    switchView("auctions");
    await loadAuctions();
  }

  function formatMoney(value) {
    return Number(value).toLocaleString("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatTime(iso) {
    return new Date(iso).toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" });
  }

  // ---------------------------------------------------------------- auctions list
  async function loadAuctions() {
    try {
      state.auctions = await Api.listAuctions();
    } catch (err) {
      toast(`Не вдалося завантажити аукціони: ${err.detail}`, "error");
      return;
    }
    renderAuctionList();
    if (state.selectedAuctionId) {
      const stillThere = state.auctions.some((a) => a.id === state.selectedAuctionId);
      if (stillThere) await selectAuction(state.selectedAuctionId, { keepSocket: true });
    }
  }

  function renderAuctionList() {
    const list = el("auction-list");
    list.innerHTML = "";
    if (state.auctions.length === 0) {
      list.innerHTML = '<p class="empty-hint">Поки що немає жодного лоту.</p>';
      return;
    }
    for (const auction of state.auctions) {
      const li = document.createElement("li");
      li.className = `auction-card${auction.id === state.selectedAuctionId ? " is-selected" : ""}`;
      li.innerHTML = `
        <span class="status-pill status-${auction.status}">${STATUS_LABEL[auction.status]}</span>
        <div class="auction-card-title">Лот #${auction.id}</div>
        <div class="auction-card-price">${formatMoney(auction.current_price)} cr</div>
      `;
      li.addEventListener("click", () => selectAuction(auction.id));
      list.appendChild(li);
    }
  }

  async function selectAuction(auctionId, { keepSocket = false } = {}) {
    state.selectedAuctionId = auctionId;
    renderAuctionList();
    if (!keepSocket) connectSocket(auctionId);

    let auction, bids;
    try {
      [auction, bids] = await Promise.all([Api.getAuction(auctionId), Api.listBids(auctionId)]);
    } catch (err) {
      toast(`Не вдалося відкрити лот: ${err.detail}`, "error");
      return;
    }
    renderAuctionDetail(auction, bids);
  }

  function renderAuctionDetail(auction, bids) {
    const detail = el("auction-detail");
    const isActive = auction.status === "active";
    const canBid = isActive && state.me.role === "user";

    detail.innerHTML = `
      <span class="status-pill status-${auction.status}">${STATUS_LABEL[auction.status]}</span>
      <h3 class="detail-title">Лот #${auction.id} &middot; артефакт #${auction.artifact_id}</h3>
      <p class="detail-meta">
        <span class="live-dot${state.ws ? " is-connected" : ""}"></span>
        ${formatTime(auction.starts_at)} &rarr; ${formatTime(auction.ends_at)}
      </p>
      <div class="price-board">
        <div>
          <div class="label">Поточна ціна</div>
          <div class="value" id="current-price">${formatMoney(auction.current_price)} cr</div>
        </div>
        <div>
          <div class="label">Лідер</div>
          <div class="value" style="font-size:16px">${auction.highest_bidder_id ?? "&mdash;"}</div>
        </div>
      </div>
      ${
        state.me.role === "admin"
          ? `<button class="btn btn-danger" id="close-auction-btn" ${isActive ? "" : "disabled"}>Закрити торги</button>`
          : `<form class="bid-form" id="bid-form">
               <input type="number" name="amount" min="0.01" step="0.01" placeholder="Ваша ставка" ${canBid ? "" : "disabled"} required />
               <button type="submit" class="btn btn-primary" ${canBid ? "" : "disabled"}>Зробити ставку</button>
             </form>
             <p class="form-error" data-error="bid"></p>`
      }
      <ul class="bid-history" id="bid-history"></ul>
    `;

    renderBidHistory(bids);

    const bidForm = el("bid-form");
    if (bidForm) {
      bidForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showFormError("bid", null);
        const amount = new FormData(event.target).get("amount");
        try {
          await Api.placeBid(auction.id, amount);
          event.target.reset();
        } catch (err) {
          showFormError("bid", err);
        }
      });
    }

    const closeBtn = el("close-auction-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", async () => {
        try {
          await Api.closeAuction(auction.id);
          toast("Аукціон закрито", "success");
          await loadAuctions();
        } catch (err) {
          toast(err.detail, "error");
        }
      });
    }
  }

  function renderBidHistory(bids, { prependLive } = {}) {
    const list = el("bid-history");
    if (!list) return;
    if (!prependLive) {
      list.innerHTML = bids.length
        ? ""
        : '<li class="bid-row"><span class="empty-hint">Ставок ще не було</span></li>';
      for (const bid of bids) list.appendChild(bidRow(bid));
    } else {
      const row = bidRow(prependLive);
      row.classList.add("is-live");
      list.prepend(row);
    }
  }

  function bidRow(bid) {
    const li = document.createElement("li");
    li.className = "bid-row";
    li.innerHTML = `<span>Користувач #${bid.user_id}</span><span class="amount">${formatMoney(bid.amount)} cr</span>`;
    return li;
  }

  // ---------------------------------------------------------------- websocket
  function connectSocket(auctionId) {
    closeSocket();
    const ws = new WebSocket(Api.wsUrl(auctionId));
    state.ws = ws;

    ws.addEventListener("open", () => {
      const dot = qs(".live-dot");
      if (dot) dot.classList.add("is-connected");
    });

    ws.addEventListener("message", (event) => {
      if (event.data === "pong") return;
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (payload.auction_id !== state.selectedAuctionId) return;

      if (payload.type === "new_bid") {
        const priceNode = el("current-price");
        if (priceNode) priceNode.textContent = `${formatMoney(payload.amount)} cr`;
        renderBidHistory(null, {
          prependLive: { user_id: payload.user_id, amount: payload.amount },
        });
        loadAuctions();
      } else if (payload.type === "auction_closed") {
        toast(`Аукціон #${payload.auction_id} закрито`, "success");
        loadAuctions();
      }
    });

    ws.addEventListener("close", () => {
      if (state.ws === ws) state.ws = null;
      const dot = qs(".live-dot");
      if (dot) dot.classList.remove("is-connected");
    });
  }

  function closeSocket() {
    if (state.ws) {
      state.ws.close();
      state.ws = null;
    }
  }

  el("refresh-auctions").addEventListener("click", loadAuctions);

  // ---------------------------------------------------------------- profile view
  async function loadProfile() {
    try {
      const bids = await Api.myBids(state.me.id);
      const list = el("my-bids");
      list.innerHTML = bids.length
        ? ""
        : '<li class="bid-row"><span class="empty-hint">Ви ще не робили ставок</span></li>';
      for (const bid of bids) {
        const li = document.createElement("li");
        li.className = "bid-row";
        li.innerHTML = `<span>Лот #${bid.auction_id}</span><span class="amount">${formatMoney(bid.amount)} cr</span>`;
        list.appendChild(li);
      }
    } catch (err) {
      toast(`Не вдалося завантажити ставки: ${err.detail}`, "error");
    }
  }

  el("deposit-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("deposit", null);
    const amount = new FormData(event.target).get("amount");
    try {
      state.me = await Api.deposit(state.me.id, amount);
      renderMe();
      event.target.reset();
      toast("Баланс поповнено", "success");
    } catch (err) {
      showFormError("deposit", err);
    }
  });

  // ---------------------------------------------------------------- admin view
  async function loadAdmin() {
    await Promise.all([loadAdminStats(), loadUsersTable(), loadArtifactOptions()]);
  }

  async function loadAdminStats() {
    try {
      const stats = await Api.adminStats();
      const entries = [
        ["Користувачі", stats.users],
        ["Адміни", stats.admins],
        ["Аукціони", stats.auctions],
        ["Ставки", stats.bids],
      ];
      el("admin-stats").innerHTML = entries
        .map(([label, value]) => `<div class="stat-card"><div class="value">${value}</div><div class="label">${label}</div></div>`)
        .join("");
    } catch (err) {
      toast(`Статистика недоступна: ${err.detail}`, "error");
    }
  }

  async function loadUsersTable() {
    let users;
    try {
      users = await Api.adminListUsers();
    } catch (err) {
      toast(`Список користувачів недоступний: ${err.detail}`, "error");
      return;
    }
    const tbody = qs("#users-table tbody");
    tbody.innerHTML = "";
    for (const user of users) {
      const isSelf = user.id === state.me.id;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${user.username}</td>
        <td>${user.email}</td>
        <td><span class="role-badge ${user.role}">${user.role}</span></td>
        <td><span class="status-dot ${user.is_active ? "active" : "blocked"}"></span>${user.is_active ? "активний" : "заблокований"}</td>
        <td>${formatMoney(user.balance)}</td>
        <td class="row-actions"></td>
      `;
      const actions = qs(".row-actions", tr);
      if (!isSelf) {
        const roleBtn = document.createElement("button");
        roleBtn.className = "btn btn-ghost btn-sm";
        roleBtn.textContent = user.role === "admin" ? "Зробити user" : "Зробити admin";
        roleBtn.addEventListener("click", () => patchUser(user.id, { role: user.role === "admin" ? "user" : "admin" }));

        const blockBtn = document.createElement("button");
        blockBtn.className = "btn btn-ghost btn-sm";
        blockBtn.textContent = user.is_active ? "Заблокувати" : "Розблокувати";
        blockBtn.addEventListener("click", () => patchUser(user.id, { is_active: !user.is_active }));

        actions.append(roleBtn, blockBtn);
      } else {
        actions.textContent = "це ви";
      }
      tbody.appendChild(tr);
    }
  }

  async function patchUser(userId, payload) {
    try {
      await Api.adminUpdateUser(userId, payload);
      await loadUsersTable();
      toast("Збережено", "success");
    } catch (err) {
      toast(err.detail, "error");
    }
  }

  async function loadArtifactOptions() {
    let artifacts;
    try {
      artifacts = await Api.listArtifacts();
    } catch (err) {
      toast(`Список артефактів недоступний: ${err.detail}`, "error");
      return;
    }
    const select = el("artifact-select");
    select.innerHTML = artifacts.length
      ? artifacts.map((a) => `<option value="${a.id}">#${a.id} &middot; ${a.name}</option>`).join("")
      : '<option value="">Немає артефактів, створіть один</option>';
  }

  el("artifact-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("artifact", null);
    const data = new FormData(event.target);
    const payload = {
      name: data.get("name"),
      rarity: data.get("rarity") || "common",
      origin_galaxy: data.get("origin_galaxy") || null,
      description: data.get("description") || null,
    };
    try {
      await Api.createArtifact(payload);
      event.target.reset();
      toast("Артефакт створено", "success");
      await loadArtifactOptions();
    } catch (err) {
      showFormError("artifact", err);
    }
  });

  el("new-auction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("new-auction", null);
    const data = new FormData(event.target);
    const payload = {
      artifact_id: Number(data.get("artifact_id")),
      starting_price: data.get("starting_price"),
      starts_at: new Date(data.get("starts_at")).toISOString(),
      ends_at: new Date(data.get("ends_at")).toISOString(),
    };
    try {
      await Api.createAuction(payload);
      event.target.reset();
      toast("Аукціон створено", "success");
      await loadAuctions();
    } catch (err) {
      showFormError("new-auction", err);
    }
  });

  // ---------------------------------------------------------------- boot
  initAuthScreen();
  initNav();

  if (Api.getToken()) {
    enterApp();
  } else {
    showAuthScreen();
  }
})();
