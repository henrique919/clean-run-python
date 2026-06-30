const state = {
  settings: null,
  items: [],
  trades: [],
  raisedByOptions: [],
  photos: [],
  editingItem: null,
  actionItem: null,
  actionMode: null,
  itemView: "standard",
  authToken: localStorage.getItem("cleanrun_auth_token") || "",
  authConfig: null,
  user: null,
};

const $ = (id) => document.getElementById(id);
const AUTH_TOKEN_KEY = "cleanrun_auth_token";

const TYPE_LABELS = { defect: "Defect", incomplete: "Incomplete Work", client: "Client Defect" };
const STATUS_LABELS = {
  open: "Open",
  issued: "Issued",
  in_progress: "In Progress",
  ready_for_review: "Ready for Review",
  under_inspection: "Under Inspection",
  rejected: "Rejected",
  closed: "Closed",
  complete: "Complete",
};

const ITEM_VIEW_OPTIONS = [
  ["standard", "Standard list"],
  ["building", "By building"],
  ["level", "By level"],
  ["unit", "By unit / area"],
  ["room", "By room / location"],
  ["trade", "By trade"],
  ["subcontractor", "By subcontractor"],
  ["status", "By status"],
];

const LIFECYCLE_ACTION_SELECTORS = ["data-rectify", "data-reject", "data-close", "data-comment"];

function text(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toast(message) {
  const el = $("toast");
  if (!el) return alert(message);
  el.textContent = message;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2600);
}

function setAuthToken(token) {
  state.authToken = token || "";
  if (state.authToken) localStorage.setItem(AUTH_TOKEN_KEY, state.authToken);
  else localStorage.removeItem(AUTH_TOKEN_KEY);
  document.cookie = state.authToken
    ? `cleanrun_access_token=${encodeURIComponent(state.authToken)}; Path=/; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`
    : `cleanrun_access_token=; Path=/; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}; Max-Age=0`;
  updateAuthUi();
}

function authHeaders(extra = {}) {
  return {
    ...extra,
    ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
  };
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, { ...options, headers: authHeaders(options.headers || {}) });
  if (res.status === 401) {
    setAuthToken("");
    state.user = null;
    updateAuthUi();
    const error = new Error("Login required.");
    error.authRequired = true;
    throw error;
  }
  if (res.status === 403) throw new Error("You do not have permission for that action.");
  return res;
}

window.cleanrunApiFetch = apiFetch;

async function loadAuthConfig() {
  if (state.authConfig) return state.authConfig;
  const res = await fetch("/api/auth/config");
  state.authConfig = res.ok ? await res.json() : { dev_tokens_enabled: false };
  updateAuthUi();
  return state.authConfig;
}

function updateAuthUi() {
  const signedIn = !!state.authToken;
  document.body.classList.toggle("signed-out", !signedIn);
  document.body.classList.toggle("signed-in", signedIn);
  $("authPanel")?.classList.toggle("hidden", signedIn);
  $("logoutBtn")?.classList.toggle("hidden", !signedIn);
  if ($("currentUser")) $("currentUser").textContent = state.user?.email || "";
  $("authDevRow")?.classList.toggle("hidden", !(state.authConfig?.dev_tokens_enabled));
}

