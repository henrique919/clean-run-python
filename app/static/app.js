const state = {
  settings: null,
  items: [],
  trades: [],
  raisedByOptions: [],
  photos: [],
  editingItem: null,
  actionItem: null,
  actionMode: null,
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

function refreshSubcontractors() { setDatalist("subOptions", subcontractorsForTrade($("trade")?.value)); }
function refreshEditSubcontractors() { setDatalist("editSubOptions", subcontractorsForTrade($("editTrade")?.value)); }

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
    const res = await fetch(`/api/items?issue_now=${issueNow}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not save item");
    }
    const item = await res.json();
    state.items.unshift(item);
    renderItems();
    resetForm(true);
    toast(issueNow ? "Item issued" : "Item saved");
  } catch (error) { showValidation(error.message || "Could not save item."); }
}

async function patchItem(id, patch) {
  const res = await fetch(`/api/items/${id}?by=${encodeURIComponent(state.settings.prepared_by)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
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
  const res = await fetch(`/api/items/${id}/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ by: state.settings.prepared_by, ...body }) });
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

function visibleItems() {
  const status = $("statusFilter")?.value || "all";
  const query = ($("searchInput")?.value || "").trim().toLowerCase();
  return state.items.filter((item) => {
    if (status !== "all" && item.status !== status) return false;
    if (!query) return true;
    const haystack = [item.code, TYPE_LABELS[item.type], STATUS_LABELS[item.status], item.description, item.trade, item.subcontractor, locationText(item)].join(" ").toLowerCase();
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

function nextActionFor(item) {
  if (item.status === "open") return { label: item.trade && item.subcontractor ? "Issue" : "Edit to issue", run: () => item.trade && item.subcontractor ? issueItem(item) : openEdit(item) };
  if (item.status === "issued") return { label: "Start work", run: () => quickAction(item, "in-progress", "Marked in progress") };
  if (item.status === "in_progress" || item.status === "rejected") return { label: "Add rectification", run: () => openActionDrawer(item, "rectification") };
  if (item.status === "ready_for_review") return { label: "Start inspection", run: () => quickAction(item, "inspection/start", "Inspection started") };
  if (item.status === "under_inspection") return { label: "Close", run: () => openActionDrawer(item, "close") };
  return { label: "Report", run: () => window.open("/api/reports/handover", "_blank") };
}

async function quickAction(item, endpoint, success) { try { await action(item.id, endpoint); toast(success); } catch (error) { toast(error.message || "Action failed"); } }
async function issueItem(item) {
  try {
    const res = await fetch(`/api/items/${item.id}/issue`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: item.subcontractor, by: state.settings.prepared_by }) });
    if (!res.ok) throw new Error("Issue failed");
    replaceItem(await res.json());
    toast("Item issued");
  } catch (error) { toast(error.message || "Issue failed"); }
}

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
    menu.appendChild(menuButton("Report", "Open handover report", () => window.open("/api/reports/handover", "_blank")));
    return;
  }
  const titleMap = { rectification: "Add Rectification", reject: "Reject Item", comment: "Add Comment", close: "Close Item" };
  $("actionKicker").textContent = titleMap[mode] || "Item action";
  submit.textContent = mode === "reject" ? "Reject" : mode === "close" ? "Close item" : "Save";
  if (mode === "rectification") form.innerHTML = `<p class="hint">Record what the subcontractor has done and attach evidence where available.</p><label for="actionPhoto">Rectification photo</label><input id="actionPhoto" type="file" accept="image/*" capture="environment" /><label for="actionComment">Comment</label><textarea id="actionComment" placeholder="Describe the rectification completed"></textarea><label class="check-row"><input id="actionAdvance" type="checkbox" /> Mark ready for review</label>`;
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
      const res = await fetch(`/api/items/${item.id}/rectification`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ photo: photos[0] || null, comment, by: state.settings.prepared_by, advance_to_ready: $("actionAdvance")?.checked || false }) });
      if (!res.ok) throw new Error("Rectification failed");
      updated = await res.json();
      toast("Rectification added");
    } else if (mode === "reject") {
      const reason = $("actionReason").value.trim();
      if (!reason) return toast("Add a rejection reason");
      updated = await action(item.id, "inspection/reject", { reason });
      toast("Item rejected");
    } else if (mode === "comment") {
      const value = $("actionComment").value.trim();
      if (!value) return toast("Add a comment");
      const res = await fetch(`/api/items/${item.id}/comments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: value, by: state.settings.prepared_by }) });
      if (!res.ok) throw new Error("Comment failed");
      updated = await res.json();
      toast("Comment added");
    } else if (mode === "close") {
      const photos = await handleFiles($("actionPhoto")?.files || []);
      const note = $("actionNote").value.trim();
      const confirmation = $("actionConfirmation").value.trim();
      const res = await fetch(`/api/items/${item.id}/closeout`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ photo: photos[0] || null, by: state.settings.prepared_by, role: "Supervisor", note, confirmation }) });
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
  $("type").onchange = () => { const itemType = $("type").value; $("raisedByWrap").classList.toggle("hidden", itemType !== "client"); $("photoRequirement").textContent = itemType === "incomplete" ? "Incomplete Work: photo recommended" : itemType === "client" ? "Client Defect: photo required" : "Defect: photo required"; clearValidation(); };
  $("project").onchange = () => { refreshProjectConfig(); $("building").value = ""; $("level").value = ""; $("unit").value = ""; $("room").value = ""; };
  $("trade").onchange = () => { refreshSubcontractors(); $("subcontractor").value = ""; };
  $("cameraInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
  $("libraryInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
  $("draftFromNote").onclick = draftFromNote;
  $("saveBtn").onclick = () => save(false);
  $("issueBtn").onclick = () => save(true);
  $("resetDemo").onclick = async () => { await fetch("/api/reset-demo", { method: "POST" }); await bootstrap(); toast("Demo reset"); };
  $("searchInput")?.addEventListener("input", renderItems);
  $("statusFilter")?.addEventListener("change", renderItems);
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
bootstrap().catch((error) => toast(error.message));
