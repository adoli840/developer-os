const state = {
  authenticated: false,
  publicReadOnly: false,
  trustedLocal: false,
  csrfToken: "",
  overview: null,
  roadmaps: null,
  activeRoadmap: "",
  activeRoadmapTrack: "overall",
  activeResourceMetric: "",
  pendingAction: null,
  refreshTimer: null,
};

const elements = {
  loginShell: document.querySelector("#login-shell"),
  loginForm: document.querySelector("#login-form"),
  loginError: document.querySelector("#login-error"),
  accessToken: document.querySelector("#access-token"),
  appShell: document.querySelector("#app-shell"),
  modeBadge: document.querySelector("#mode-badge"),
  syncState: document.querySelector("#sync-state"),
  refreshButton: document.querySelector("#refresh-button"),
  logoutButton: document.querySelector("#logout-button"),
  serverMetrics: document.querySelector("#server-metrics"),
  overviewTime: document.querySelector("#overview-time"),
  alertSummary: document.querySelector("#alert-summary"),
  workstationSummary: document.querySelector("#workstation-summary"),
  dockerSummary: document.querySelector("#docker-summary"),
  activitySummary: document.querySelector("#activity-summary"),
  workstationDetail: document.querySelector("#workstation-detail"),
  roadmapTime: document.querySelector("#roadmap-time"),
  roadmapSummary: document.querySelector("#roadmap-summary"),
  roadmapTabs: document.querySelector("#roadmap-tabs"),
  roadmapTrackTabs: document.querySelector("#roadmap-track-tabs"),
  roadmapDetail: document.querySelector("#roadmap-detail"),
  backupSummary: document.querySelector("#backup-summary"),
  timerSummary: document.querySelector("#timer-summary"),
  deploymentList: document.querySelector("#deployment-list"),
  closeoutList: document.querySelector("#closeout-list"),
  commandList: document.querySelector("#command-list"),
  commandNotice: document.querySelector("#command-notice"),
  usagePanel: document.querySelector("#usage-panel"),
  actionDialog: document.querySelector("#action-dialog"),
  dialogTitle: document.querySelector("#dialog-title"),
  dialogDescription: document.querySelector("#dialog-description"),
  dialogCommand: document.querySelector("#dialog-command"),
  dialogConfirm: document.querySelector("#dialog-confirm"),
  outputDialog: document.querySelector("#output-dialog"),
  outputTitle: document.querySelector("#output-title"),
  outputContent: document.querySelector("#output-content"),
  toast: document.querySelector("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatBytes(value) {
  if (!Number.isFinite(value)) return "Unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index > 2 ? 1 : 0)} ${units[index]}`;
}

function formatMoney(value, currency = "USD") {
  if (!Number.isFinite(value)) return "Unavailable";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: String(currency || "USD").toUpperCase(),
      maximumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return `${Number(value).toFixed(2)} ${String(currency || "USD").toUpperCase()}`;
  }
}

function formatQuantity(value, unit) {
  if (!Number.isFinite(value)) return "Unavailable";
  const amount = Number(value);
  return `${amount.toLocaleString(undefined, {maximumFractionDigits: 2})} ${unit || ""}`.trim();
}

function formatDate(value) {
  if (!value) return "Unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function shortRevision(value) {
  const revision = String(value || "");
  return revision ? revision.slice(0, 7) : "-";
}

function shortRevisions(values) {
  return Array.isArray(values) && values.length
    ? values.map((value) => shortRevision(value)).join(", ")
    : "-";
}

function statusBadge(label, kind) {
  return `<span class="status ${kind}">${escapeHtml(label)}</span>`;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  window.setTimeout(() => elements.toast.classList.remove("visible"), 2800);
}

async function request(path, options = {}) {
  const headers = {"Content-Type": "application/json", ...(options.headers || {})};
  if (state.csrfToken && options.method && options.method !== "GET") {
    headers["X-CSRF-Token"] = state.csrfToken;
  }
  const response = await fetch(path, {...options, headers});
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {error: `Unexpected response (${response.status})`};
  }
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

async function initialize() {
  selectPrimaryTab(tabFromPath(), false);
  try {
    const session = await request("/api/session");
    state.authenticated = Boolean(session.authenticated);
    state.publicReadOnly = Boolean(session.public_read_only);
    state.trustedLocal = Boolean(session.trusted_local);
    state.csrfToken = session.csrf_token || "";
    showApplication();
    await refreshOverview();
  } catch {
    showLogin();
  }
}

