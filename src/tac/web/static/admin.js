const csrf = document.querySelector('meta[name="tac-csrf"]').content;

const state = {
  page: Number(new URLSearchParams(location.search).get("page") || "1"),
  pageSize: 50,
  q: new URLSearchParams(location.search).get("q") || "",
  status: new URLSearchParams(location.search).get("status") || "",
  source: new URLSearchParams(location.search).get("source") || "",
  since: new URLSearchParams(location.search).get("since") || "",
  until: new URLSearchParams(location.search).get("until") || "",
  failedOnly: new URLSearchParams(location.search).get("failed_only") === "true",
  sourcesHash: "",
};

const $ = (selector) => document.querySelector(selector);

const STATUS_LABELS = {
  accepted: "已通过",
  active: "启用",
  candidate: "候选",
  disabled: "停用",
  evaluation_failed: "评估失败",
  failed: "失败",
  fetch_failed: "抓取失败",
  low_confidence: "低置信",
  pending: "待处理",
  queued: "排队中",
  rejected: "已拒绝",
  running: "运行中",
  skipped: "已跳过",
  skipped_out_of_range: "超出范围",
  succeeded: "成功",
};

const JOB_LABELS = {
  discover: "发现文章",
  evaluate: "评估文章",
  fetch: "抓取内容",
  publish: "发布数据",
  run: "运行全部",
  "retry-evaluate": "重试评估",
  "retry-fetch": "重试抓取",
};

const STAGE_LABELS = {
  evaluate: "评估",
  fetch: "抓取",
};

const TRIGGER_LABELS = {
  manual: "手动",
  schedule: "定时",
};

const DETAIL_FIELD_LABELS = {
  article_count: "文章数",
  article_id: "文章编号",
  article_title: "文章标题",
  authors: "作者",
  canonical_url: "规范链接",
  content_hash: "内容哈希",
  created_at: "创建时间",
  description: "说明",
  error: "错误",
  evaluate_queue_status: "评估队列状态",
  evaluation_error: "评估错误",
  evaluation_status: "评估状态",
  fetch_error: "抓取错误",
  fetch_queue_status: "抓取队列状态",
  fetch_status: "抓取状态",
  fetched_at: "抓取时间",
  id: "编号",
  job_id: "任务编号",
  kind: "任务类型",
  name: "名称",
  normalized_url: "规范化链接",
  published_at: "发布时间",
  reason: "原因",
  retry_count: "重试次数",
  schedule_id: "计划编号",
  score: "评分",
  slug: "短标识",
  source_content_markdown: "原文 Markdown",
  source_content_metadata: "原文元数据",
  source_name: "来源",
  status: "状态",
  suggested_tag: "建议 Tag",
  summary: "摘要",
  tags: "标签",
  title: "标题",
  trigger: "触发方式",
  updated_at: "更新时间",
  url: "链接",
};

function setStatus(text) {
  $("#runtime-status").textContent = text;
}

function labelFor(map, value) {
  if (value === null || value === undefined || value === "") return "-";
  return map[value] || value;
}

function statusLabel(value) {
  return labelFor(STATUS_LABELS, value);
}

function jobLabel(value) {
  return labelFor(JOB_LABELS, value);
}

function stageLabel(value) {
  return labelFor(STAGE_LABELS, value);
}

function triggerLabel(value) {
  return labelFor(TRIGGER_LABELS, value);
}

function detailValue(value, key = "") {
  if (Array.isArray(value)) {
    return value.map((item) => detailValue(item, key));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([itemKey, itemValue]) => [
        DETAIL_FIELD_LABELS[itemKey] || itemKey,
        detailValue(itemValue, itemKey),
      ]),
    );
  }
  if (key === "status" || key.endsWith("_status")) return statusLabel(value);
  if (key === "kind") return jobLabel(value);
  if (key === "stage") return stageLabel(value);
  if (key === "trigger") return triggerLabel(value);
  return value;
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
  if (state.since) params.set("since", state.since);
  if (state.until) params.set("until", state.until);
  if (state.failedOnly) params.set("failed_only", "true");
  history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
}

function errorText(error) {
  if (error.status === 403) return "写入请求被拒绝，请从同源 /admin 页面操作。";
  if (error.status === 409) return "存在冲突：任务正在运行，或文件已被其他操作修改。";
  if (error.status === 429) return "请求过多：已达到并发或队列上限。";
  return error.message || "请求失败";
}

