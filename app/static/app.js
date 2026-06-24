const state = {
  settings: null,
  items: [],
  trades: [],
  raisedByOptions: [],
  photos: [],
};

const $ = (id) => document.getElementById(id);

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2600);
}

function setOptions(select, values, placeholder) {
  select.innerHTML = "";
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
  list.innerHTML = "";
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    list.appendChild(opt);
  });
}

function activeConfig() {
  const project = $("project").value || state.settings.active_project;
  return state.settings.project_configs[project];
}

function refreshProjectConfig() {
  const cfg = activeConfig();
  $("activeProject").textContent = `Active project · ${$("project").value || state.settings.active_project}`;
  setDatalist("buildingOptions", cfg?.buildings || []);
  setDatalist("levelOptions", cfg?.levels || []);
  setDatalist("unitOptions", cfg?.units || []);
  setDatalist("roomOptions", cfg?.rooms || []);
}

function refreshSubcontractors() {
  const trade = $("trade").value;
  const subs = state.settings.subcontractors.filter((name) => {
    const profile = state.settings.sub_profiles[name];
    return !trade || !profile?.trade || profile.trade === trade;
  });
  setDatalist("subOptions", subs.length ? subs : state.settings.subcontractors);
}

function dueDate(days = 7) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

async function bootstrap() {
  const res = await fetch("/api/bootstrap");
  const data = await res.json();
  state.settings = data.settings;
  state.items = data.items;
  state.trades = data.trades;
  state.raisedByOptions = data.raised_by_options;

  setOptions($("project"), state.settings.projects);
  $("project").value = state.settings.active_project;
  setOptions($("raisedBy"), state.raisedByOptions, "Who raised this?");
  setOptions($("trade"), state.trades, "Select trade");
  $("dueDate").value = dueDate(7);
  refreshProjectConfig();
  refreshSubcontractors();
  renderItems();
}

function renderThumbs() {
  const row = $("thumbRow");
  row.innerHTML = "";
  state.photos.forEach((photo, index) => {
    const div = document.createElement("div");
    div.className = "thumb";
    div.innerHTML = `<img src="${photo}" alt="photo" /><button aria-label="Remove photo">×</button>`;
    div.querySelector("button").onclick = () => {
      state.photos.splice(index, 1);
      renderThumbs();
    };
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

async function handleFiles(files) {
  const next = await Promise.all([...files].map(fileToDataUrl));
  state.photos.push(...next);
  renderThumbs();
}

function draftFromNote() {
  const text = $("voiceNote").value.trim();
  if (!text) return;
  const lower = text.toLowerCase();
  const cfg = activeConfig();
  for (const building of cfg.buildings || []) if (lower.includes(building.toLowerCase())) $("building").value = building;
  for (const unit of cfg.units || []) if (lower.includes(unit.toLowerCase())) $("unit").value = unit;
  for (const room of cfg.rooms || []) if (lower.includes(room.toLowerCase())) $("room").value = room;
  for (const trade of state.trades) if (lower.includes(trade.toLowerCase())) $("trade").value = trade;
  if (!$("description").value.trim()) $("description").value = text;
  refreshSubcontractors();
  toast("Drafted fields from note. Review before saving.");
}

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
    voice_note: voiceText ? {
      transcript: voiceText,
      parsed_fields: {},
      status: "parsed",
    } : null,
    created_by: state.settings.prepared_by,
  };
}

function resetForm(keepLocation = true) {
  $("description").value = "";
  $("voiceNote").value = "";
  $("raisedBy").value = "";
  state.photos = [];
  renderThumbs();
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
  try {
    const res = await fetch(`/api/items?issue_now=${issueNow}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Could not save item");
    }
    const item = await res.json();
    state.items.unshift(item);
    renderItems();
    resetForm(true);
    toast(issueNow ? "Item issued" : "Item saved");
  } catch (e) {
    toast(e.message);
  }
}

async function patchItem(id, patch) {
  const res = await fetch(`/api/items/${id}?by=${encodeURIComponent(state.settings.prepared_by)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error("Update failed");
  const item = await res.json();
  const index = state.items.findIndex((i) => i.id === id);
  if (index >= 0) state.items[index] = item;
  renderItems();
}

async function action(id, endpoint, body = {}) {
  const res = await fetch(`/api/items/${id}/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ by: state.settings.prepared_by, ...body }),
  });
  if (!res.ok) throw new Error("Action failed");
  const item = await res.json();
  const index = state.items.findIndex((i) => i.id === id);
  if (index >= 0) state.items[index] = item;
  renderItems();
}

function renderItems() {
  const list = $("itemsList");
  list.innerHTML = "";
  state.items.slice(0, 12).forEach((item) => {
    const div = document.createElement("div");
    div.className = "item-card";
    div.innerHTML = `
      <div class="item-top">
        <div>
          <div class="code">${item.code}</div>
          <div class="meta">${[item.building, item.level, item.unit, item.room].filter(Boolean).join(" / ")}</div>
        </div>
        <span class="status ${item.status}">${item.status.replaceAll("_", " ")}</span>
      </div>
      <div class="desc">${item.description}</div>
      <div class="meta">${item.trade || "No trade"} · ${item.subcontractor || "Unassigned"} · due ${item.due_date}</div>
      <div class="card-actions">
        <button data-edit>Edit</button>
        <button data-issue>Issue</button>
        <button data-ready>Ready</button>
        <button data-report>Report</button>
      </div>`;
    div.querySelector("[data-edit]").onclick = async () => {
      const description = prompt("Edit description", item.description);
      if (description === null) return;
      await patchItem(item.id, { description });
      toast("Item updated");
    };
    div.querySelector("[data-issue]").onclick = async () => {
      const to = item.subcontractor || prompt("Subcontractor", "");
      if (!to) return;
      const res = await fetch(`/api/items/${item.id}/issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to, by: state.settings.prepared_by }),
      });
      const updated = await res.json();
      state.items[state.items.findIndex((i) => i.id === item.id)] = updated;
      renderItems();
    };
    div.querySelector("[data-ready]").onclick = () => action(item.id, "ready").then(() => toast("Marked ready for review"));
    div.querySelector("[data-report]").onclick = () => window.open("/api/reports/handover", "_blank");
    list.appendChild(div);
  });
}

function bindKeyboardDone() {
  const done = $("keyboardDone");
  document.addEventListener("focusin", (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) done.classList.remove("hidden");
  });
  document.addEventListener("focusout", () => setTimeout(() => done.classList.add("hidden"), 120));
  done.onclick = () => {
    if (document.activeElement) document.activeElement.blur();
    done.classList.add("hidden");
  };
}

function bind() {
  $("type").onchange = () => {
    const client = $("type").value === "client";
    $("raisedByWrap").classList.toggle("hidden", !client);
    $("photoRequirement").textContent = $("type").value === "incomplete" ? "Recommended" : "Required for this item type";
  };
  $("project").onchange = refreshProjectConfig;
  $("trade").onchange = refreshSubcontractors;
  $("cameraInput").onchange = (e) => handleFiles(e.target.files);
  $("libraryInput").onchange = (e) => handleFiles(e.target.files);
  $("draftFromNote").onclick = draftFromNote;
  $("saveBtn").onclick = () => save(false);
  $("issueBtn").onclick = () => save(true);
  $("resetDemo").onclick = async () => {
    await fetch("/api/reset-demo", { method: "POST" });
    await bootstrap();
    toast("Demo reset");
  };
}

bindKeyboardDone();
bind();
bootstrap().catch((e) => toast(e.message));