function showLogin() {
  elements.loginShell.hidden = false;
  elements.appShell.hidden = true;
  elements.accessToken.focus();
}

function showApplication() {
  elements.loginShell.hidden = true;
  elements.appShell.hidden = false;
  elements.logoutButton.hidden = !state.authenticated || state.trustedLocal;
  if (state.publicReadOnly) {
    elements.modeBadge.textContent = "Public read-only";
    elements.modeBadge.classList.add("read-only");
  } else {
    elements.modeBadge.textContent = state.trustedLocal ? "Local" : "Secure session";
    elements.modeBadge.classList.remove("read-only");
  }
}

async function refreshOverview() {
  elements.syncState.textContent = "Refreshing";
  elements.refreshButton.disabled = true;
  try {
    [state.overview, state.roadmaps] = await Promise.all([
      request("/api/overview"),
      request("/api/roadmaps"),
    ]);
    render();
    elements.syncState.textContent = "Live";
  } catch (error) {
    elements.syncState.textContent = "Refresh failed";
    showToast(error.message);
  } finally {
    elements.refreshButton.disabled = false;
  }
}

function render() {
  if (!state.overview) return;
  renderMetrics(state.overview.system);
  renderAlerts(state.overview.alerts || []);
  renderWorkstations(state.overview.workstations || []);
  renderDocker(state.overview.system.docker);
  renderActivity(state.overview.audit);
  renderRoadmaps(state.roadmaps);
  renderOperations(state.overview.projects, state.overview.backups);
  renderCommands(state.overview.projects);
  renderUsage(state.overview.usage);
  const collectedAt = state.overview.system.collected_at;
  elements.overviewTime.textContent = collectedAt
    ? `Collected ${new Date(collectedAt * 1000).toLocaleString()}`
    : "Collection time unavailable";
}

function roadmapStatusKind(status) {
  if (status === "Done") return "good";
  if (status === "Blocked" || status === "Cancelled") return "bad";
  if (status === "Paused") return "warn";
  return "neutral";
}

function roadmapStatusClass(status) {
  return {
    "Done": "done",
    "In Progress": "in-progress",
    "Planned": "planned",
    "Blocked": "blocked",
    "Paused": "paused",
    "Cancelled": "cancelled",
  }[status] || "planned";
}

function roadmapLegend() {
  return [
    ["Done", "done"],
    ["In progress", "in-progress"],
    ["Planned", "planned"],
    ["Blocked", "blocked"],
    ["Paused", "paused"],
    ["Cancelled", "cancelled"],
  ].map(([label, kind]) => `
    <span class="roadmap-legend-item">
      <i class="roadmap-status-swatch ${kind}" aria-hidden="true"></i>
      ${escapeHtml(label)}
    </span>
  `).join("");
}

function renderRoadmaps(roadmaps) {
  if (!roadmaps) return;
  const summary = roadmaps.summary || {};
  elements.roadmapSummary.innerHTML = [
    {label: "Projects", value: summary.total || 0},
    {label: "Available", value: summary.available || 0},
    {label: "Missing", value: summary.missing || 0},
    {label: "Invalid", value: summary.invalid || 0},
  ].map((item) => `
    <div class="roadmap-summary-item">
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
    </div>
  `).join("");

  const projects = roadmaps.projects || [];
  if (!projects.some((project) => project.slug === state.activeRoadmap)) {
    state.activeRoadmap = projects.find((project) => project.slug === "developer-os")?.slug
      || projects[0]?.slug
      || "";
  }
  elements.roadmapTabs.innerHTML = projects.map((project) => {
    const active = project.slug === state.activeRoadmap;
    return `<button class="roadmap-tab${active ? " active" : ""}" data-roadmap="${escapeHtml(project.slug)}" role="tab" aria-selected="${active}" type="button">${escapeHtml(project.name)}</button>`;
  }).join("");
  elements.roadmapTabs.querySelectorAll("button[data-roadmap]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeRoadmap = button.dataset.roadmap;
      state.activeRoadmapTrack = "overall";
      renderRoadmaps(state.roadmaps);
    });
  });

  const activeProject = projects.find((project) => project.slug === state.activeRoadmap);
  renderRoadmapTracks(activeProject);
  elements.roadmapTime.textContent = roadmaps.generated_at
    ? `Collected ${new Date(roadmaps.generated_at).toLocaleString()}`
    : "Collection time unavailable";
}