async function loginWithPassword() {
  const cfg = await loadAuthConfig();
  const email = $("authEmail")?.value.trim();
  const password = $("authPassword")?.value;
  if (!cfg.supabase_url || !cfg.supabase_publishable_key) return toast("Password login is not configured.");
  if (!email || !password) return toast("Enter email and password.");
  const res = await fetch(`${cfg.supabase_url}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: cfg.supabase_publishable_key },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    setAuthToken("");
    return toast("Invalid login credentials.");
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  await bootstrap().catch((error) => {
    if (error.authRequired) return;
    showAppError(error.message || "The app could not initialise.");
  });
}

async function loginWithToken(token) {
  if (!token) return toast("Enter an access token.");
  setAuthToken(token);
  await bootstrap();
}

function showAccessRequestPanel() {
  $("accessRequestPanel")?.classList.toggle("hidden");
}

async function submitAccessRequest() {
  const payload = {
    full_name: $("requestFullName")?.value.trim(),
    email: $("requestEmail")?.value.trim(),
    company: $("requestCompany")?.value.trim(),
    role_requested: $("requestRole")?.value.trim(),
    project_site: $("requestProject")?.value.trim(),
    message: $("requestMessage")?.value.trim(),
  };
  const missing = ["full_name", "email", "company", "role_requested", "project_site"].find((key) => !payload[key]);
  if (missing) return toast("Complete the request access form.");
  const res = await fetch("/api/access-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return toast("Could not submit access request. Email info@cleanruniq.com.");
  ["requestFullName", "requestEmail", "requestCompany", "requestRole", "requestProject", "requestMessage"].forEach((id) => {
    if ($(id)) $(id).value = "";
  });
  toast("Request submitted. Admin approval is required before login.");
}

function logout() {
  setAuthToken("");
  state.user = null;
  state.items = [];
  renderItems();
  updateAuthUi();
}

function showAppError(message) {
  if (/login|required|credential|token|unauthor/i.test(String(message || ""))) {
    setAuthToken("");
    state.user = null;
    updateAuthUi();
    toast("Sign in to continue.");
    return;
  }
  const el = $("appError");
  if (!el) return toast(message);
  el.innerHTML = `<strong>Could not load CleanRun IQ</strong><span>${text(message)} Check your connection, then try again.</span><button type="button" id="retryBootstrap">Retry</button>`;
  el.classList.remove("hidden");
  $("retryBootstrap").onclick = () => {
    el.classList.add("hidden");
    bootstrap().catch((error) => showAppError(error.message || "The app could not initialise."));
  };
}

function projectName() {
  return $("project")?.value || state.settings?.active_project || "";
}

function selectedProjectConfig(project = projectName()) {
  return state.settings?.project_configs?.[project];
}

function projectDefaultView(project = projectName()) {
  return selectedProjectConfig(project)?.preferred_items_view || "standard";
}

function suggestedProjectCodePrefix(project) {
  const firstWord = String(project || "").match(/[A-Za-z0-9]+/)?.[0] || "";
  return firstWord.slice(0, 3).toUpperCase();
}

function sanitizeProjectCodePrefix(value) {
  return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
}

function cardCodePrefix(item) {
  const cfg = selectedProjectConfig(item.project);
  if (!cfg?.code_prefix_locked || !cfg?.code_prefix_hidden_on_cards || !cfg.code_prefix) return "";
  return cfg.code_prefix;
}

function displayItemCode(item) {
  const prefix = cardCodePrefix(item);
  if (prefix && item.code?.toUpperCase().startsWith(`${prefix}-`)) return item.code.slice(prefix.length + 1);
  return item.code;
}

function todayIso() { return new Date().toISOString().slice(0, 10); }
function isClosed(item) { return item.status === "closed" || item.status === "complete"; }
function isOverdue(item) { return !isClosed(item) && item.due_date && item.due_date < todayIso(); }

function showValidation(message, title = "Check required fields") {
  const el = $("validationAlert");
  if (!el) return toast(message);
  el.textContent = "";
  const strong = document.createElement("strong");
  strong.textContent = title;
  el.appendChild(strong);
  el.appendChild(document.createTextNode(message));
  el.classList.remove("hidden");
  el.scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearValidation() {
  const el = $("validationAlert");
  if (!el) return;
  el.classList.add("hidden");
  el.textContent = "";
}

function showEditAlert(message) {
  const el = $("editAlert");
  if (!el) return toast(message);
  el.textContent = "";
  const strong = document.createElement("strong");
  strong.textContent = "Cannot save edit";
  el.appendChild(strong);
  el.appendChild(document.createTextNode(message));
  el.classList.remove("hidden");
}

function clearEditAlert() {
  const el = $("editAlert");
  if (!el) return;
  el.classList.add("hidden");
  el.textContent = "";
}

function setOptions(select, values, placeholder) {
  if (!select) return;
  select.textContent = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    select.appendChild(opt);
  });
}

function setDatalist(id, values) {
  const list = $(id);
  if (!list) return;
  list.textContent = "";
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    list.appendChild(opt);
  });
}

function projectConfig(projectName) {
  return selectedProjectConfig(projectName);
}

function setItemViewOptions(select) {
  if (!select) return;
  select.textContent = "";
  ITEM_VIEW_OPTIONS.forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  });
}

function refreshProjectCodePrefixSetting() {
  const project = state.settings?.active_project || "";
  const cfg = selectedProjectConfig(project) || {};
  const input = $("projectCodePrefix");
  const button = $("lockProjectCodePrefix");
  const status = $("projectCodePrefixStatus");
  if (!input || !button || !status) return;
  const locked = !!cfg.code_prefix_locked;
  const prefix = cfg.code_prefix || suggestedProjectCodePrefix(project);
  input.value = prefix;
  input.disabled = locked;
  button.disabled = locked;
  button.textContent = locked ? "Locked" : "Lock prefix";
  status.textContent = locked
    ? `Locked as ${prefix}. Item cards show DEF-1001 while reports keep ${prefix}-DEF-1001.`
    : "Choose once for this project. It cannot be changed after locking.";
}

function refreshProjectConfig(projectName) {
  const project = projectName || $("project")?.value || state.settings.active_project;
  const cfg = projectConfig(project);
  if ($("activeProject")) $("activeProject").textContent = project;
  setDatalist("buildingOptions", cfg?.buildings || []);
  setDatalist("levelOptions", cfg?.levels || []);
  setDatalist("unitOptions", cfg?.units || []);
  setDatalist("roomOptions", cfg?.rooms || []);
}

function refreshEditProjectConfig(projectName) {
  const cfg = projectConfig(projectName || $("editProject")?.value);
  setDatalist("editBuildingOptions", cfg?.buildings || []);
  setDatalist("editLevelOptions", cfg?.levels || []);
  setDatalist("editUnitOptions", cfg?.units || []);
  setDatalist("editRoomOptions", cfg?.rooms || []);
}

function subcontractorsForTrade(trade) {
  const subs = state.settings.subcontractors.filter((name) => {
    const profile = state.settings.sub_profiles[name];
    return !trade || !profile?.trade || profile.trade === trade;
  });
  return subs.length ? subs : state.settings.subcontractors;
}

function refreshSubcontractors() { setDatalist("subOptions", subcontractorsForTrade($("trade")?.value)); }
function refreshEditSubcontractors() { setDatalist("editSubOptions", subcontractorsForTrade($("editTrade")?.value)); }
function refreshReportSubcontractors() { setOptions($("reportSubcontractor"), state.settings?.subcontractors || [], "Subcontractor..."); }

function dueDate(days = 7) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

async function bootstrap() {
  await loadAuthConfig();
  if (!state.authToken) {
    updateAuthUi();
    return;
  }
  const res = await apiFetch("/api/bootstrap");
  if (!res.ok) throw new Error("Could not load app data");
  const data = await res.json();
  if (!data.settings || !Array.isArray(data.items)) throw new Error("Bootstrap response was incomplete.");
  $("appError")?.classList.add("hidden");
  state.settings = data.settings;
  state.items = data.items;
  state.trades = data.trades;
  state.raisedByOptions = data.raised_by_options;
  state.user = data.user;
  updateAuthUi();

  setOptions($("project"), state.settings.projects);
  setOptions($("editProject"), state.settings.projects);
  if ($("project")) $("project").value = state.settings.active_project;
  setOptions($("raisedBy"), state.raisedByOptions, "Who raised this?");
  setOptions($("editRaisedBy"), state.raisedByOptions, "Who raised this?");
  setOptions($("trade"), state.trades, "Select trade");
  setOptions($("editTrade"), state.trades, "Select trade");
  setItemViewOptions($("itemsView"));
  setItemViewOptions($("preferredItemsView"));
  state.itemView = projectDefaultView();
  if ($("itemsView")) $("itemsView").value = state.itemView;
  if ($("preferredItemsView")) $("preferredItemsView").value = state.itemView;
  if ($("dueDate")) $("dueDate").value = dueDate(7);
  refreshProjectConfig();
  refreshEditProjectConfig(state.settings.active_project);
  refreshProjectCodePrefixSetting();
  refreshSubcontractors();
  refreshEditSubcontractors();
  refreshReportSubcontractors();
  renderItems();
}

function renderThumbs() {
  const row = $("thumbRow");
  if (!row) return;
  row.textContent = "";
  state.photos.forEach((photo, index) => {
    const div = document.createElement("div");
    div.className = "thumb";
    const img = document.createElement("img");
    img.src = photo;
    img.alt = `Captured evidence ${index + 1}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", "Remove photo");
    btn.textContent = "×";
    btn.onclick = () => { state.photos.splice(index, 1); renderThumbs(); };
    div.appendChild(img);
    div.appendChild(btn);
    row.appendChild(div);
  });
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleFiles(files, input) {
  if (!files || files.length === 0) return [];
  const next = await Promise.all([...files].map(fileToDataUrl));
  if (input) input.value = "";
  return next;
}

