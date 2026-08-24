const API_BASE = "http://localhost:8000";

const STATUSES = ["saved", "applied", "screen", "interview", "offer", "rejected", "withdrawn"];

const state = {
  q: "",
  statuses: new Set(),
  source: "",
  sortBy: "created_at",
  sortDir: "desc",
  limit: 25,
  offset: 0,
};

const el = {
  searchInput: document.getElementById("search-input"),
  statusFilters: document.getElementById("status-filters"),
  sourceFilter: document.getElementById("source-filter"),
  sortSelect: document.getElementById("sort-select"),
  summary: document.getElementById("summary"),
  tableBody: document.getElementById("applications-body"),
  emptyState: document.getElementById("empty-state"),
  loadingState: document.getElementById("loading-state"),
  errorState: document.getElementById("error-state"),
  prevPage: document.getElementById("prev-page"),
  nextPage: document.getElementById("next-page"),
  pageInfo: document.getElementById("page-info"),
  detailPanel: document.getElementById("detail-panel"),
  detailBackdrop: document.getElementById("detail-backdrop"),
  detailContent: document.getElementById("detail-content"),
  closeDetail: document.getElementById("close-detail"),
};

function renderStatusChips() {
  el.statusFilters.innerHTML = "";
  for (const status of STATUSES) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "filter-chip";
    chip.textContent = status;
    chip.setAttribute("aria-pressed", state.statuses.has(status) ? "true" : "false");
    chip.addEventListener("click", () => {
      if (state.statuses.has(status)) {
        state.statuses.delete(status);
      } else {
        state.statuses.add(status);
      }
      state.offset = 0;
      renderStatusChips();
      loadApplications();
    });
    el.statusFilters.appendChild(chip);
  }
}

function buildQuery() {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  for (const status of state.statuses) params.append("status", status);
  if (state.source) params.set("source", state.source);
  params.set("sort_by", state.sortBy);
  params.set("sort_dir", state.sortDir);
  params.set("limit", String(state.limit));
  params.set("offset", String(state.offset));
  return params.toString();
}

function setLoading(isLoading) {
  el.loadingState.hidden = !isLoading;
  if (isLoading) {
    el.errorState.hidden = true;
    el.emptyState.hidden = true;
  }
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function renderRows(items) {
  el.tableBody.innerHTML = "";
  for (const app of items) {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.addEventListener("click", () => openDetail(app.id));

    tr.innerHTML = `
      <td>${escapeHtml(app.company)}</td>
      <td class="role-cell"><span class="role-title">${escapeHtml(app.role)}</span></td>
      <td><span class="status-badge status-${app.status}">${app.status}</span></td>
      <td>${escapeHtml(app.location || "—")}</td>
      <td><span class="source-tag">${escapeHtml(app.source)}</span></td>
      <td>${formatDate(app.updated_at)}</td>
    `;
    el.tableBody.appendChild(tr);
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function renderPagination(total) {
  const start = total === 0 ? 0 : state.offset + 1;
  const end = Math.min(state.offset + state.limit, total);
  el.pageInfo.textContent = `${start}–${end} of ${total}`;
  el.prevPage.disabled = state.offset === 0;
  el.nextPage.disabled = end >= total;
}

async function loadApplications() {
  setLoading(true);
  try {
    const response = await fetch(`${API_BASE}/applications?${buildQuery()}`);
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    const data = await response.json();

    renderRows(data.items);
    renderPagination(data.total);
    el.summary.textContent = `${data.total} application${data.total === 1 ? "" : "s"}`;
    el.emptyState.hidden = data.items.length !== 0;
  } catch (err) {
    el.errorState.textContent = `Couldn't load applications: ${err.message}. Is the API running at ${API_BASE}?`;
    el.errorState.hidden = false;
    el.tableBody.innerHTML = "";
    el.summary.textContent = "";
  } finally {
    setLoading(false);
  }
}

async function openDetail(id) {
  el.detailPanel.hidden = false;
  el.detailPanel.setAttribute("aria-hidden", "false");
  el.detailBackdrop.hidden = false;
  el.detailContent.innerHTML = `<p class="loading-state">Loading…</p>`;

  try {
    const response = await fetch(`${API_BASE}/applications/${id}`);
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    const app = await response.json();
    renderDetail(app);
  } catch (err) {
    el.detailContent.innerHTML = `<p class="error-state">Couldn't load this application: ${escapeHtml(err.message)}</p>`;
  }
}

function renderDetail(app) {
  const events = app.events
    .slice()
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const eventsHtml = events.length
    ? events
        .map(
          (evt) => `
        <div class="timeline-event">
          <div class="timeline-desc">${escapeHtml(evt.description || evt.event_type)}</div>
          <div class="timeline-meta">${formatDate(evt.created_at)} · ${escapeHtml(evt.source)}</div>
        </div>`
        )
        .join("")
    : `<p class="timeline-meta">No timeline events yet.</p>`;

  el.detailContent.innerHTML = `
    <h2>${escapeHtml(app.company)}</h2>
    <p class="detail-role">${escapeHtml(app.role)}</p>

    <div class="detail-field"><span class="label">Status</span><span class="status-badge status-${app.status}">${app.status}</span></div>
    <div class="detail-field"><span class="label">Location</span>${escapeHtml(app.location || "—")}</div>
    <div class="detail-field"><span class="label">Source</span>${escapeHtml(app.source)}</div>
    <div class="detail-field"><span class="label">Applied</span>${formatDate(app.applied_date)}</div>
    <div class="detail-field"><span class="label">Saved</span>${formatDate(app.created_at)}</div>
    ${app.url ? `<div class="detail-field"><span class="label">Link</span><a href="${escapeHtml(app.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(app.url)}</a></div>` : ""}
    ${app.notes ? `<div class="detail-field"><span class="label">Notes</span>${escapeHtml(app.notes)}</div>` : ""}

    <div class="timeline">
      <h3>Timeline</h3>
      ${eventsHtml}
    </div>
  `;
}

function closeDetail() {
  el.detailPanel.hidden = true;
  el.detailPanel.setAttribute("aria-hidden", "true");
  el.detailBackdrop.hidden = true;
}

let searchDebounce;
el.searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    state.q = el.searchInput.value.trim();
    state.offset = 0;
    loadApplications();
  }, 300);
});

el.sourceFilter.addEventListener("change", () => {
  state.source = el.sourceFilter.value;
  state.offset = 0;
  loadApplications();
});

el.sortSelect.addEventListener("change", () => {
  const [sortBy, sortDir] = el.sortSelect.value.split(":");
  state.sortBy = sortBy;
  state.sortDir = sortDir;
  loadApplications();
});

el.prevPage.addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadApplications();
});

el.nextPage.addEventListener("click", () => {
  state.offset += state.limit;
  loadApplications();
});

el.closeDetail.addEventListener("click", closeDetail);
el.detailBackdrop.addEventListener("click", closeDetail);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDetail();
});

renderStatusChips();
loadApplications();