function renderRoadmapTracks(project) {
  const tracks = project?.state === "available" ? (project.tracks || []) : [];
  if (!tracks.length) {
    state.activeRoadmapTrack = "overall";
    elements.roadmapTrackTabs.hidden = true;
    elements.roadmapTrackTabs.innerHTML = "";
    renderRoadmapDetail(project);
    return;
  }

  const choices = [{slug: "overall", name: "Overall", roadmap: project}]
    .concat(tracks.map((track) => ({slug: track.slug, name: track.name, roadmap: track})));
  if (!choices.some((choice) => choice.slug === state.activeRoadmapTrack)) {
    state.activeRoadmapTrack = "overall";
  }
  elements.roadmapTrackTabs.hidden = false;
  elements.roadmapTrackTabs.innerHTML = choices.map((choice) => {
    const active = choice.slug === state.activeRoadmapTrack;
    return `<button class="roadmap-track-tab${active ? " active" : ""}" data-roadmap-track="${escapeHtml(choice.slug)}" role="tab" aria-selected="${active}" type="button">${escapeHtml(choice.name)}</button>`;
  }).join("");
  elements.roadmapTrackTabs.querySelectorAll("button[data-roadmap-track]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeRoadmapTrack = button.dataset.roadmapTrack;
      renderRoadmapTracks(project);
    });
  });
  const active = choices.find((choice) => choice.slug === state.activeRoadmapTrack);
  renderRoadmapDetail(active?.roadmap || project);
}

function renderRoadmapDetail(project) {
  if (!project) {
    elements.roadmapDetail.innerHTML = `<section class="roadmap-empty"><h2>No projects configured</h2></section>`;
    return;
  }
  if (project.state !== "available") {
    const label = project.state === "missing" ? "Not available" : "Format mismatch";
    const kind = project.state === "missing" ? "warn" : "bad";
    elements.roadmapDetail.innerHTML = `
      <section class="roadmap-empty">
        <div>
          <p class="eyebrow">${escapeHtml(project.name)}</p>
          <h2>Standard roadmap view unavailable</h2>
          <p class="muted">${escapeHtml(project.message)}</p>
        </div>
        ${statusBadge(label, kind)}
      </section>
    `;
    return;
  }

  const milestone = project.milestone || {};
  const latest = project.latest_status_change || {};
  const topics = project.topics || [];
  elements.roadmapDetail.innerHTML = `
    <section class="roadmap-hero">
      <div class="roadmap-title-block">
        <p class="eyebrow">UPDATED ${escapeHtml(project.updated_at)}</p>
        <h2>${escapeHtml(project.title)}</h2>
        <p>${escapeHtml(project.direction)}</p>
      </div>
      <aside class="roadmap-legend" aria-label="Roadmap status legend">
        <h3>Detail status</h3>
        <div class="roadmap-legend-grid">${roadmapLegend()}</div>
      </aside>
    </section>

    <section class="roadmap-milestone-strip">
      <div>
        <span>Current milestone</span>
        <strong>${escapeHtml(milestone.objective)}</strong>
      </div>
      <div>
        <span>Status</span>
        ${statusBadge(milestone.status, roadmapStatusKind(milestone.status))}
      </div>
      <div>
        <span>Completion signal</span>
        <strong>${escapeHtml(milestone.completion_signal)}</strong>
      </div>
    </section>

    <section class="roadmap-stage-section">
      <div class="roadmap-band-heading">
        <h3>Roadmap stages</h3>
        <span>${escapeHtml(topics.length)} stages</span>
      </div>
      <div class="roadmap-stage-scroll">
        <div class="roadmap-stage-track" role="list">
          ${topics.map((topic, index) => {
            const statusClass = roadmapStatusClass(topic.status);
            return `
              <article class="roadmap-stage ${statusClass}" role="listitem">
                <div class="roadmap-stage-card">
                  <span class="roadmap-stage-number" aria-hidden="true">${index + 1}</span>
                  <h4>${escapeHtml(topic.topic)}</h4>
                  <span class="roadmap-stage-status">${escapeHtml(topic.status)}</span>
                </div>
                <div class="roadmap-stage-facts">
                  <div>
                    <span>Completion</span>
                    <p>${escapeHtml(topic.completion_signal)}</p>
                  </div>
                  <div>
                    <span>Next</span>
                    <p>${escapeHtml(topic.next_transition)}</p>
                  </div>
                </div>
              </article>
            `;
          }).join("")}
        </div>
      </div>
    </section>

    <div class="roadmap-columns">
      <section class="roadmap-band">
        <h3>Current priority</h3>
        ${roadmapOrderedList(project.current_priority)}
      </section>
      <section class="roadmap-band">
        <h3>Latest status change</h3>
        <dl class="roadmap-change">
          <div><dt>Topic</dt><dd>${escapeHtml(latest.topic)}</dd></div>
          <div><dt>Change</dt><dd>${escapeHtml(latest.change)}</dd></div>
          <div><dt>Evidence</dt><dd>${escapeHtml(latest.evidence_or_reason)}</dd></div>
        </dl>
      </section>
    </div>

    <div class="roadmap-columns">
      <section class="roadmap-band">
        <h3>Next status transitions</h3>
        ${roadmapOrderedList(project.next_status_transitions)}
      </section>
      <section class="roadmap-band">
        <h3>Risks and blockers</h3>
        ${roadmapBulletList(project.risks_and_blockers)}
      </section>
    </div>
  `;
}