async function handleCaptureFiles(files, input) {
  const next = await handleFiles(files, input);
  state.photos.push(...next);
  renderThumbs();
  clearValidation();
}

function applyParsedFields(parsed) {
  const warnings = [];
  function applyField(fieldId, value, label) {
    if (!value) return;
    const el = $(fieldId);
    if (!el) return;
    if (!el.value.trim()) { el.value = value; }
    else { warnings.push(`${label} already filled — voice result (${value}) not applied.`); }
  }
  applyField("building", parsed.building, "Building");
  applyField("level", parsed.level, "Level");
  applyField("unit", parsed.unit, "Unit");
  applyField("room", parsed.room, "Room");
  if (parsed.trade) {
    const tradeEl = $("trade");
    if (tradeEl && !tradeEl.value) {
      const opt = [...tradeEl.options].find(o => o.value === parsed.trade);
      if (opt) tradeEl.value = parsed.trade;
    } else if (tradeEl && tradeEl.value) {
      warnings.push(`Trade already selected — voice result (${parsed.trade}) not applied.`);
    }
  }
  if (parsed.description) {
    const descEl = $("description");
    const currentDesc = descEl ? descEl.value.trim() : '';
    const rawTranscript = (parsed.raw_transcript || '').trim();
    if (descEl && (!currentDesc || currentDesc.toLowerCase() === rawTranscript.toLowerCase())) {
      descEl.value = parsed.description;
    }
  }
  refreshSubcontractors();
  clearValidation();
  toast(warnings.length ? warnings.join(" ") : "Fields drafted from note. Review before saving.");
}

function draftFromNote() {
  const value = $("voiceNote").value.trim();
  if (!value) { toast("Type or speak a note first."); return; }
  if (!window.VoiceParser) { toast("Parser not loaded — refresh the page."); return; }
  const cfg = projectConfig() || {};
  const parsed = window.VoiceParser.parseVoiceNote(value, {
    buildings: cfg.buildings || [],
    levels: cfg.levels || [],
    units: cfg.units || [],
    rooms: cfg.rooms || [],
    projectNames: state.settings ? state.settings.projects : [],
  });
  applyParsedFields(parsed);
}

window.draftFromVoice = function (transcript) { draftFromNote(); };

function payload() {
  const voiceText = $("voiceNote").value.trim();
  return {
    type: $("type").value,
    project: $("project").value,
    building: $("building").value.trim(),
    level: $("level").value.trim(),
    unit: $("unit").value.trim(),
    room: $("room").value.trim(),
    trade: $("trade").value,
    subcontractor: $("subcontractor").value.trim(),
    priority: $("priority").value,
    due_date: $("dueDate").value,
    description: $("description").value.trim(),
    raised_by: $("type").value === "client" ? $("raisedBy").value : null,
    original_photos: state.photos,
    voice_transcript: voiceText || null,
    voice_note: voiceText ? { transcript: voiceText, parsed_fields: {}, status: "parsed" } : null,
    created_by: state.settings.prepared_by,
  };
}

