const API_BASE = "";

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  me: null,
  dates: [],
  selectedDate: null,
  selectedGroupId: null,
  search: ""
};

const el = {
  userRole: document.getElementById("userRole"),
  dates: document.getElementById("dates"),
  restaurantList: document.getElementById("restaurantList"),
  assignedRestaurant: document.getElementById("assignedRestaurant"),
  assignedRestaurantName: document.getElementById("assignedRestaurantName"),
  searchInput: document.getElementById("searchInput"),
  selectedDate: document.getElementById("selectedDate"),
  recordsCount: document.getElementById("recordsCount"),
  tableBody: document.getElementById("masterClassTable"),
  empty: document.getElementById("emptyMessage"),
  error: document.getElementById("errorMessage"),
  appTabs: document.getElementById("appTabs"),
  settingsTabButton: document.getElementById("settingsTabButton"),
  recordsView: document.getElementById("recordsView"),
  settingsView: document.getElementById("settingsView"),
  limitsHead: document.getElementById("limitsHead"),
  limitsBody: document.getElementById("limitsBody"),
  saveLimitsButton: document.getElementById("saveLimitsButton"),
  settingsSaveStatus: document.getElementById("settingsSaveStatus")
};

let limitsData = null;

function authHeaders(extra = {}) {
  return {
    "X-Telegram-Init-Data": tg?.initData || "",
    ...extra
  };
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {})
  });
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data.detail || "Помилка сервера");
  return data;
}