async function loadSummary() {
  const summary = await api("/api/admin/summary");
  const labels = [
    ["total", "总数"],
    ["candidate", "候选"],
    ["accepted", "已通过"],
    ["rejected", "已拒绝"],
    ["low_confidence", "低置信"],
    ["skipped_out_of_range", "超出范围"],
    ["fetch_failed", "抓取失败"],
    ["evaluation_failed", "评估失败"],
  ];
  $("#summary-grid").innerHTML = labels
    .map(([key, label]) => `<div class="metric"><span>${label}</span><b>${summary[key] || 0}</b></div>`)
    .join("");
}

async function loadSourceNames() {
  const payload = await api("/api/admin/source-names");
  $("#source-filter").innerHTML =
    '<option value="">全部来源</option>' +
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
          <td><span class="tag ${statusClass}">${escapeHtml(statusLabel(item.status))}</span></td>
          <td>${escapeHtml(statusLabel(item.fetch_status || item.fetch_queue_status))}<br><span class="muted">${escapeHtml(item.fetch_error || "")}</span></td>
          <td>${escapeHtml(statusLabel(item.evaluation_status || item.evaluate_queue_status))}<br><span class="muted">${escapeHtml(item.evaluation_error || "")}</span></td>
          <td>${item.retry_count}</td>
          <td>${escapeHtml(item.published_at || "-")}</td>
          <td>${escapeHtml(item.updated_at)}</td>
          <td class="actions">
            <button data-action="retry-fetch" data-id="${item.id}">重抓</button>
            <button data-action="retry-evaluate" data-id="${item.id}">重评</button>
            <button data-action="status" data-status="candidate" data-id="${item.id}">候选</button>
            <button data-action="status" data-status="accepted" data-id="${item.id}">通过</button>
            <button data-action="status" data-status="rejected" data-id="${item.id}">拒绝</button>
            <button data-action="status" data-status="low_confidence" data-id="${item.id}">低置信</button>
            <button data-action="status" data-status="skipped_out_of_range" data-id="${item.id}">跳过</button>
          </td>
        </tr>`;
    })
    .join("");
  $("#page-label").textContent = `第 ${page.page} 页 / 共 ${page.total} 条`;
  $("#prev-page").disabled = page.page <= 1;
  $("#next-page").disabled = !page.has_next;
}

async function loadArticles() {
  updateUrl();
  const params = new URLSearchParams({
    page: String(state.page),
    page_size: String(state.pageSize),
    sort: "published_at",
    order: "desc",
  });
  if (state.q) params.set("q", state.q);
  if (state.status) params.set("status", state.status);
  if (state.source) params.set("source", state.source);
  if (state.since) params.set("since", state.since);
  if (state.until) params.set("until", state.until);
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
            <b>${escapeHtml(stageLabel(item.stage))}</b> #${item.article_id} ${escapeHtml(item.title)}<br>
            ${escapeHtml(item.error || "")}<br>
            <button data-action="${item.stage === "fetch" ? "retry-fetch" : "retry-evaluate"}" data-id="${item.article_id}">重试</button>
          </div>`,
      )
      .join("") || '<p class="muted">暂无失败记录</p>';
}

async function loadTags() {
  const [tags, candidates] = await Promise.all([
    api("/api/admin/tags?limit=200"),
    api("/api/admin/tag-candidates?status=pending&limit=50"),
  ]);
  $("#tag-candidates-list").innerHTML =
    candidates.items
      .map(
        (item) => `
          <div class="list-item">
            <b>${escapeHtml(item.suggested_tag)}</b> <span class="muted">候选 #${item.id}</span><br>
            文章：${escapeHtml(item.article_title)}<br>
            <span class="muted">${escapeHtml(item.reason || "")}</span><br>
            <button data-tag-candidate-action="approve" data-id="${item.id}">通过</button>
            <button data-tag-candidate-action="reject" data-id="${item.id}">拒绝</button>
          </div>`,
      )
      .join("") || '<p class="muted">暂无待审核 Tag 候选</p>';
  $("#tags-list").innerHTML =
    tags.items
      .map(
        (tag) => `
          <div class="list-item">
            <b>${escapeHtml(tag.name)}</b> <span class="tag ${escapeHtml(tag.status)}">${escapeHtml(statusLabel(tag.status))}</span>
            <span class="muted">${tag.article_count || 0} 篇文章</span><br>
            ${escapeHtml(tag.description || "")}<br>
            <button data-tag-status="${tag.status === "active" ? "disabled" : "active"}" data-id="${tag.id}">
              ${tag.status === "active" ? "停用" : "启用"}
            </button>
          </div>`,
      )
      .join("") || '<p class="muted">暂无词库 Tag</p>';
}

