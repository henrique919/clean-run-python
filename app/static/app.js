const state = {
  settings: null,
  items: [],
  trades: [],
  raisedByOptions: [],
  photos: [],
  editingItem: null,
};

const $ = (id) => document.getElementById(id);

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
  const project = projectName || $("project")?.value || state.settings.active_project;
  return state.settings.project_configs[project];
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

function refreshSubcontractors() {
  setDatalist("subOptions", subcontractorsForTrade($("trade")?.value));
}

function refreshEditSubcontractors() {
  setDatalist("editSubOptions", subcontractorsForTrade($("editTrade")?.value));
}

function dueDate(days = 7) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

async function bootstrap() {
  const res = await fetch("/api/bootstrap");
  if (!res.ok) throw new Error("Could not load app data");
  const data = await res.json();
  state.settings = data.settings;
  state.items = data.items;
  state.trades = data.trades;
  state.raisedByOptions = data.raised_by_options;

  setOptions($("project"), state.settings.projects);
  setOptions($("editProject"), state.settings.projects);
  if ($("project")) $("project").value = state.settings.active_project;
  setOptions($("raisedBy"), state.raisedByOptions, "Who raised this?");
  setOptions($("editRaisedBy"), state.raisedByOptions, "Who raised this?");
  setOptions($("trade"), state.trades, "Select trade");
  setOptions($("editTrade"), state.trades, "Select trade");
  if ($("dueDate")) $("dueDate").value = dueDate(7);
  refreshProjectConfig();
  refreshEditProjectConfig(state.settings.active_project);
  refreshSubcontractors();
  refreshEditSubcontractors();
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
  if (!files || files.length === 0) return;
  const next = await Promise.all([...files].map(fileToDataUrl));
  state.photos.push(...next);
  renderThumbs();
  if (input) input.value = "";
  clearValidation();
}

function draftFromNote() {
  const value = $("voiceNote").value.trim();
  if (!value) return;
  const lower = value.toLowerCase();
  const cfg = projectConfig();
  for (const building of cfg?.buildings || []) if (lower.includes(building.toLowerCase())) $("building").value = building;
  for (const unit of cfg?.units || []) if (lower.includes(unit.toLowerCase())) $("unit").value = unit;
  for (const room of cfg?.rooms || []) if (lower.includes(room.toLowerCase())) $("room").value = room;
  for (const trade of state.trades) if (lower.includes(trade.toLowerCase())) $("trade").value = trade;
  if (!$("description").value.trim()) $("description").value = value;
  refreshSubcontractors();
  clearValidation();
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
    voice_note: voiceText ? { transcript: voiceText, parsed_fields: {}, status: "parsed" } : null,
    created_by: state.settings.prepared_by,
  };
}