function clientValidate(issueNow) {
  const data = payload();
  if (!data.building) return "Select a building.";
  if (!data.unit) return "Select a unit / area.";
  if ((data.type === "defect" || data.type === "client") && data.original_photos.length === 0) return data.type === "client" ? "A Client Defect requires at least one original photo." : "A Defect requires at least one original photo.";
  if (data.type === "client" && !data.raised_by) return "Client Defects require a Raised By / source.";
  if (!data.description) return "Add a short description.";
  if (issueNow && !data.trade) return "Issue Now requires a trade.";
  if (issueNow && !data.subcontractor) return "Issue Now requires a subcontractor.";
  return null;
}

function resetForm(keepLocation = true) {
  $("description").value = "";
  $("voiceNote").value = "";
  if ($("raisedBy")) $("raisedBy").value = "";
  state.photos = [];
  renderThumbs();
  clearValidation();
  if (!keepLocation) {
    $("building").value = "";
    $("level").value = "";
    $("unit").value = "";
    $("room").value = "";
    $("trade").value = "";
    $("subcontractor").value = "";
  }
}

async function save(issueNow = false) {
  clearValidation();
  const warning = clientValidate(issueNow);
  if (warning) return showValidation(warning);
  if ($("type").value === "incomplete" && state.photos.length === 0 && !confirm("Incomplete Work can be saved without a photo, but evidence is recommended. Save anyway?")) return;
  try {
    const res = await apiFetch(`/api/items?issue_now=${issueNow}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not save item");
    }
    const item = await res.json();
    state.items.unshift(item);
    renderItems();
    resetForm(true);
    toast(saveConfirmation(item));
  } catch (error) { showValidation(error.message || "Could not save item."); }
}

async function patchItem(id, patch) {
  const res = await apiFetch(`/api/items/${id}?by=${encodeURIComponent(state.settings.prepared_by)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Update failed");
  }
  const item = await res.json();
  replaceItem(item);
  return item;
}

function replaceItem(item) {
  const index = state.items.findIndex((candidate) => candidate.id === item.id);
  if (index >= 0) state.items[index] = item;
  renderItems();
}

async function action(id, endpoint, body = {}) {
  const res = await apiFetch(`/api/items/${id}/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ by: state.settings.prepared_by, ...body }) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Action failed");
  }
  const item = await res.json();
  replaceItem(item);
  return item;
}

function evidenceCounts(item) { return { original: item.original_photos?.length || 0, rectification: item.rectification_evidence?.length || 0, closeout: item.closeout_evidence?.length || 0 }; }
function locationText(item) { return [item.building, item.level, item.unit, item.room].filter(Boolean).join(" / ") || "Unassigned location"; }
function saveConfirmation(item) { return `${displayItemCode(item)} ${item.status === "issued" ? "issued" : "saved"} to ${locationText(item)}. Capture another here?`; }

function visibleItems() {
  const status = $("statusFilter")?.value || "all";
  const query = ($("searchInput")?.value || "").trim().toLowerCase();
  return state.items.filter((item) => {
    if (status !== "all" && item.status !== status) return false;
    if (!query) return true;
    const haystack = [item.code, displayItemCode(item), TYPE_LABELS[item.type], STATUS_LABELS[item.status], item.description, item.trade, item.subcontractor, locationText(item)].join(" ").toLowerCase();
    return haystack.includes(query);
  });
}

function renderStats(items = state.items) {
  const el = $("statsBar");
  if (!el) return;
  const outstanding = items.filter((i) => !isClosed(i)).length;
  const overdue = items.filter(isOverdue).length;
  const closed = items.filter(isClosed).length;
  const issued = items.filter((i) => ["issued", "in_progress", "ready_for_review", "under_inspection"].includes(i.status)).length;
  el.innerHTML = `<div class="stat-card"><span class="stat-value">${items.length}</span><span class="stat-label">Total</span></div><div class="stat-card"><span class="stat-value">${outstanding}</span><span class="stat-label">${overdue ? `${overdue} overdue` : "Open"}</span></div><div class="stat-card"><span class="stat-value">${issued}</span><span class="stat-label">With trade</span></div><div class="stat-card"><span class="stat-value">${closed}</span><span class="stat-label">Closed</span></div>`;
}

async function savePreferredItemsView(value) {
  const project = state.settings.active_project;
  const project_configs = JSON.parse(JSON.stringify(state.settings.project_configs));
  project_configs[project] = { ...project_configs[project], preferred_items_view: value };
  const res = await apiFetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_configs }) });
  if (!res.ok) throw new Error("Could not save project setting");
  state.settings = await res.json();
}

async function lockProjectCodePrefix() {
  const project = state.settings.active_project;
  const prefix = sanitizeProjectCodePrefix($("projectCodePrefix")?.value || suggestedProjectCodePrefix(project));
  if (!prefix) return toast("Add a project prefix before locking.");
  const project_configs = JSON.parse(JSON.stringify(state.settings.project_configs));
  project_configs[project] = {
    ...project_configs[project],
    code_prefix: prefix,
    code_prefix_locked: true,
    code_prefix_hidden_on_cards: true,
  };
  const res = await apiFetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_configs }) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not lock project prefix");
  }
  state.settings = await res.json();
  refreshProjectCodePrefixSetting();
  renderItems();
}

function groupLabel(item, view) {
  const labels = {
    standard: "Standard list",
    building: item.building || "Unassigned building",
    level: item.level || "Unassigned level",
    unit: item.unit || "Unassigned unit / area",
    room: item.room || "Unassigned room / location",
    trade: item.trade || "No trade",
    subcontractor: item.subcontractor || "Unassigned subcontractor",
    status: STATUS_LABELS[item.status] || item.status,
  };
  return labels[view] || labels.standard;
}

function groupedItems(items) {
  if (state.itemView === "standard") return [["", items]];
  const groups = new Map();
  items.forEach((item) => {
    const label = groupLabel(item, state.itemView);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(item);
  });
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function nextActionFor(item) {
  if (item.status === "open") return { label: item.trade && item.subcontractor ? "Issue" : "Edit to issue", run: () => item.trade && item.subcontractor ? issueItem(item) : openEdit(item) };
  if (item.status === "issued") return { label: "Start work", run: () => quickAction(item, "in-progress", "Marked in progress") };
  if (item.status === "in_progress" || item.status === "rejected") return { label: "Add rectification", run: () => openActionDrawer(item, "rectification") };
  if (item.status === "ready_for_review") return { label: "Start inspection", run: () => quickAction(item, "inspection/start", "Inspection started") };
  if (item.status === "under_inspection") return { label: "Close", run: () => openActionDrawer(item, "close") };
  return { label: "Report", run: () => openReport("handover") };
}

async function quickAction(item, endpoint, success) { try { await action(item.id, endpoint); toast(success); } catch (error) { toast(error.message || "Action failed"); } }

async function openReport(reportType) {
  try {
    const params = new URLSearchParams({ project: projectName() });
    if (reportType === "subcontractor") {
      const subcontractor = $("reportSubcontractor")?.value || "";
      if (!subcontractor) return toast("Choose a subcontractor for the summary report.");
      params.set("subcontractor", subcontractor);
    }
    const res = await apiFetch(`/api/reports/${reportType}?${params.toString()}`);
    if (!res.ok) throw new Error("Report failed");
    const html = await res.text();
    const reportWindow = window.open("", "_blank");
    if (!reportWindow) return toast("Allow popups to view reports.");
    reportWindow.document.open();
    reportWindow.document.write(html);
    reportWindow.document.close();
  } catch (error) {
    toast(error.message || "Could not open report");
  }
}
async function issueItem(item) {
  try {
    const res = await apiFetch(`/api/items/${item.id}/issue`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: item.subcontractor, by: state.settings.prepared_by }) });
    if (!res.ok) throw new Error("Issue failed");
    replaceItem(await res.json());
    toast("Item issued");
  } catch (error) { toast(error.message || "Issue failed"); }
}

function cardPhoto(item) {
  const src = item.original_photos?.[0];
  if (!src) return `<div class="item-photo empty">No photo</div>`;
  if (src.startsWith("seed://")) {
    const label = src.replace("seed://", "").replaceAll("/", " / ");
    return `<div class="item-photo seed">${text(label)}</div>`;
  }
  return `<img class="item-photo" src="${text(src)}" alt="Original evidence for ${text(item.code)}">`;
}

function itemCardMarkup(item) {
  const counts = evidenceCounts(item);
  const next = nextActionFor(item);
  const cardCode = displayItemCode(item);
  return `<div class="item-band"><div><div class="code" title="${text(item.code)}" data-full-code="${text(item.code)}">${text(cardCode)}</div><div class="item-type">${text(TYPE_LABELS[item.type] || item.type)}</div></div><span class="status ${text(item.status)}">${text(STATUS_LABELS[item.status] || item.status)}</span></div><div class="item-card-body"><aside class="item-evidence">${cardPhoto(item)}<div class="due-under-photo">Due ${text(item.due_date || "Not set")}</div></aside><div class="item-copy"><div class="location-line">${text(locationText(item))}</div><div class="desc">${text(item.description)}</div><div class="assignment-block"><div class="subcontractor-name">${text(item.subcontractor || "Unassigned subcontractor")}</div><div class="trade-name">${text(item.trade || "No trade")}</div></div><div class="evidence-counts"><span class="ev-chip original">Original ${counts.original}</span><span class="ev-chip rectification">Rectification ${counts.rectification}</span><span class="ev-chip closeout">Closeout ${counts.closeout}</span></div></div></div><div class="card-actions"><button type="button" class="quiet-action" data-edit>Edit</button><button type="button" class="next-action" data-next>${text(next.label)}</button><button type="button" class="more-action" data-more>More</button></div>`;
}

async function uploadSettingsSheet(target, input) {
  const file = input?.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append("target", target);
  form.append("project", projectName());
  form.append("file", file);
  try {
    const res = await apiFetch("/api/settings/import", { method: "POST", body: form });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || "Import failed");
    state.settings = payload.settings;
    refreshProjectConfig();
    refreshEditProjectConfig(state.settings.active_project);
    refreshSubcontractors();
    refreshEditSubcontractors();
    refreshReportSubcontractors();
    toast(`${payload.imported || 0} records imported`);
  } catch (error) {
    toast(error.message || "Import failed");
  } finally {
    input.value = "";
  }
}

/*
Legacy renderer retained only as non-executable reference while this file is being consolidated.
It should be deleted during the next frontend module split.
function renderItemsLegacyUnused() {
  const list = $("itemsList");
  if (!list) return;
  const items = visibleItems();
  renderStats(state.items);
  if ($("listCount")) $("listCount").textContent = `${items.length} shown`;
  list.textContent = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "item-card";
    empty.innerHTML = `<div class="code">No matching items</div><div class="meta">Capture an item or clear your filters.</div>`;
    list.appendChild(empty);
    return;
  }
  items.slice(0, 30).forEach((item) => {
    const counts = evidenceCounts(item);
    const next = nextActionFor(item);
    const div = document.createElement("div");
    div.className = `item-card status-${item.status}`;
    div.innerHTML = `<div class="item-top"><div><div class="code">${text(item.code)}</div><div class="item-type">${text(TYPE_LABELS[item.type] || item.type)}</div></div><span class="status ${text(item.status)}">${text(STATUS_LABELS[item.status] || item.status)}</span></div><div class="desc">${text(item.description)}</div><div class="item-meta-grid"><div><strong>Location</strong> · ${text(locationText(item))}</div><div><strong>Trade</strong> · ${text(item.trade || "No trade")}</div><div><strong>Subcontractor</strong> · ${text(item.subcontractor || "Unassigned")}</div><div><strong>Due</strong> · ${text(item.due_date || "Not set")}</div></div><div class="evidence-counts"><span class="ev-chip original">Original ${counts.original}</span><span class="ev-chip rectification">Rectification ${counts.rectification}</span><span class="ev-chip closeout">Closeout ${counts.closeout}</span></div><div class="card-actions"><button type="button" class="quiet-action" data-edit>Edit</button><button type="button" class="next-action" data-next>${text(next.label)}</button><button type="button" class="more-action" data-more>More</button></div>`;
    div.querySelector("[data-edit]").onclick = () => openEdit(item);
    div.querySelector("[data-next]").onclick = next.run;
    div.querySelector("[data-more]").onclick = () => openActionDrawer(item, "menu");
    list.appendChild(div);
  });
}

*/
function renderItems() {
  const list = $("itemsList");
  if (!list) return;
  const items = visibleItems();
  renderStats(state.items);
  if ($("listCount")) $("listCount").textContent = `${items.length} shown`;
  list.textContent = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "item-card";
    empty.innerHTML = `<div class="code">No matching items</div><div class="meta">Capture an item or clear your filters.</div>`;
    list.appendChild(empty);
    return;
  }
  groupedItems(items).forEach(([label, group]) => {
    if (label) {
      const heading = document.createElement("div");
      heading.className = "item-group-heading";
      heading.textContent = `${label} (${group.length})`;
      list.appendChild(heading);
    }
    group.forEach((item) => {
      const next = nextActionFor(item);
      const div = document.createElement("div");
      div.className = `item-card status-${item.status}`;
      div.innerHTML = itemCardMarkup(item);
      div.querySelector("[data-edit]").onclick = () => openEdit(item);
      div.querySelector("[data-next]").onclick = next.run;
      div.querySelector("[data-more]").onclick = () => openActionDrawer(item, "menu");
      list.appendChild(div);
    });
  });
}

function openEdit(item) {
  state.editingItem = item;
  clearEditAlert();
  $("editType").value = item.type;
  $("editProject").value = item.project;
  $("editBuilding").value = item.building || "";
  $("editLevel").value = item.level || "";
  $("editUnit").value = item.unit || "";
  $("editRoom").value = item.room || "";
  $("editTrade").value = item.trade || "";
  $("editSubcontractor").value = item.subcontractor || "";
  $("editPriority").value = item.priority || "high";
  $("editDueDate").value = item.due_date || dueDate(7);
  $("editDescription").value = item.description || "";
  $("editRaisedBy").value = item.raised_by || "";
  $("editRaisedByWrap").classList.toggle("hidden", item.type !== "client");
  refreshEditProjectConfig(item.project);
  refreshEditSubcontractors();
  $("editOverlay").classList.remove("hidden");
  $("editOverlay").setAttribute("aria-hidden", "false");
}

function closeEdit() { state.editingItem = null; $("editOverlay")?.classList.add("hidden"); $("editOverlay")?.setAttribute("aria-hidden", "true"); }
function editPayload() { const type = $("editType").value; return { type, project: $("editProject").value, building: $("editBuilding").value.trim(), level: $("editLevel").value.trim(), unit: $("editUnit").value.trim(), room: $("editRoom").value.trim(), trade: $("editTrade").value, subcontractor: $("editSubcontractor").value.trim(), priority: $("editPriority").value, due_date: $("editDueDate").value, description: $("editDescription").value.trim(), raised_by: type === "client" ? $("editRaisedBy").value : null }; }
async function saveEdit() {
  if (!state.editingItem) return;
  clearEditAlert();
  const patch = editPayload();
  if (!patch.building) return showEditAlert("Building cannot be blank.");
  if (!patch.unit) return showEditAlert("Unit / Area cannot be blank.");
  if (!patch.description) return showEditAlert("Description cannot be blank.");
  if (patch.type === "client" && !patch.raised_by) return showEditAlert("Client Defects require a Raised By / source.");
  try { await patchItem(state.editingItem.id, patch); closeEdit(); toast("Item details updated"); } catch (error) { showEditAlert(error.message || "Could not update item."); }
}

function openActionDrawer(item, mode = "menu") {
  state.actionItem = item;
  state.actionMode = mode;
  $("actionTitle").textContent = item.code;
  $("actionMeta").textContent = `${TYPE_LABELS[item.type] || item.type} · ${locationText(item)} · ${STATUS_LABELS[item.status] || item.status}`;
  $("actionOverlay").classList.remove("hidden");
  $("actionOverlay").setAttribute("aria-hidden", "false");
  renderActionContent();
}
function closeActionDrawer() { state.actionItem = null; state.actionMode = null; $("actionOverlay")?.classList.add("hidden"); $("actionOverlay")?.setAttribute("aria-hidden", "true"); }
function menuButton(label, description, handler, primary = false) { const btn = document.createElement("button"); btn.type = "button"; btn.className = primary ? "primary-choice" : ""; btn.innerHTML = `<span>${text(label)}</span><small>${text(description)}</small>`; btn.onclick = handler; return btn; }

function renderActionContent() {
  const item = state.actionItem;
  const mode = state.actionMode;
  const menu = $("actionMenu");
  const form = $("actionForm");
  const submit = $("actionSubmit");
  menu.textContent = "";
  form.textContent = "";
  menu.classList.toggle("hidden", mode !== "menu");
  form.classList.toggle("hidden", mode === "menu");
  submit.classList.toggle("hidden", mode === "menu");
  if (mode === "menu") {
    const next = nextActionFor(item);
    menu.appendChild(menuButton(next.label, "Recommended next step", next.run, true));
    menu.appendChild(menuButton("Add Rectification", "Upload or record trade rectification evidence", () => openActionDrawer(item, "rectification")));
    menu.appendChild(menuButton("Reject", "Send back after failed inspection", () => openActionDrawer(item, "reject")));
    menu.appendChild(menuButton("Comment", "Add an audit note", () => openActionDrawer(item, "comment")));
    menu.appendChild(menuButton("Close", "Close with supervisor proof", () => openActionDrawer(item, "close")));
    menu.appendChild(menuButton("Report", "Open handover report", () => openReport("handover")));
    return;
  }
  const titleMap = { rectification: "Add Rectification", reject: "Reject Item", comment: "Add Comment", close: "Close Item" };
  $("actionKicker").textContent = titleMap[mode] || "Item action";
  submit.textContent = mode === "reject" ? "Reject" : mode === "close" ? "Close item" : "Save";
  if (mode === "rectification") {
    submit.textContent = "Submit rectification";
    form.innerHTML = `<p class="hint">Upload the rectification photo and describe what was fixed. Tick ready for review when the site team can inspect it.</p><label for="actionPhoto">Rectification photo</label><input id="actionPhoto" type="file" accept="image/*" capture="environment" /><label for="actionComment">Rectification comment</label><textarea id="actionComment" placeholder="What was fixed?"></textarea><label class="check-row"><input id="actionAdvance" type="checkbox" /> Send back ready for review</label>`;
  }
  else if (mode === "reject") form.innerHTML = `<p class="hint">Capture the reason this item failed inspection.</p><label for="actionReason">Rejection reason</label><textarea id="actionReason" placeholder="Explain what still needs to be fixed"></textarea>`;
  else if (mode === "comment") form.innerHTML = `<p class="hint">Add a note to the item audit trail.</p><label for="actionComment">Comment</label><textarea id="actionComment" placeholder="Add comment"></textarea>`;
  else if (mode === "close") form.innerHTML = `<p class="hint">Close the item with supervisor confirmation. Add a photo where practical.</p><label for="actionPhoto">Closeout photo</label><input id="actionPhoto" type="file" accept="image/*" capture="environment" /><label for="actionNote">Closeout note</label><textarea id="actionNote">Reviewed and accepted for closeout.</textarea><label for="actionConfirmation">Confirmation</label><input id="actionConfirmation" value="Confirmed acceptable for closeout" />`;
}

async function submitAction() {
  const item = state.actionItem;
  const mode = state.actionMode;
  if (!item || !mode) return;
  try {
    let updated;
    if (mode === "rectification") {
      const photos = await handleFiles($("actionPhoto")?.files || []);
      const comment = $("actionComment").value.trim();
      const res = await apiFetch(`/api/items/${item.id}/rectification`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ photo: photos[0] || null, comment, by: state.settings.prepared_by, advance_to_ready: $("actionAdvance")?.checked || false }) });
      if (!res.ok) throw new Error("Rectification failed");
      updated = await res.json();
      toast($("actionAdvance")?.checked ? "Rectification submitted for review" : "Rectification saved");
    } else if (mode === "reject") {
      const reason = $("actionReason").value.trim();
      if (!reason) return toast("Add a rejection reason");
      updated = await action(item.id, "inspection/reject", { reason });
      toast("Item rejected");
    } else if (mode === "comment") {
      const value = $("actionComment").value.trim();
      if (!value) return toast("Add a comment");
      const res = await apiFetch(`/api/items/${item.id}/comments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: value, by: state.settings.prepared_by }) });
      if (!res.ok) throw new Error("Comment failed");
      updated = await res.json();
      toast("Comment added");
    } else if (mode === "close") {
      const photos = await handleFiles($("actionPhoto")?.files || []);
      const note = $("actionNote").value.trim();
      const confirmation = $("actionConfirmation").value.trim();
      const res = await apiFetch(`/api/items/${item.id}/closeout`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ photo: photos[0] || null, by: state.settings.prepared_by, role: "Supervisor", note, confirmation }) });
      if (!res.ok) throw new Error("Closeout failed");
      updated = await res.json();
      toast("Item closed");
    }
    if (updated) replaceItem(updated);
    closeActionDrawer();
  } catch (error) { toast(error.message || "Action failed"); }
}