async function createTag() {
  const name = $("#tag-name").value.trim();
  if (!name) {
    $("#tags-status").textContent = "Tag 名称不能为空";
    return;
  }
  await api("/api/admin/tags", {
    method: "POST",
    body: JSON.stringify({
      name,
      description: $("#tag-description").value.trim(),
      status: "active",
    }),
  });
  $("#tag-name").value = "";
  $("#tag-description").value = "";
  $("#tags-status").textContent = "Tag 已新增";
  await loadTags();
}

async function loadJobs() {
  const payload = await api("/api/admin/jobs");
  $("#jobs-list").innerHTML =
    payload.items
      .slice(0, 8)
      .map(
        (job) =>
          `<div class="list-item">
            <b>${escapeHtml(jobLabel(job.kind))}</b> ${escapeHtml(statusLabel(job.status))} ${escapeHtml(triggerLabel(job.trigger || "manual"))}
            ${job.schedule_id ? `/${escapeHtml(job.schedule_id)}` : ""}<br>
            <span class="muted">${escapeHtml(job.started_at || job.created_at)}${job.finished_at ? ` 至 ${escapeHtml(job.finished_at)}` : ""}</span><br>
            ${escapeHtml(job.error || JSON.stringify(job.result || ""))}
          </div>`,
      )
      .join("") || '<p class="muted">暂无任务</p>';
}

async function loadSchedules() {
  const payload = await api("/api/admin/schedules");
  $("#schedules-list").innerHTML =
    payload.items
      .map(
        (schedule) => `
          <div class="list-item">
            <b>${escapeHtml(schedule.schedule_id)}</b> ${escapeHtml(jobLabel(schedule.kind))}
            ${schedule.enabled ? "启用" : "停用"}<br>
            <span class="muted">${escapeHtml(schedule.cron)} ${escapeHtml(schedule.timezone)} 下次 ${escapeHtml(schedule.next_run_at || "-")}</span><br>
            ${schedule.latest_job ? `最近 ${escapeHtml(statusLabel(schedule.latest_job.status))} ${escapeHtml(schedule.latest_job.finished_at || schedule.latest_job.created_at)}` : "暂无运行记录"}<br>
            <button data-schedule-trigger="${escapeHtml(schedule.schedule_id)}">立即触发</button>
          </div>`,
      )
      .join("") || '<p class="muted">暂无定时计划</p>';
}

async function submitJob(kind) {
  const params = new URLSearchParams();
  if (["discover", "run"].includes(kind)) {
    if (state.since) params.set("since", state.since);
    if (state.until) params.set("until", state.until);
  }
  const suffix = params.toString() ? `?${params}` : "";
  const job = await api(`/api/admin/jobs/${kind}${suffix}`, { method: "POST" });
  setStatus(`任务已提交：${job.job_id}`);
  await pollJob(job.job_id);
}