function clientValidate(issueNow) {
  const data = payload();
  if (!data.building) return "Select a building.";
  if (!data.unit) return "Select a unit / area.";
  if ((data.type === "defect" || data.type === "client") && data.original_photos.length === 0) {
    return data.type === "client" ? "A Client Defect requires at least one original photo." : "A Defect requires at least one original photo.";
  }
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
    const res = await fetch(`/api/items?issue_now=${issueNow}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not save item");
    }
    const item = await res.json();
    state.items.unshift(item);
    renderItems();
    resetForm(true);
    toast(issueNow ? "Item issued" : "Item saved");
  } catch (error) {
    showValidation(error.message || "Could not save item.");
  }
}

async function patchItem(id, patch) {
  const res = await fetch(`/api/items/${id}?by=${encodeURIComponent(state.settings.prepared_by)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Update failed");
  }
  const item = await res.json();
  const index = state.items.findIndex((candidate) => candidate.id === id);
  if (index >= 0) state.items[index] = item;
  renderItems();
  return item;
}

async function action(id, endpoint, body = {}) {
  const res = await fetch(`/api/items/${id}/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ by: state.settings.prepared_by, ...body }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Action failed");
  }
  const item = await res.json();
  const index = state.items.findIndex((candidate) => candidate.id === id);
  if (index >= 0) state.items[index] = item;
  renderItems();
  return item;
}

function evidenceCounts(item) {
  return {
    original: item.original_photos?.length || 0,
    rectification: item.rectification_evidence?.length || 0,
    closeout: item.closeout_evidence?.length || 0,
  };
}

function locationText(item) {
  return [item.building, item.level, item.unit, item.room].filter(Boolean).join(" / ") || "Unassigned location";
}

function filteredItems() {
  const query = ($("searchInput")?.value || "").trim().toLowerCase();
  const status = $("statusFilter")?.value || "all";
  return state.items.filter((item) => {
    if (status !== "all" && item.status !== status) return false;
    if (!query) return true;
    return [item.code, item.type, item.status, item.description, item.project, item.building, item.level, item.unit, item.room, item.trade, item.subcontractor]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
}

function renderStats() {
  const bar = $("statsBar");
  if (!bar) return;
  const terminal = new Set(["closed", "complete"]);
  const today = new Date().toISOString().slice(0, 10);
  const open = state.items.filter((item) => !terminal.has(item.status)).length;
  const overdue = state.items.filter((item) => !terminal.has(item.status) && item.due_date && item.due_date < today).length;
  const closed = state.items.filter((item) => terminal.has(item.status)).length;
  const stats = [[state.items.length, "Total"], [open, "Open"], [overdue, "Overdue"], [closed, "Closed"]];
  bar.innerHTML = stats.map(([value, label]) => `<div class="stat-card"><span class="stat-value">${value}</span><span class="stat-label">${label}</span></div>`).join("");
}

function renderItems() {
  const list = $("itemsList");
  if (!list) return;
  const items = filteredItems();
  renderStats();
  if ($("listCount")) $("listCount").textContent = `${items.length} shown`;
  list.textContent = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "item-card";
    empty.innerHTML = `<div class="code">No matching items</div><div class="meta">Adjust the register filters or capture a new item.</div>`;
    list.appendChild(empty);
    return;
  }
  items.slice(0, 50).forEach((item) => {
    const counts = evidenceCounts(item);
    const div = document.createElement("div");
    div.className = `item-card status-${item.status}`;
    div.innerHTML = `
      <div class="item-top">
        <div>
          <div class="code">${text(item.code)}</div>
          <div class="item-type">${text(TYPE_LABELS[item.type] || item.type)}</div>
        </div>
        <span class="status ${text(item.status)}">${text(STATUS_LABELS[item.status] || item.status)}</span>
      </div>
      <div class="desc">${text(item.description)}</div>
      <div class="item-meta-grid">
        <div><strong>Location</strong> · ${text(locationText(item))}</div>
        <div><strong>Trade</strong> · ${text(item.trade || "No trade")}</div>
        <div><strong>Subcontractor</strong> · ${text(item.subcontractor || "Unassigned")}</div>
        <div><strong>Due</strong> · ${text(item.due_date)}</div>
      </div>
      <div class="evidence-counts">
        <span class="ev-chip original">Original ${counts.original}</span>
        <span class="ev-chip rectification">Rectification ${counts.rectification}</span>
        <span class="ev-chip closeout">Closeout ${counts.closeout}</span>
      </div>
      <div class="card-actions">
        <button type="button" data-edit>Edit</button>
        <button type="button" data-issue>Issue</button>
        <button type="button" data-progress>In Progress</button>
        <button type="button" data-rectify>Add Rectification</button>
        <button type="button" data-ready>Ready</button>
        <button type="button" data-inspect>Inspect</button>
        <button type="button" data-reject>Reject</button>
        <button type="button" data-close>Close</button>
        <button type="button" data-comment>Comment</button>
        <button type="button" data-report>Report</button>
      </div>`;
    div.querySelector("[data-edit]").onclick = () => openEdit(item);
    div.querySelector("[data-issue]").onclick = async () => {
      if (!item.subcontractor) return toast("Add a subcontractor before issuing.");
      try {
        const res = await fetch(`/api/items/${item.id}/issue`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to: item.subcontractor, by: state.settings.prepared_by }),
        });
        if (!res.ok) throw new Error("Issue failed");
        const updated = await res.json();
        state.items[state.items.findIndex((candidate) => candidate.id === item.id)] = updated;
        renderItems();
        toast("Item issued");
      } catch (error) { toast(error.message || "Issue failed"); }
    };
    div.querySelector("[data-progress]").onclick = () => action(item.id, "in-progress").then(() => toast("Marked in progress")).catch((e) => toast(e.message));
    div.querySelector("[data-rectify]").onclick = () => addRectification(item);
    div.querySelector("[data-ready]").onclick = () => action(item.id, "ready").then(() => toast("Marked ready for review")).catch((e) => toast(e.message));
    div.querySelector("[data-inspect]").onclick = () => action(item.id, "inspection/start").then(() => toast("Inspection started")).catch((e) => toast(e.message));
    div.querySelector("[data-reject]").onclick = () => rejectItem(item);
    div.querySelector("[data-close]").onclick = () => closeItem(item);
    div.querySelector("[data-comment]").onclick = () => addComment(item);
    div.querySelector("[data-report]").onclick = () => window.open("/api/reports/handover", "_blank");
    list.appendChild(div);
  });
}

async function postItemUpdate(item, endpoint, body, successMessage) {
  try {
    const res = await fetch(`/api/items/${item.id}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || "Action failed");
    }
    const updated = await res.json();
    const index = state.items.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) state.items[index] = updated;
    renderItems();
    toast(successMessage);
  } catch (error) {
    toast(error.message || "Action failed");
  }
}