function roadmapOrderedList(items) {
  return `<ol class="roadmap-list">${(items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>`;
}

function roadmapBulletList(items) {
  return `<ul class="roadmap-list">${(items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function tabFromPath() {
  return window.location.pathname.replace(/\/$/, "") === "/roadmap" ? "roadmap" : "overview";
}

function selectPrimaryTab(tab, updateHistory = true) {
  const button = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (!button) return;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".tab-view").forEach((view) => view.classList.toggle("active", view.id === `tab-${tab}`));
  if (updateHistory) {
    const nextPath = tab === "roadmap" ? "/roadmap" : "/";
    if (window.location.pathname !== nextPath) window.history.pushState({tab}, "", nextPath);
  }
}

function renderMetrics(system) {
  const metrics = [
    {key: "cpu", label: "CPU", value: Number.isFinite(system.cpu_percent) ? `${system.cpu_percent}%` : `${system.cpu_count || "-"} cores`, percent: system.cpu_percent || 0},
    {key: "memory", label: "Memory", value: formatBytes(system.memory.used), detail: `of ${formatBytes(system.memory.total)}`, percent: system.memory.percent || 0},
    {key: "disk", label: "Root disk", value: formatBytes(system.disk.used), detail: `${formatBytes(system.disk.free)} free`, percent: system.disk.percent || 0},
  ];
  const activeMetric = metrics.find((metric) => metric.key === state.activeResourceMetric);
  elements.serverMetrics.innerHTML = `
    ${metrics.map((metric) => `
      <button class="metric${activeMetric?.key === metric.key ? " active" : ""}" type="button" data-metric="${escapeHtml(metric.key)}" aria-expanded="${activeMetric?.key === metric.key}">
        <span class="metric-label">${escapeHtml(metric.label)}</span>
        <strong class="metric-value">${escapeHtml(metric.value)}</strong>
        <span class="cell-detail">${escapeHtml(metric.detail || "")}</span>
        <progress class="meter" max="100" value="${Math.max(0, Math.min(100, metric.percent))}">${metric.percent}%</progress>
      </button>
    `).join("")}
    ${activeMetric ? resourceBreakdown(activeMetric.key, system.resources?.[activeMetric.key] || []) : ""}
  `;
  elements.serverMetrics.querySelectorAll("button[data-metric]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeResourceMetric = state.activeResourceMetric === button.dataset.metric
        ? ""
        : button.dataset.metric;
      renderMetrics(system);
    });
  });
}

function resourceBreakdown(metric, rows) {
  if (!rows.length) return `<p class="resource-empty">Usage breakdown unavailable.</p>`;
  const formatValue = (value) => metric === "cpu" ? `${Number(value).toFixed(1)}%` : formatBytes(value);
  return `
    <div class="resource-breakdown">
      ${rows.map((row) => `
        <div class="resource-row">
          <div class="resource-row-heading"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(formatValue(row.value))}</span></div>
          <p>${(row.components || []).map((component) => `${escapeHtml(component.name)} ${escapeHtml(formatValue(component.value))}`).join(" / ")}</p>
        </div>
      `).join("")}
    </div>
  `;
}

function repositoryStatus(project) {
  if (!project.available) return statusBadge("Missing", "bad");
  if (!project.repository) return statusBadge("Not Git", "neutral");
  const repo = project.repository;
  if (repo.modified > 0) return statusBadge(`${repo.modified} modified`, "warn");
  if (repo.behind > 0) return statusBadge(`${repo.behind} behind`, "warn");
  if (repo.ahead > 0) return statusBadge(`${repo.ahead} ahead`, "neutral");
  return statusBadge("Clean", "good");
}

function deploymentStatus(project) {
  const status = project.deployment?.status;
  if (status === "current") return statusBadge("Current", "good");
  if (status === "out_of_sync") return statusBadge("Out of sync", "warn");
  if (status === "running") return statusBadge("Running", "neutral");
  if (status === "not_deployed") return statusBadge("Not deployed", "neutral");
  return statusBadge("Unknown", "neutral");
}

function renderAlerts(alerts) {
  const critical = alerts.filter((item) => item.severity === "critical").length;
  const warning = alerts.filter((item) => item.severity === "warning").length;
  const headingBadge = critical
    ? statusBadge(`${critical} critical`, "bad")
    : warning
      ? statusBadge(`${warning} warnings`, "warn")
      : statusBadge("No action required", "good");
  elements.alertSummary.innerHTML = `
    <div class="surface-heading"><div><h2>Actionable alerts</h2><p>Only conditions that affect delivery or recovery.</p></div>${headingBadge}</div>
    <div class="alert-list">
      ${alerts.length ? alerts.map((item) => `
        <div class="alert-item ${escapeHtml(item.severity)}">
          <span>${escapeHtml(item.source)}</span>
          <strong>${escapeHtml(item.message)}</strong>
        </div>
      `).join("") : `<p class="muted">No operational alerts.</p>`}
    </div>
  `;
}

function workstationStatus(workstation) {
  if (workstation.status === "online") return statusBadge("Online", "good");
  if (workstation.status === "offline") return statusBadge("Offline", "neutral");
  if (workstation.status === "never_reported") return statusBadge("Not connected", "warn");
  return statusBadge("Invalid report", "bad");
}

function renderWorkstations(workstations) {
  const home = workstations.find((item) => item.id === "home");
  if (!home) {
    elements.workstationSummary.innerHTML = `
      <div class="surface-heading"><div><h2>Home computer</h2><p>No Home workstation is configured.</p></div>${statusBadge("Not configured", "neutral")}</div>
    `;
    elements.workstationDetail.innerHTML = "";
    return;
  }
  const lastReport = formatDate(home.last_report_at);
  elements.workstationSummary.innerHTML = `
    <div class="surface-heading">
      <div><h2>Home computer</h2><p>Local Git state reported while the computer is powered on.</p></div>
      ${workstationStatus(home)}
    </div>
    <div class="workstation-stats">
      <div><span>Last report</span><strong>${escapeHtml(lastReport)}</strong></div>
      <div><span>Repositories</span><strong>${escapeHtml(home.summary.available)}</strong></div>
      <div><span>Dirty</span><strong>${escapeHtml(home.summary.dirty)}</strong></div>
      <div><span>Not pushed</span><strong>${escapeHtml(home.summary.ahead)}</strong></div>
      <div><span>Mismatches</span><strong>${escapeHtml(home.summary.mismatches || 0)}</strong></div>
    </div>
  `;

  elements.workstationDetail.innerHTML = `
    <div class="surface-heading">
      <div><h2>Home repositories</h2><p>${home.online ? "Live local state." : `Last known state from ${lastReport}.`}</p></div>
      ${workstationStatus(home)}
    </div>
    <div class="table-wrap">
      <table class="project-comparison-table">
        <thead><tr><th>Project</th><th>Local</th><th>GitHub</th><th>Server</th><th>Service</th><th>Port</th><th>Terminal</th></tr></thead>
        <tbody>
          ${home.projects.length ? home.projects.map((project) => `
            <tr>
              <td><strong>${escapeHtml(project.name)}</strong><div class="mobile-terminal">${terminalLink(project)}</div></td>
              <td>${repositoryStatus(project)}<div class="cell-detail">${escapeHtml(shortRevision(project.repository?.revision))}</div></td>
              <td>${githubStatus(project.repository)}<div class="cell-detail">${escapeHtml(project.repository?.remote_revision ? shortRevision(project.repository.remote_revision) : project.repository?.upstream || "-")}</div></td>
              <td>${comparisonStatus(project.comparison?.runtime_status)}<div class="cell-detail">${escapeHtml(shortRevisions(project.comparison?.deployed_revisions))}</div></td>
              <td>${serviceStatus(project.comparison?.service_status)}</td>
              <td><strong>${project.port ? escapeHtml(project.port) : "-"}</strong></td>
              <td class="terminal-cell">${terminalLink(project)}</td>
            </tr>
          `).join("") : `<tr><td colspan="7" class="muted">No Home report has been received yet.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function githubStatus(repository) {
  if (!repository?.upstream) return statusBadge("Unavailable", "neutral");
  if (repository.ahead > 0 && repository.behind > 0) return statusBadge("Diverged", "bad");
  if (repository.ahead > 0) return statusBadge("Push needed", "warn");
  if (repository.behind > 0) return statusBadge("Pull needed", "warn");
  return statusBadge("Match", "good");
}

function serviceStatus(status) {
  if (status === "healthy") return statusBadge("Healthy", "good");
  if (status === "degraded") return statusBadge("Degraded", "warn");
  if (status === "stopped") return statusBadge("Stopped", "bad");
  return statusBadge("Unavailable", "neutral");
}

function terminalLink(project) {
  const terminalProjects = new Set(["developer-os", "oa", "gaia", "btest"]);
  if (!project.available || !terminalProjects.has(project.slug)) {
    return `<span class="terminal-unavailable">Unavailable</span>`;
  }
  return `<a class="terminal-link" href="http://127.0.0.1:8092/?project=${encodeURIComponent(project.slug)}" target="_blank" rel="noopener">Terminal</a>`;
}

function comparisonStatus(status) {
  if (status === "match") return statusBadge("Match", "good");
  if (status === "mismatch") return statusBadge("Mismatch", "bad");
  return statusBadge("Unavailable", "neutral");
}

function renderDocker(docker) {
  elements.dockerSummary.innerHTML = `
    <div class="surface-heading"><div><h2>Docker engine</h2><p>Host container runtime.</p></div>${docker.available ? statusBadge("Available", "good") : statusBadge("Unavailable", "bad")}</div>
    <div class="summary-body">
      <dl class="summary-list">
        <dt>Version</dt><dd>${escapeHtml(docker.version || "-")}</dd>
        <dt>Containers</dt><dd>${escapeHtml(docker.containers ?? "-")}</dd>
        <dt>Running</dt><dd>${escapeHtml(docker.running ?? "-")}</dd>
        <dt>Unhealthy</dt><dd>${escapeHtml(docker.unhealthy ?? "-")}</dd>
      </dl>
    </div>
  `;
}

function renderActivity(audit) {
  const recent = audit.slice(0, 5);
  elements.activitySummary.innerHTML = `
    <div class="surface-heading"><div><h2>Recent activity</h2><p>Allowlisted console operations.</p></div></div>
    <div class="summary-body">
      ${recent.length ? `<dl class="summary-list">${recent.map((item) => `<dt>${escapeHtml(item.event)}</dt><dd>${escapeHtml(item.project || new Date(item.at).toLocaleTimeString())}</dd>`).join("")}</dl>` : `<p class="muted">${state.publicReadOnly ? "Hidden on the public endpoint." : "No recorded operations."}</p>`}
    </div>
  `;
}

function backupStatus(backup) {
  if (backup.status === "healthy" && backup.verification_status === "passed") return statusBadge("Protected", "good");
  if (backup.status === "failed") return statusBadge("Backup failed", "bad");
  if (backup.status === "stale") return statusBadge("Backup stale", "warn");
  return statusBadge("Needs verification", "warn");
}

function renderOperations(projects, backups) {
  const backupItems = backups?.items || [];
  elements.backupSummary.innerHTML = `
    <div class="surface-heading"><div><h2>Database protection</h2><p>Daily dumps with isolated restore verification.</p></div></div>
    <div class="backup-list">
      ${backupItems.length ? backupItems.map((backup) => `
        <div class="backup-row">
          <div><strong>${escapeHtml(backup.name)}</strong><span>${escapeHtml(backup.message)}</span></div>
          <div>${backupStatus(backup)}<span>${formatBytes(backup.size_bytes)}</span></div>
          <dl>
            <dt>Backup</dt><dd>${escapeHtml(formatDate(backup.last_success_at))}</dd>
            <dt>Restore test</dt><dd>${escapeHtml(formatDate(backup.last_verification_at))}</dd>
            <dt>Policy</dt><dd>${escapeHtml(!backup.backup_policy ? "Pending first backup" : backup.backup_policy === "multi-container-excluding-market.klines-data" ? "All DBs except Kline rows" : "Full database")}</dd>
          </dl>
        </div>
      `).join("") : `<p class="muted">No databases are configured for managed backups.</p>`}
    </div>
  `;

  const backupTimer = backups?.backup_timer || {};
  const verifyTimer = backups?.verification_timer || {};
  elements.timerSummary.innerHTML = `
    <div class="surface-heading"><div><h2>Automation schedule</h2><p>Persistent systemd timers on the Oracle host.</p></div></div>
    <div class="summary-body">
      <dl class="summary-list">
        <dt>Daily backup</dt><dd>${backupTimer.active ? "Active" : "Unavailable"}</dd>
        <dt>Next backup</dt><dd>${escapeHtml(backupTimer.next || "-")}</dd>
        <dt>Weekly restore test</dt><dd>${verifyTimer.active ? "Active" : "Unavailable"}</dd>
        <dt>Next restore test</dt><dd>${escapeHtml(verifyTimer.next || "-")}</dd>
      </dl>
    </div>
  `;

  elements.deploymentList.innerHTML = projects.map((project) => {
    const deployment = project.deployment || {};
    const image = deployment.images?.[0];
    return `
      <tr>
        <td><strong>${escapeHtml(project.name)}</strong><div>${deploymentStatus(project)}</div></td>
        <td>${escapeHtml(project.repository?.revision || "-")}</td>
        <td>${escapeHtml(deployment.deployed_revisions?.join(", ") || "-")}</td>
        <td><strong>${escapeHtml(image?.name || deployment.mode || "-")}</strong><div class="cell-detail">${escapeHtml(image?.id || "")}</div></td>
        <td>${escapeHtml(formatDate(deployment.deployed_at))}</td>
      </tr>
    `;
  }).join("");

  elements.closeoutList.innerHTML = projects.map((project) => `
    <article class="closeout-row">
      <div><h3>${escapeHtml(project.name)}</h3>${project.work_end?.ready ? statusBadge("Ready", "good") : statusBadge(`${project.work_end?.blocking || 0} items`, "warn")}</div>
      <div class="check-list">
        ${(project.work_end?.checks || []).map((check) => `<span class="check ${escapeHtml(check.status)}">${escapeHtml(check.label)}</span>`).join("")}
      </div>
    </article>
  `).join("");
}

function renderCommands(projects) {
  elements.commandNotice.textContent = state.publicReadOnly
    ? "This public HTTP endpoint is read-only. Server shell access uses the private SSH-tunneled Terminal link on each project."
    : "Fixed project commands are available here. The private Terminal is isolated behind an SSH tunnel.";
  elements.commandList.innerHTML = projects.map((project) => {
    const buttons = project.actions.length
      ? project.actions.map((action) => `<button class="button" data-project="${escapeHtml(project.slug)}" data-action="${escapeHtml(action.id)}" data-label="${escapeHtml(action.label)}" type="button">${escapeHtml(action.label)}</button>`).join("")
      : `<span class="muted">${state.publicReadOnly ? "Disabled on public HTTP" : "No commands available"}</span>`;
    return `<tr><td><strong>${escapeHtml(project.name)}</strong></td><td><div class="command-buttons">${buttons}</div></td></tr>`;
  }).join("");
  elements.commandList.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", () => openActionDialog(button.dataset.project, button.dataset.action, button.dataset.label));
  });
}

function renderOpenAIUsage(usage) {
  return `
    <section class="surface usage-surface">
      <p class="eyebrow">OPENAI</p>
      <h2>${usage.status === "snapshot" ? "Month-to-date API cost" : "Usage data is not configured"}</h2>
      <p class="muted">${escapeHtml(usage.message)}</p>
      <div class="usage-grid">
        <div class="usage-value"><span>Current cost</span><strong>${formatMoney(usage.cost_usd)}</strong></div>
        <div class="usage-value"><span>Budget</span><strong>${formatMoney(usage.budget_usd)}</strong></div>
        <div class="usage-value"><span>Remaining</span><strong>${formatMoney(usage.remaining_usd)}</strong></div>
      </div>
      <p class="cell-detail">Last update: ${escapeHtml(usage.updated_at || "Unavailable")}</p>
    </section>
  `;
}

function renderOracleUsage(usage) {
  const resources = Array.isArray(usage.free_resources) ? usage.free_resources : [];
  const resourceRows = resources.length
    ? resources.map((resource) => `
      <tr>
        <td><strong>${escapeHtml(resource.label || resource.key)}</strong></td>
        <td>${escapeHtml(formatQuantity(resource.used, resource.unit))}</td>
        <td>${escapeHtml(formatQuantity(resource.free_allowance, resource.unit))}</td>
        <td>${escapeHtml(formatQuantity(resource.free_remaining, resource.unit))}</td>
      </tr>
    `).join("")
    : `<tr><td colspan="4" class="muted">Free allowance data is not configured.</td></tr>`;
  const serviceCosts = Array.isArray(usage.service_costs) ? usage.service_costs : [];
  const serviceRows = serviceCosts.length
    ? serviceCosts.map((service) => `
      <tr>
        <td>${escapeHtml(service.name || "Other")}</td>
        <td>${escapeHtml(formatMoney(service.cost, service.currency || usage.currency))}</td>
      </tr>
    `).join("")
    : `<tr><td colspan="2" class="muted">No billable service cost is available.</td></tr>`;

  return `
    <section class="surface usage-surface">
      <p class="eyebrow">ORACLE CLOUD</p>
      <h2>${usage.status === "snapshot" ? "Month-to-date infrastructure cost" : "Usage data is not configured"}</h2>
      <p class="muted">${escapeHtml(usage.message)}</p>
      <div class="usage-grid">
        <div class="usage-value"><span>Current cost</span><strong>${formatMoney(usage.cost, usage.currency)}</strong></div>
        <div class="usage-value"><span>Budget</span><strong>${formatMoney(usage.budget, usage.currency)}</strong></div>
        <div class="usage-value"><span>Remaining</span><strong>${formatMoney(usage.remaining, usage.currency)}</strong></div>
      </div>
      <div class="usage-section">
        <h3>Always Free compute</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Resource</th><th>Used</th><th>Free allowance</th><th>Remaining</th></tr></thead>
            <tbody>${resourceRows}</tbody>
          </table>
        </div>
      </div>
      <details class="usage-details">
        <summary>Cost by service</summary>
        <div class="table-wrap">
          <table><thead><tr><th>Service</th><th>Cost</th></tr></thead><tbody>${serviceRows}</tbody></table>
        </div>
      </details>
      <p class="cell-detail">Last update: ${escapeHtml(usage.updated_at || "Unavailable")}</p>
    </section>
  `;
}

function renderUsage(usage) {
  const providers = Array.isArray(usage?.providers) ? usage.providers : [usage || {}];
  elements.usagePanel.innerHTML = providers.map((provider) => (
    provider.provider === "Oracle Cloud" ? renderOracleUsage(provider) : renderOpenAIUsage(provider)
  )).join("");
}

function openActionDialog(project, action, label) {
  state.pendingAction = {project, action, label};
  elements.dialogTitle.textContent = label;
  elements.dialogDescription.textContent = "The server will run this fixed command for the selected project.";
  elements.dialogCommand.textContent = `${project}:${action}`;
  elements.actionDialog.showModal();
}

async function runPendingAction() {
  const action = state.pendingAction;
  if (!action) return;
  elements.dialogConfirm.disabled = true;
  try {
    const result = await request("/api/actions", {
      method: "POST",
      body: JSON.stringify({
        project: action.project,
        action: action.action,
        confirmation: `${action.project}:${action.action}`,
      }),
    });
    elements.outputTitle.textContent = `${action.label} result`;
    elements.outputContent.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n") || "Command completed without output.";
    elements.outputDialog.showModal();
    showToast("Command completed.");
    await refreshOverview();
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.dialogConfirm.disabled = false;
    state.pendingAction = null;
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginError.textContent = "";
  try {
    const result = await request("/api/login", {
      method: "POST",
      body: JSON.stringify({token: elements.accessToken.value}),
    });
    state.authenticated = true;
    state.csrfToken = result.csrf_token;
    elements.accessToken.value = "";
    showApplication();
    await refreshOverview();
  } catch (error) {
    elements.loginError.textContent = error.message;
  }
});

elements.refreshButton.addEventListener("click", refreshOverview);
elements.logoutButton.addEventListener("click", async () => {
  try {
    await request("/api/logout", {method: "POST", body: "{}"});
  } finally {
    state.authenticated = false;
    state.csrfToken = "";
    showLogin();
  }
});

elements.dialogConfirm.addEventListener("click", (event) => {
  event.preventDefault();
  elements.actionDialog.close();
  runPendingAction();
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => selectPrimaryTab(button.dataset.tab));
});

window.addEventListener("popstate", () => selectPrimaryTab(tabFromPath(), false));

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && elements.appShell.hidden === false) refreshOverview();
});

state.refreshTimer = window.setInterval(() => {
  if (!document.hidden && elements.appShell.hidden === false) refreshOverview();
}, 20000);

initialize();