function bindKeyboardDone() { const done = $("keyboardDone"); if (!done) return; document.addEventListener("focusin", (event) => { if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) done.classList.remove("hidden"); }); document.addEventListener("focusout", () => setTimeout(() => done.classList.add("hidden"), 120)); done.onclick = () => { if (document.activeElement) document.activeElement.blur(); done.classList.add("hidden"); }; }
function bind() {
  $("loginBtn")?.addEventListener("click", loginWithPassword);
  $("tokenLoginBtn")?.addEventListener("click", () => loginWithToken($("authToken")?.value.trim()));
  $("showAccessRequest")?.addEventListener("click", showAccessRequestPanel);
  $("submitAccessRequest")?.addEventListener("click", submitAccessRequest);
  $("logoutBtn")?.addEventListener("click", logout);
  document.querySelectorAll("[data-dev-token]").forEach((button) => {
    button.addEventListener("click", () => loginWithToken(button.dataset.devToken));
  });
  document.querySelectorAll("[data-report]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openReport(link.dataset.report);
    });
  });
  $("type").onchange = () => { const itemType = $("type").value; $("raisedByWrap").classList.toggle("hidden", itemType !== "client"); $("photoRequirement").textContent = itemType === "incomplete" ? "Incomplete Work: photo recommended" : itemType === "client" ? "Client Defect: photo required" : "Defect: photo required"; clearValidation(); };
  $("project").onchange = () => { refreshProjectConfig(); $("building").value = ""; $("level").value = ""; $("unit").value = ""; $("room").value = ""; };
  $("trade").onchange = () => { refreshSubcontractors(); $("subcontractor").value = ""; };
  $("cameraInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
  $("libraryInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
  $("draftFromNote").onclick = draftFromNote;
  $("saveBtn").onclick = () => save(false);
  $("issueBtn").onclick = () => save(true);
  $("resetDemo").onclick = async () => {
    try {
      const res = await apiFetch("/api/reset-demo", { method: "POST" });
      if (!res.ok) throw new Error("Demo reset failed");
      await bootstrap();
      toast("Demo reset");
    } catch (error) { showAppError(error.message || "Demo reset failed."); }
  };
  $("searchInput")?.addEventListener("input", renderItems);
  $("statusFilter")?.addEventListener("change", renderItems);
  $("clearFilters")?.addEventListener("click", () => {
    if ($("searchInput")) $("searchInput").value = "";
    if ($("statusFilter")) $("statusFilter").value = "all";
    renderItems();
  });
  $("itemsView")?.addEventListener("change", () => { state.itemView = $("itemsView").value; renderItems(); });
  $("preferredItemsView")?.addEventListener("change", async () => {
    state.itemView = $("preferredItemsView").value;
    if ($("itemsView")) $("itemsView").value = state.itemView;
    renderItems();
    try { await savePreferredItemsView(state.itemView); toast("Project Items view saved"); } catch (error) { toast(error.message || "Could not save setting"); }
  });
  $("projectCodePrefix")?.addEventListener("input", () => {
    $("projectCodePrefix").value = sanitizeProjectCodePrefix($("projectCodePrefix").value);
  });
  $("lockProjectCodePrefix")?.addEventListener("click", async () => {
    try { await lockProjectCodePrefix(); toast("Project prefix locked"); } catch (error) { toast(error.message || "Could not lock project prefix"); }
  });
  $("unitsImport")?.addEventListener("change", (event) => uploadSettingsSheet("units", event.target));
  $("subcontractorsImport")?.addEventListener("change", (event) => uploadSettingsSheet("subcontractors", event.target));
  $("editClose").onclick = closeEdit;
  $("editCancel").onclick = closeEdit;
  $("editSave").onclick = saveEdit;
  $("editOverlay").onclick = (event) => { if (event.target.id === "editOverlay") closeEdit(); };
  $("editType").onchange = () => $("editRaisedByWrap").classList.toggle("hidden", $("editType").value !== "client");
  $("editProject").onchange = () => { refreshEditProjectConfig($("editProject").value); $("editBuilding").value = ""; $("editLevel").value = ""; $("editUnit").value = ""; $("editRoom").value = ""; };
  $("editTrade").onchange = () => { refreshEditSubcontractors(); $("editSubcontractor").value = ""; };
  $("actionClose").onclick = closeActionDrawer;
  $("actionCancel").onclick = closeActionDrawer;
  $("actionSubmit").onclick = submitAction;
  $("actionOverlay").onclick = (event) => { if (event.target.id === "actionOverlay") closeActionDrawer(); };
}

bindKeyboardDone();
bind();
bootstrap().catch((error) => showAppError(error.message || "The app could not initialise."));