function addRectification(item) {
  const comment = prompt("Rectification evidence", "Works completed and ready for review.");
  if (comment === null || !comment.trim()) return;
  postItemUpdate(item, "rectification", { by: state.settings.prepared_by, comment: comment.trim(), advance_to_ready: false }, "Rectification evidence added");
}

function rejectItem(item) {
  const reason = prompt("Reason for rejection");
  if (reason === null || !reason.trim()) return;
  postItemUpdate(item, "inspection/reject", { by: state.settings.prepared_by, reason: reason.trim() }, "Item rejected");
}

function addComment(item) {
  const comment = prompt("Add register comment");
  if (comment === null || !comment.trim()) return;
  postItemUpdate(item, "comments", { by: state.settings.prepared_by, text: comment.trim() }, "Comment added");
}

async function closeItem(item) {
  const note = prompt("Closeout note", "Reviewed and accepted for closeout.");
  if (note === null) return;
  try {
    const res = await fetch(`/api/items/${item.id}/closeout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ by: state.settings.prepared_by, role: "Supervisor", note, confirmation: "Confirmed acceptable for closeout" }),
    });
    if (!res.ok) throw new Error("Closeout failed");
    const updated = await res.json();
    state.items[state.items.findIndex((candidate) => candidate.id === item.id)] = updated;
    renderItems();
    toast("Item closed");
  } catch (error) { toast(error.message || "Closeout failed"); }
}

function openEdit(item) {
  if (!$("editOverlay")) {
    const description = prompt("Edit description", item.description);
    if (description !== null) patchItem(item.id, { description }).then(() => toast("Item updated")).catch((e) => toast(e.message));
    return;
  }
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

function closeEdit() {
  state.editingItem = null;
  if (!$("editOverlay")) return;
  $("editOverlay").classList.add("hidden");
  $("editOverlay").setAttribute("aria-hidden", "true");
}

function editPayload() {
  const type = $("editType").value;
  return {
    type,
    project: $("editProject").value,
    building: $("editBuilding").value.trim(),
    level: $("editLevel").value.trim(),
    unit: $("editUnit").value.trim(),
    room: $("editRoom").value.trim(),
    trade: $("editTrade").value,
    subcontractor: $("editSubcontractor").value.trim(),
    priority: $("editPriority").value,
    due_date: $("editDueDate").value,
    description: $("editDescription").value.trim(),
    raised_by: type === "client" ? $("editRaisedBy").value : null,
  };
}

async function saveEdit() {
  if (!state.editingItem) return;
  clearEditAlert();
  const patch = editPayload();
  if (!patch.building) return showEditAlert("Building cannot be blank.");
  if (!patch.unit) return showEditAlert("Unit / Area cannot be blank.");
  if (!patch.description) return showEditAlert("Description cannot be blank.");
  if (patch.type === "client" && !patch.raised_by) return showEditAlert("Client Defects require a Raised By / source.");
  try {
    await patchItem(state.editingItem.id, patch);
    closeEdit();
    toast("Item details updated");
  } catch (error) {
    showEditAlert(error.message || "Could not update item.");
  }
}

function bindKeyboardDone() {
  const done = $("keyboardDone");
  if (!done) return;
  document.addEventListener("focusin", (event) => { if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) done.classList.remove("hidden"); });
  document.addEventListener("focusout", () => setTimeout(() => done.classList.add("hidden"), 120));
  done.onclick = () => { if (document.activeElement) document.activeElement.blur(); done.classList.add("hidden"); };
}

function bind() {
  $("type").onchange = () => {
    const itemType = $("type").value;
    $("raisedByWrap").classList.toggle("hidden", itemType !== "client");
    $("photoRequirement").textContent = itemType === "incomplete" ? "Incomplete Work: photo recommended" : itemType === "client" ? "Client Defect: photo required" : "Defect: photo required";
    clearValidation();
  };
  $("project").onchange = () => { refreshProjectConfig(); $("building").value = ""; $("level").value = ""; $("unit").value = ""; $("room").value = ""; };
  $("trade").onchange = () => { refreshSubcontractors(); $("subcontractor").value = ""; };
  $("cameraInput").onchange = (event) => handleFiles(event.target.files, event.target);
  $("libraryInput").onchange = (event) => handleFiles(event.target.files, event.target);
  $("draftFromNote").onclick = draftFromNote;
  $("saveBtn").onclick = () => save(false);
  $("issueBtn").onclick = () => save(true);
  $("resetDemo").onclick = async () => { await fetch("/api/reset-demo", { method: "POST" }); await bootstrap(); toast("Demo reset"); };
  if ($("editClose")) $("editClose").onclick = closeEdit;
  if ($("editCancel")) $("editCancel").onclick = closeEdit;
  if ($("editSave")) $("editSave").onclick = saveEdit;
  if ($("editOverlay")) $("editOverlay").onclick = (event) => { if (event.target.id === "editOverlay") closeEdit(); };
  if ($("editType")) $("editType").onchange = () => $("editRaisedByWrap").classList.toggle("hidden", $("editType").value !== "client");
  if ($("editProject")) $("editProject").onchange = () => { refreshEditProjectConfig($("editProject").value); $("editBuilding").value = ""; $("editLevel").value = ""; $("editUnit").value = ""; $("editRoom").value = ""; };
  if ($("editTrade")) $("editTrade").onchange = () => { refreshEditSubcontractors(); $("editSubcontractor").value = ""; };
  if ($("searchInput")) $("searchInput").oninput = renderItems;
  if ($("statusFilter")) $("statusFilter").onchange = renderItems;
  if ($("clearFilters")) $("clearFilters").onclick = () => {
    if ($("searchInput")) $("searchInput").value = "";
    if ($("statusFilter")) $("statusFilter").value = "all";
    renderItems();
  };
}

bindKeyboardDone();
bind();
bootstrap().catch((error) => toast(error.message));
