const API_BASE = (window.MK_API_BASE || "").replace(/\/$/, "");

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
  error: document.getElementById("errorMessage")
};

function authHeaders(extra = {}) {
  return {
    "X-Telegram-Init-Data": tg?.initData || "",
    ...extra
  };
}

async function api(path, options = {}) {
  if (!API_BASE) {
    throw new Error("API ще не підключено. Вкажіть MK_API_BASE у config.js");
  }
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

function cellPhone(phone) {
  const td = document.createElement("td");
  const a = document.createElement("a");
  a.className = "phone";
  a.href = `tel:${phone || ""}`;
  a.textContent = phone || "—";
  td.appendChild(a);
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
