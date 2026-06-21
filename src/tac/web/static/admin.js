const csrf = document.querySelector('meta[name="tac-csrf"]').content;

const state = {
  page: Number(new URLSearchParams(location.search).get("page") || "1"),
  pageSize: 50,
  q: new URLSearchParams(location.search).get("q") || "",
  status: new URLSearchParams(location.search).get("status") || "",
  source: new URLSearchParams(location.search).get("source") || "",
  failedOnly: new URLSearchParams(location.search).get("failed_only") === "true",
  sourcesHash: "",
};

const $ = (selector) => document.querySelector(selector);

function setStatus(text) {
  $("#runtime-status").textContent = text;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (!["GET", "HEAD"].includes(options.method || "GET")) {
    headers.set("x-tac-csrf", csrf);
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const error = new Error(payload.detail || response.statusText);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function updateUrl() {
  const params = new URLSearchParams();
  if (state.page > 1) params.set("page", String(state.page));
  if (state.q) params.set("q", state.q);
  if (state.status) params.set("status", state.status);
  if (state.source) params.set("source", state.source);
  if (state.failedOnly) params.set("failed_only", "true");
  history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
}

function errorText(error) {
  if (error.status === 403) return "Write request denied. Open and operate from same-origin /admin.";
  if (error.status === 409) return "Conflict: a job is running or the file changed.";
  if (error.status === 429) return "Too many requests: concurrency or queue limit reached.";
  return error.message || "Request failed";
}

async function loadSummary() {
  const summary = await api("/api/admin/summary");
  const labels = [
    ["total", "Total"],
    ["candidate", "Candidates"],
    ["accepted", "Accepted"],
    ["rejected", "Rejected"],
    ["low_confidence", "Low confidence"],
    ["archived", "Archived"],
    ["fetch_failed", "Fetch failures"],
    ["evaluation_failed", "Evaluation failures"],
  ];
  $("#summary-grid").innerHTML = labels
    .map(([key, label]) => `<div class="metric"><span>${label}</span><b>${summary[key] || 0}</b></div>`)
    .join("");
}

async function loadSourceNames() {
  const payload = await api("/api/admin/source-names");
  $("#source-filter").innerHTML =
    '<option value="">All sources</option>' +
    payload.items
      .map((source) => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`)
      .join("");
  $("#source-filter").value = state.source;
}

function renderArticles(page) {
  $("#articles-body").innerHTML = page.items
    .map((item) => {
      const statusClass = item.status || "";
      const archiveButton =
        item.status === "archived"
          ? `<button data-action="unarchive" data-id="${item.id}">unarchive</button>`
          : `<button data-action="archive" data-id="${item.id}">archive</button>`;
      return `
        <tr>
          <td><button data-action="detail" data-id="${item.id}">${escapeHtml(item.title)}</button><br><span class="muted">${escapeHtml(item.url)}</span></td>
          <td>${escapeHtml(item.source_name)}</td>
          <td><span class="tag ${statusClass}">${item.status}</span></td>
          <td>${escapeHtml(item.fetch_status || "-")}<br><span class="muted">${escapeHtml(item.fetch_error || "")}</span></td>
          <td>${escapeHtml(item.evaluation_status || "-")}<br><span class="muted">${escapeHtml(item.evaluation_error || "")}</span></td>
          <td>${item.retry_count}</td>
          <td>${escapeHtml(item.updated_at)}</td>
          <td class="actions">
            <button data-action="retry-fetch" data-id="${item.id}">fetch</button>
            <button data-action="retry-evaluate" data-id="${item.id}">eval</button>
            <button data-action="status" data-status="candidate" data-id="${item.id}">candidate</button>
            <button data-action="status" data-status="accepted" data-id="${item.id}">accept</button>
            <button data-action="status" data-status="rejected" data-id="${item.id}">reject</button>
            <button data-action="status" data-status="low_confidence" data-id="${item.id}">low</button>
            ${archiveButton}
          </td>
        </tr>`;
    })
    .join("");
  $("#page-label").textContent = `Page ${page.page} / ${page.total} total`;
  $("#prev-page").disabled = page.page <= 1;
  $("#next-page").disabled = !page.has_next;
}

async function loadArticles() {
  updateUrl();
  const params = new URLSearchParams({
    page: String(state.page),
    page_size: String(state.pageSize),
    sort: "updated_at",
    order: "desc",
  });
  if (state.q) params.set("q", state.q);
  if (state.status) params.set("status", state.status);
  if (state.source) params.set("source", state.source);
  if (state.failedOnly) params.set("failed_only", "true");
  const page = await api(`/api/admin/articles?${params}`);
  renderArticles(page);
}

async function loadFailures() {
  const payload = await api("/api/admin/failures?page_size=8");
  $("#failures-list").innerHTML =
    payload.items
      .map(
        (item) => `
          <div class="list-item">
            <b>${escapeHtml(item.stage)}</b> #${item.article_id} ${escapeHtml(item.title)}<br>
            ${escapeHtml(item.error || "")}<br>
            <button data-action="${item.stage === "fetch" ? "retry-fetch" : "retry-evaluate"}" data-id="${item.article_id}">Retry</button>
          </div>`,
      )
      .join("") || '<p class="muted">No failures</p>';
}

async function loadJobs() {
  const payload = await api("/api/admin/jobs");
  $("#jobs-list").innerHTML =
    payload.items
      .slice(0, 8)
      .map(
        (job) =>
          `<div class="list-item">${job.kind} ${job.status} ${job.job_id}<br>${escapeHtml(job.error || JSON.stringify(job.result || ""))}</div>`,
      )
      .join("") || '<p class="muted">No jobs</p>';
}

async function submitJob(kind) {
  const job = await api(`/api/admin/jobs/${kind}`, { method: "POST" });
  setStatus(`Job submitted: ${job.job_id}`);
  await pollJob(job.job_id);
}

async function pollJob(jobId) {
  const timer = setInterval(async () => {
    try {
      const job = await api(`/api/admin/jobs/${jobId}`);
      setStatus(`${job.kind}: ${job.status}`);
      await loadJobs();
      if (["succeeded", "failed", "skipped"].includes(job.status)) {
        clearInterval(timer);
        await Promise.all([loadSummary(), loadArticles(), loadFailures()]);
      }
    } catch (error) {
      clearInterval(timer);
      setStatus(errorText(error));
    }
  }, 2000);
}

async function loadSources() {
  const payload = await api("/api/admin/sources");
  state.sourcesHash = payload.content_hash;
  $("#sources-editor").value = payload.content;
}

async function saveSources() {
  const payload = await api("/api/admin/sources", {
    method: "PUT",
    body: JSON.stringify({
      content: $("#sources-editor").value,
      previous_hash: state.sourcesHash,
    }),
  });
  state.sourcesHash = payload.content_hash;
  $("#sources-status").textContent = "Saved";
}

async function showDetail(id) {
  const detail = await api(`/api/admin/articles/${id}`);
  $("#detail-content").textContent = JSON.stringify(detail, null, 2);
  $("#detail-drawer").classList.add("open");
  $("#detail-drawer").setAttribute("aria-hidden", "false");
}

async function handleArticleAction(button) {
  const id = button.dataset.id;
  const action = button.dataset.action;
  if (action === "detail") {
    await showDetail(id);
    return;
  }
  if (action === "retry-fetch" || action === "retry-evaluate") {
    const suffix = action === "retry-fetch" ? "retry-fetch" : "retry-evaluate";
    const job = await api(`/api/admin/articles/${id}/${suffix}`, { method: "POST" });
    setStatus(`Job submitted: ${job.job_id}`);
    await pollJob(job.job_id);
    return;
  }
  if (action === "archive" || action === "unarchive") {
    await api(`/api/admin/articles/${id}/${action}`, { method: "POST" });
  }
  if (action === "status") {
    await api(`/api/admin/articles/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status: button.dataset.status }),
    });
  }
  await Promise.all([loadSummary(), loadArticles(), loadFailures()]);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function bindEvents() {
  $("#search-input").value = state.q;
  $("#status-filter").value = state.status;
  $("#source-filter").value = state.source;
  $("#failed-only").checked = state.failedOnly;

  document.querySelectorAll("[data-job]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        button.disabled = true;
        await submitJob(button.dataset.job);
      } catch (error) {
        setStatus(errorText(error));
      } finally {
        button.disabled = false;
      }
    });
  });

  $("#search-input").addEventListener(
    "input",
    debounce((event) => {
      state.q = event.target.value.trim();
      state.page = 1;
      loadArticles().catch((error) => setStatus(errorText(error)));
    }, 300),
  );
  $("#status-filter").addEventListener("change", (event) => {
    state.status = event.target.value;
    state.page = 1;
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#source-filter").addEventListener("change", (event) => {
    state.source = event.target.value;
    state.page = 1;
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#failed-only").addEventListener("change", (event) => {
    state.failedOnly = event.target.checked;
    state.page = 1;
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#next-page").addEventListener("click", () => {
    state.page += 1;
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#articles-body").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    try {
      await handleArticleAction(button);
    } catch (error) {
      setStatus(errorText(error));
    }
  });
  $("#failures-list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    try {
      await handleArticleAction(button);
    } catch (error) {
      setStatus(errorText(error));
    }
  });
  $("#refresh-jobs").addEventListener("click", () => {
    loadJobs().catch((error) => setStatus(errorText(error)));
  });
  $("#refresh-failures").addEventListener("click", () => {
    loadFailures().catch((error) => setStatus(errorText(error)));
  });
  $("#save-sources").addEventListener("click", async () => {
    try {
      await saveSources();
    } catch (error) {
      $("#sources-status").textContent = errorText(error);
    }
  });
  $("#close-detail").addEventListener("click", () => {
    $("#detail-drawer").classList.remove("open");
    $("#detail-drawer").setAttribute("aria-hidden", "true");
  });
}

async function boot() {
  bindEvents();
  await loadSourceNames();
  await Promise.all([loadSummary(), loadArticles(), loadFailures(), loadJobs(), loadSources()]);
  setStatus("Ready");
}

boot().catch((error) => setStatus(errorText(error)));
