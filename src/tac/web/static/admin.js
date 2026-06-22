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
          `<div class="list-item">
            <b>${escapeHtml(job.kind)}</b> ${escapeHtml(job.status)} ${escapeHtml(job.trigger || "manual")}
            ${job.schedule_id ? `/${escapeHtml(job.schedule_id)}` : ""}<br>
            <span class="muted">${escapeHtml(job.started_at || job.created_at)}${job.finished_at ? ` -> ${escapeHtml(job.finished_at)}` : ""}</span><br>
            ${escapeHtml(job.error || JSON.stringify(job.result || ""))}
          </div>`,
      )
      .join("") || '<p class="muted">No jobs</p>';
}

async function loadSchedules() {
  const payload = await api("/api/admin/schedules");
  $("#schedules-list").innerHTML =
    payload.items
      .map(
        (schedule) => `
          <div class="list-item">
            <b>${escapeHtml(schedule.schedule_id)}</b> ${escapeHtml(schedule.kind)}
            ${schedule.enabled ? "enabled" : "disabled"}<br>
            <span class="muted">${escapeHtml(schedule.cron)} ${escapeHtml(schedule.timezone)} next ${escapeHtml(schedule.next_run_at || "-")}</span><br>
            ${schedule.latest_job ? `last ${escapeHtml(schedule.latest_job.status)} ${escapeHtml(schedule.latest_job.finished_at || schedule.latest_job.created_at)}` : "No runs"}<br>
            <button data-schedule-trigger="${escapeHtml(schedule.schedule_id)}">Trigger</button>
          </div>`,
      )
      .join("") || '<p class="muted">No schedules</p>';
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

async function previewRsshub() {
  const paramsText = $("#rsshub-params").value.trim() || "{}";
  let params;
  try {
    params = JSON.parse(paramsText);
  } catch (error) {
    $("#rsshub-status").textContent = "Params JSON is invalid";
    return;
  }
  const payload = await api("/api/admin/sources/preview-rsshub", {
    method: "POST",
    body: JSON.stringify({
      route: $("#rsshub-route").value.trim(),
      instance: $("#rsshub-instance").value.trim() || null,
      limit: Number($("#rsshub-limit").value || "10"),
      params,
    }),
  });
  $("#rsshub-status").textContent = payload.feed_url;
  $("#rsshub-preview-list").innerHTML =
    payload.entries
      .map(
        (entry) => `
          <div class="list-item">
            <b>${escapeHtml(entry.title)}</b><br>
            <a href="${escapeHtml(entry.url)}" target="_blank" rel="noreferrer">${escapeHtml(entry.url)}</a>
          </div>`,
      )
      .join("") || '<p class="muted">No entries</p>';
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
  $("#refresh-schedules").addEventListener("click", () => {
    loadSchedules().catch((error) => setStatus(errorText(error)));
  });
  $("#schedules-list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-schedule-trigger]");
    if (!button) return;
    try {
      const job = await api(`/api/admin/schedules/${button.dataset.scheduleTrigger}/trigger`, { method: "POST" });
      setStatus(`Schedule submitted: ${job.job_id}`);
      await pollJob(job.job_id);
    } catch (error) {
      setStatus(errorText(error));
    }
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
  $("#preview-rsshub").addEventListener("click", async () => {
    try {
      $("#preview-rsshub").disabled = true;
      await previewRsshub();
    } catch (error) {
      $("#rsshub-status").textContent = errorText(error);
    } finally {
      $("#preview-rsshub").disabled = false;
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
  await Promise.all([loadSummary(), loadArticles(), loadFailures(), loadJobs(), loadSchedules(), loadSources()]);
  setStatus("Ready");
}

boot().catch((error) => setStatus(errorText(error)));