async function pollJob(jobId) {
  const timer = setInterval(async () => {
    try {
      const job = await api(`/api/admin/jobs/${jobId}`);
      setStatus(`${jobLabel(job.kind)}：${statusLabel(job.status)}`);
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
  $("#sources-status").textContent = "已保存";
}

async function previewRsshub() {
  const paramsText = $("#rsshub-params").value.trim() || "{}";
  let params;
  try {
    params = JSON.parse(paramsText);
  } catch (error) {
    $("#rsshub-status").textContent = "参数 JSON 无效";
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
            ${entry.published_at ? `<br><span class="muted">${escapeHtml(entry.published_at)}</span>` : ""}
          </div>`,
      )
      .join("") || '<p class="muted">暂无条目</p>';
}

async function previewSitemap() {
  const payload = await api("/api/admin/sources/preview-sitemap", {
    method: "POST",
    body: JSON.stringify({
      url: $("#sitemap-url").value.trim(),
      limit: Number($("#sitemap-limit").value || "10"),
    }),
  });
  $("#sitemap-status").textContent = payload.feed_url;
  $("#sitemap-preview-list").innerHTML =
    payload.entries
      .map(
        (entry) => `
          <div class="list-item">
            <b>${escapeHtml(entry.title)}</b><br>
            <a href="${escapeHtml(entry.url)}" target="_blank" rel="noreferrer">${escapeHtml(entry.url)}</a>
            ${entry.published_at ? `<br><span class="muted">${escapeHtml(entry.published_at)}</span>` : ""}
          </div>`,
      )
      .join("") || '<p class="muted">暂无条目</p>';
}

async function previewListing() {
  const patternsText = $("#listing-url-patterns").value.trim();
  const url_patterns = patternsText
    ? patternsText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
    : [];
  const payload = await api("/api/admin/sources/preview-listing", {
    method: "POST",
    body: JSON.stringify({
      url: $("#listing-url").value.trim(),
      link_selector: $("#listing-link-selector").value.trim(),
      title_selector: $("#listing-title-selector").value.trim() || null,
      base_url: $("#listing-base-url").value.trim() || null,
      url_patterns,
      limit: Number($("#listing-limit").value || "10"),
    }),
  });
  $("#listing-status").textContent = payload.feed_url;
  $("#listing-preview-list").innerHTML =
    payload.entries
      .map(
        (entry) => `
          <div class="list-item">
            <b>${escapeHtml(entry.title)}</b><br>
            <a href="${escapeHtml(entry.url)}" target="_blank" rel="noreferrer">${escapeHtml(entry.url)}</a>
            ${entry.published_at ? `<br><span class="muted">${escapeHtml(entry.published_at)}</span>` : ""}
          </div>`,
      )
      .join("") || '<p class="muted">暂无条目</p>';
}

async function showDetail(id) {
  const detail = await api(`/api/admin/articles/${id}`);
  $("#detail-content").textContent = JSON.stringify(detailValue(detail), null, 2);
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
    setStatus(`任务已提交：${job.job_id}`);
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
  $("#discover-since").value = state.since;
  $("#discover-until").value = state.until;
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
  $("#discover-since").addEventListener("change", (event) => {
    state.since = event.target.value;
    state.page = 1;
    loadArticles().catch((error) => setStatus(errorText(error)));
  });
  $("#discover-until").addEventListener("change", (event) => {
    state.until = event.target.value;
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
      setStatus(`计划任务已提交：${job.job_id}`);
      await pollJob(job.job_id);
    } catch (error) {
      setStatus(errorText(error));
    }
  });
  $("#refresh-failures").addEventListener("click", () => {
    loadFailures().catch((error) => setStatus(errorText(error)));
  });
  $("#refresh-tags").addEventListener("click", () => {
    loadTags().catch((error) => {
      $("#tags-status").textContent = errorText(error);
    });
  });
  $("#create-tag").addEventListener("click", async () => {
    try {
      await createTag();
    } catch (error) {
      $("#tags-status").textContent = errorText(error);
    }
  });
  $("#tag-candidates-list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-tag-candidate-action]");
    if (!button) return;
    try {
      await api(`/api/admin/tag-candidates/${button.dataset.id}/${button.dataset.tagCandidateAction}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await loadTags();
      await loadArticles();
    } catch (error) {
      $("#tags-status").textContent = errorText(error);
    }
  });
  $("#tags-list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-tag-status]");
    if (!button) return;
    try {
      await api(`/api/admin/tags/${button.dataset.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: button.dataset.tagStatus }),
      });
      await loadTags();
    } catch (error) {
      $("#tags-status").textContent = errorText(error);
    }
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
  $("#preview-sitemap").addEventListener("click", async () => {
    try {
      $("#preview-sitemap").disabled = true;
      await previewSitemap();
    } catch (error) {
      $("#sitemap-status").textContent = errorText(error);
    } finally {
      $("#preview-sitemap").disabled = false;
    }
  });
  $("#preview-listing").addEventListener("click", async () => {
    try {
      $("#preview-listing").disabled = true;
      await previewListing();
    } catch (error) {
      $("#listing-status").textContent = errorText(error);
    } finally {
      $("#preview-listing").disabled = false;
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
  await Promise.all([loadSummary(), loadArticles(), loadFailures(), loadTags(), loadJobs(), loadSchedules(), loadSources()]);
  setStatus("就绪");
}

boot().catch((error) => setStatus(errorText(error)));