function formatDate(iso) {
  if (!iso) return "—";
  const [y,m,d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function shortDate(iso) {
  const [y,m,d] = iso.split("-");
  return `${d}.${m}`;
}

function roleName(role) {
  return ({developer:"Розробник", manager:"Керуючий", admin:"Адміністратор"})[role] || role;
}

async function loadMe() {
  state.me = await api("/api/me");
  el.userRole.textContent = `${state.me.name || ""}${state.me.name ? " · " : ""}${roleName(state.me.role)}`;
  if (el.settingsTabButton) el.settingsTabButton.hidden = state.me.role !== "developer";

  if (state.me.role === "admin") {
    el.restaurantList.style.display = "none";
    el.assignedRestaurant.style.display = "block";
    const names = state.me.restaurants.map(r => r.name).join(", ") || "Ресторан не призначено";
    el.assignedRestaurantName.textContent = names;
    state.selectedGroupId = state.me.restaurants.length === 1 ? state.me.restaurants[0].id : null;
  } else {
    el.restaurantList.style.display = "flex";
    el.assignedRestaurant.style.display = "none";
  }
}

async function loadDates() {
  const data = await api("/api/dates");
  state.dates = data.dates || [];
  const today = new Date();
  const todayIso = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  state.selectedDate = state.dates.find(d => d >= todayIso) || state.dates[state.dates.length - 1] || null;
  renderDates();
}

function renderDates() {
  el.dates.innerHTML = "";
  for (const date of state.dates) {
    const button = document.createElement("button");
    button.className = `date-button${date === state.selectedDate ? " active" : ""}`;
    button.textContent = shortDate(date);
    button.addEventListener("click", async () => {
      state.selectedDate = date;
      state.search = "";
      el.searchInput.value = "";
      renderDates();
      await loadRestaurants();
      await loadRegistrations();
    });
    el.dates.appendChild(button);
  }
}

async function loadRestaurants() {
  if (!state.selectedDate) return;
  const data = await api(`/api/restaurants?date=${encodeURIComponent(state.selectedDate)}`);
  const restaurants = data.restaurants || [];

  if (state.me.role === "admin") {
    if (restaurants.length === 1) state.selectedGroupId = restaurants[0].id;
    el.assignedRestaurantName.textContent = restaurants.map(r => r.name).join(", ") || "Ресторан не призначено";
    return;
  }

  el.restaurantList.innerHTML = "";
  const total = restaurants.reduce((sum, r) => sum + r.count, 0);
  addRestaurantButton(null, "Всі ресторани", total);
  for (const r of restaurants) addRestaurantButton(r.id, r.name, r.count);
}

function addRestaurantButton(id, name, count) {
  const button = document.createElement("button");
  button.className = `restaurant-button${state.selectedGroupId === id ? " active" : ""}`;
  const label = document.createElement("span");
  label.textContent = name;
  const badge = document.createElement("span");
  badge.className = "restaurant-button-count";
  badge.textContent = count;
  button.append(label, badge);
  button.addEventListener("click", async () => {
    state.selectedGroupId = id;
    await loadRestaurants();
    await loadRegistrations();
  });
  el.restaurantList.appendChild(button);
}

async function loadRegistrations() {
  el.error.style.display = "none";
  if (!state.selectedDate) {
    el.tableBody.innerHTML = "";
    el.selectedDate.textContent = "—";
    el.recordsCount.textContent = "0 записів";
    el.empty.style.display = "block";
    return;
  }

  const params = new URLSearchParams({date: state.selectedDate});
  if (state.selectedGroupId !== null) params.set("group_id", state.selectedGroupId);
  if (state.search) params.set("q", state.search);
  const data = await api(`/api/registrations?${params.toString()}`);
  const rows = data.registrations || [];

  el.selectedDate.textContent = formatDate(state.selectedDate);
  el.recordsCount.textContent = `${rows.length} записів`;
  el.tableBody.innerHTML = "";
  el.empty.style.display = rows.length ? "none" : "block";

  for (const item of rows) {
    const tr = document.createElement("tr");
    tr.append(
      cellText(item.restaurant, "restaurant-name"),
      cellText(item.guest_name, "guest-name"),
      cellText(item.child_name, "child-name"),
      cellChildren(item.children),
      cellPhone(item.phone),
      cellStatus(item)
    );
    el.tableBody.appendChild(tr);
  }
}

function cellText(text, className) {
  const td = document.createElement("td");
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text || "—";
  td.appendChild(span);
  return td;
}

function cellChildren(count) {
  const td = document.createElement("td");
  const span = document.createElement("span");
  span.className = "children-count";
  span.textContent = count;
  td.appendChild(span);
  return td;
}



function normalizePhoneForCall(phone) {
  return String(phone || "").replace(/[^\d+]/g, "");
}

function ensurePhoneModal() {
  let modal = document.getElementById("phoneActionModal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "phoneActionModal";
  modal.className = "phone-modal";
  modal.innerHTML = `
    <div class="phone-modal-backdrop" data-phone-close="1"></div>
    <div class="phone-modal-card" role="dialog" aria-modal="true" aria-labelledby="phoneModalTitle">
      <button class="phone-modal-close" type="button" aria-label="Закрити" data-phone-close="1">×</button>
      <div class="phone-modal-label">Телефон</div>
      <div class="phone-modal-number" id="phoneModalTitle">—</div>
      <div class="phone-modal-actions">
        <button type="button" class="phone-modal-btn phone-modal-copy" id="phoneCopyBtn">
          Скопіювати номер
        </button>
        <a class="phone-modal-btn phone-modal-call" id="phoneCallLink" href="#">
          Зателефонувати
        </a>
      </div>
      <div class="phone-modal-hint">
        Якщо Telegram не відкриє набір номера, скористайтеся кнопкою копіювання.
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  modal.addEventListener("click", (event) => {
    if (event.target.closest("[data-phone-close='1']")) {
      closePhoneModal();
    }
  });

  return modal;
}

function closePhoneModal() {
  const modal = document.getElementById("phoneActionModal");
  if (modal) modal.classList.remove("open");
}

async function copyPhoneNumber(phone, button) {
  const cleanPhone = normalizePhoneForCall(phone);
  if (!cleanPhone) return;

  try {
    await navigator.clipboard.writeText(cleanPhone);
    const oldText = button.textContent;
    button.textContent = "Скопійовано ✓";
    setTimeout(() => {
      button.textContent = oldText;
    }, 1400);
    return;
  } catch (_) {}

  const textarea = document.createElement("textarea");
  textarea.value = cleanPhone;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    document.execCommand("copy");
    const oldText = button.textContent;
    button.textContent = "Скопійовано ✓";
    setTimeout(() => {
      button.textContent = oldText;
    }, 1400);
  } finally {
    textarea.remove();
  }
}

function openPhoneModal(phone) {
  const cleanPhone = normalizePhoneForCall(phone);
  if (!cleanPhone) return;

  const modal = ensurePhoneModal();
  const number = modal.querySelector(".phone-modal-number");
  const callLink = modal.querySelector("#phoneCallLink");
  const copyBtn = modal.querySelector("#phoneCopyBtn");

  number.textContent = phone || cleanPhone;
  callLink.href = `tel:${cleanPhone}`;

  copyBtn.onclick = () => copyPhoneNumber(cleanPhone, copyBtn);

  callLink.onclick = () => {
    setTimeout(() => {
      // Якщо WebView блокує tel:, модальне вікно залишається відкритим,
      // щоб користувач міг одразу скопіювати номер.
    }, 0);
  };

  modal.classList.add("open");
}

function cellPhone(phone) {
  const td = document.createElement("td");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "phone phone-button";
  button.textContent = phone || "—";
  button.disabled = !phone;

  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openPhoneModal(phone);
  });

  td.appendChild(button);
  return td;
}

function cellStatus(item) {
  const td = document.createElement("td");
  const select = document.createElement("select");
  select.className = `status-select ${item.status === "no" ? "status-no" : "status-yes"}`;
  select.innerHTML = '<option value="yes">Буде</option><option value="no">Не буде</option>';
  select.value = item.status;
  select.addEventListener("change", async () => {
    const previous = item.status;
    item.status = select.value;
    select.className = `status-select ${select.value === "no" ? "status-no" : "status-yes"}`;
    try {
      await api(`/api/registrations/${item.id}/status`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: select.value})
      });
    } catch (err) {
      item.status = previous;
      select.value = previous;
      select.className = `status-select ${previous === "no" ? "status-no" : "status-yes"}`;
      showError(err.message);
    }
  });
  td.appendChild(select);
  return td;
}

function showError(message) {
  el.error.textContent = message;
  el.error.style.display = "block";
}


function switchView(view) {
  const settings = view === "settings";
  el.recordsView.hidden = settings;
  el.settingsView.hidden = !settings;
  el.appTabs?.querySelectorAll(".app-tab").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
}

async function loadLimits() {
  if (state.me?.role !== "developer") return;
  el.settingsSaveStatus.textContent = "Завантаження…";
  limitsData = await api("/api/limits");
  renderLimits();
  el.settingsSaveStatus.textContent = "";
}

function renderLimits() {
  if (!limitsData) return;
  const dates = limitsData.dates || [];
  const restaurants = limitsData.restaurants || [];

  el.limitsHead.innerHTML = "";
  const hr = document.createElement("tr");
  for (const title of ["Ресторан", "Запис", ...dates.map(shortDate)]) {
    const th = document.createElement("th");
    th.textContent = title;
    hr.appendChild(th);
  }
  el.limitsHead.appendChild(hr);
  el.limitsBody.innerHTML = "";

  for (const r of restaurants) {
    const tr = document.createElement("tr");
    tr.dataset.groupId = r.id ?? r.group_id;

    const name = document.createElement("td");
    name.className = "limits-restaurant-name";
    name.textContent = r.name || "—";
    tr.appendChild(name);

    const enabledCell = document.createElement("td");
    enabledCell.className = "limits-enabled-cell";
    const enabled = document.createElement("input");
    enabled.type = "checkbox";
    enabled.className = "limit-enabled";
    enabled.checked = r.enabled !== false;
    enabledCell.appendChild(enabled);
    tr.appendChild(enabledCell);

    const limits = r.limits || {};
    for (const date of dates) {
      const info = limits[date] || {};
      const td = document.createElement("td");
      td.className = "limit-date-cell";
      td.dataset.dateLabel = shortDate(date);

      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = "999";
      input.inputMode = "numeric";
      input.className = "limit-input";
      input.dataset.date = date;
      input.placeholder = "∞";
      input.value = info.seat_limit == null ? "" : info.seat_limit;

      const meta = document.createElement("div");
      meta.className = "limit-meta";
      const booked = Number(info.booked_children ?? 0);
      meta.textContent = info.remaining == null
        ? `Записано: ${booked}`
        : `Записано: ${booked} · Вільно: ${info.remaining}`;

      td.append(input, meta);
      tr.appendChild(td);
    }
    el.limitsBody.appendChild(tr);
  }
}

async function saveLimits() {
  if (state.me?.role !== "developer") return;
  const restaurants = [];

  el.limitsBody.querySelectorAll("tr[data-group-id]").forEach(tr => {
    const limits = {};
    tr.querySelectorAll(".limit-input").forEach(input => {
      const raw = input.value.trim();
      limits[input.dataset.date] = raw === "" ? null : Number(raw);
    });
    const groupId = Number(tr.dataset.groupId);
    restaurants.push({
      id: groupId,
      group_id: groupId,
      enabled: tr.querySelector(".limit-enabled")?.checked ?? true,
      limits
    });
  });

  el.saveLimitsButton.disabled = true;
  el.settingsSaveStatus.textContent = "Зберігаємо…";
  try {
    await api("/api/limits", {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({restaurants})
    });
    el.settingsSaveStatus.textContent = "Збережено ✓";
    await loadLimits();
    el.settingsSaveStatus.textContent = "Збережено ✓";
  } catch (err) {
    el.settingsSaveStatus.textContent = err.message;
  } finally {
    el.saveLimitsButton.disabled = false;
  }
}

el.appTabs?.addEventListener("click", async event => {
  const button = event.target.closest(".app-tab");
  if (!button) return;
  if (button.dataset.view === "settings") {
    if (state.me?.role !== "developer") return;
    switchView("settings");
    try { await loadLimits(); } catch (err) { el.settingsSaveStatus.textContent = err.message; }
  } else {
    switchView("records");
  }
});

el.saveLimitsButton?.addEventListener("click", saveLimits);


let searchTimer;
el.searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  state.search = el.searchInput.value.trim();
  searchTimer = setTimeout(() => loadRegistrations().catch(e => showError(e.message)), 250);
});

(async function start() {
  try {
    await loadMe();
    await loadDates();
    await loadRestaurants();
    await loadRegistrations();
  } catch (err) {
    showError(err.message);
    el.empty.style.display = "none";
  }
})();
