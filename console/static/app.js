const state = {
  authenticated: false,
  publicReadOnly: false,
  trustedLocal: false,
  csrfToken: "",
  overview: null,
  roadmaps: null,
  activeRoadmap: "",
  activeRoadmapTrack: "overall",
  refreshTimer: null,
};

const elements = {
  loginShell: document.querySelector("#login-shell"),
  loginForm: document.querySelector("#login-form"),
  loginError: document.querySelector("#login-error"),
  accessToken: document.querySelector("#access-token"),
  appShell: document.querySelector("#app-shell"),
  workspace: document.querySelector(".workspace"),
  modeBadge: document.querySelector("#mode-badge"),
  syncState: document.querySelector("#sync-state"),
  refreshButton: document.querySelector("#refresh-button"),
  logoutButton: document.querySelector("#logout-button"),
  serverMetrics: document.querySelector("#server-metrics"),
  workstationDetail: document.querySelector("#workstation-detail"),
  roadmapTabs: document.querySelector("#roadmap-tabs"),
  roadmapTrackTabs: document.querySelector("#roadmap-track-tabs"),
  roadmapDetail: document.querySelector("#roadmap-detail"),
  backupSummary: document.querySelector("#backup-summary"),
  timerSummary: document.querySelector("#timer-summary"),
  usagePanel: document.querySelector("#usage-panel"),
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
    state.overview = await request("/api/overview");
    render();
    if (tabFromPath() === "roadmap") await refreshRoadmaps();
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
  renderWorkstations(state.overview.workstations || [], state.overview.projects || []);
  renderRoadmaps(state.roadmaps);
  renderRecovery(state.overview.backups);
  renderUsage(state.overview.usage);
}

async function refreshRoadmaps() {
  state.roadmaps = await request("/api/roadmaps");
  renderRoadmaps(state.roadmaps);
}

function renderRoadmaps(roadmaps) {
  if (!roadmaps) return;
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
  if (!window.DeveloperOSRoadmapView) {
    elements.roadmapDetail.innerHTML = `
      <section class="roadmap-empty">
        <h2>Roadmap renderer unavailable</h2>
        <p class="muted">The shared DeveloperOS roadmap bundle could not be loaded.</p>
      </section>
    `;
    return;
  }
  window.DeveloperOSRoadmapView.renderDetail(elements.roadmapDetail, project);
}

function tabFromPath() {
  return window.location.pathname.replace(/\/$/, "") === "/roadmap" ? "roadmap" : "projects";
}

function selectPrimaryTab(tab, updateHistory = true) {
  const button = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (!button) return;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".tab-view").forEach((view) => view.classList.toggle("active", view.id === `tab-${tab}`));
  elements.workspace.classList.toggle("full-width-workspace", ["projects", "resources"].includes(tab));
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
  elements.serverMetrics.innerHTML = `
    ${metrics.map((metric) => `
      <section class="resource-panel">
        <div class="metric">
          <div class="metric-reading">
            <span class="metric-label">${escapeHtml(metric.label)}</span>
            <strong class="metric-value">${escapeHtml(metric.value)}</strong>
            <span class="cell-detail">${escapeHtml(metric.detail || "")}</span>
          </div>
          <progress class="meter" max="100" value="${Math.max(0, Math.min(100, metric.percent))}">${metric.percent}%</progress>
        </div>
        ${resourceBreakdown(metric.key, system.resources?.[metric.key] || [])}
      </section>
    `).join("")}
  `;
}

function resourceBreakdown(metric, rows) {
  if (!rows.length) return `<p class="resource-empty">Usage breakdown unavailable.</p>`;
  const formatValue = (value) => metric === "cpu" ? `${Number(value).toFixed(1)}%` : formatBytes(value);
  return `
    <div class="resource-breakdown">
      ${rows.map((row) => `
        <article class="resource-row${row.slug === "other" ? " residual" : ""}">
          <div class="resource-row-heading"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(formatValue(row.value))}</span></div>
          <div class="resource-components">
            ${(row.components || []).map((component) => `
              <div class="resource-component">
                <div class="resource-component-heading">
                  <strong>${escapeHtml(component.name)}</strong>
                  <span>${escapeHtml(formatValue(component.value))}</span>
                </div>
                ${component.disposition ? `<span class="resource-disposition ${escapeHtml(component.disposition)}">${escapeHtml(resourceDisposition(component.disposition))}</span>` : ""}
                ${component.note ? `<p>${escapeHtml(component.note)}</p>` : ""}
              </div>
            `).join("") || `<p class="muted">No component detail available.</p>`}
          </div>
        </article>
      `).join("")}
    </div>
  `;
}

function resourceDisposition(value) {
  return ({
    baseline: "Required baseline",
    service: "Required service",
    shared: "Shared",
    protected: "Protected",
    reviewable: "Reviewable",
    unattributed: "Needs attribution",
  })[value] || value;
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

function workstationIndicator(workstation) {
  const online = workstation?.status === "online";
  const label = online ? "Online" : "Offline";
  return `<span class="workstation-indicator ${online ? "online" : "offline"}" title="${label}" aria-label="${label}"></span>`;
}

function workstationProject(workstation, slug) {
  return workstation?.projects?.find((project) => project.slug === slug);
}

function workstationRepositoryCell(project, kind) {
  if (!project) return `${statusBadge("Unavailable", "neutral")}<div class="cell-detail">-</div>`;
  if (kind === "local") {
    return `${repositoryStatus(project)}<div class="cell-detail">${escapeHtml(shortRevision(project.repository?.revision))}</div>`;
  }
  return `${githubStatus(project.repository, project.comparison?.fresh)}<div class="cell-detail">${escapeHtml(project.repository?.remote_revision ? shortRevision(project.repository.remote_revision) : project.repository?.upstream || "-")}</div>`;
}

function containerStateBadge(container) {
  const stateValue = String(container?.state || "").toLowerCase();
  const statusValue = String(container?.status || "").toLowerCase();
  if (statusValue.includes("unhealthy")) return statusBadge("Unhealthy", "bad");
  if (stateValue === "running") return statusBadge("Running", "good");
  if (stateValue) return statusBadge(container.state, "bad");
  return statusBadge("Unknown", "neutral");
}

function renderProjectContainers(project) {
  const containers = project?.containers || [];
  if (!containers.length) {
    const message = project?.deployment?.mode === "systemd"
      ? "No Docker containers. This project runs as managed systemd services."
      : "No containers are registered for this project.";
    return `<div class="project-container-empty">${escapeHtml(message)}</div>`;
  }
  return `
    <div class="project-container-grid">
      ${containers.map((container) => `
        <article class="project-container-card">
          <div class="project-container-heading">
            <div><strong>${escapeHtml(container.service || container.name || "Container")}</strong><span>${escapeHtml(container.name || "-")}</span></div>
            ${containerStateBadge(container)}
          </div>
          <dl>
            <dt>Status</dt><dd>${escapeHtml(container.status || container.state || "Unavailable")}</dd>
            <dt>Image</dt><dd>${escapeHtml(container.image || "Unavailable")}</dd>
            <dt>Ports</dt><dd>${escapeHtml(container.ports || "None exposed")}</dd>
            <dt>Started</dt><dd>${escapeHtml(formatDate(container.started_at))}</dd>
          </dl>
        </article>
      `).join("")}
    </div>
  `;
}

function renderWorkstations(workstations, serverProjects) {
  if (!workstations.length) {
    elements.workstationDetail.innerHTML = "";
    return;
  }
  const home = workstations.find((workstation) => workstation.id === "home") || {name: "Home", status: "never_reported", projects: []};
  const office = workstations.find((workstation) => workstation.id === "office") || {name: "Office", status: "never_reported", projects: []};
  const serverProjectMap = new Map(serverProjects.map((project) => [project.slug, project]));
  const projects = new Map();
  for (const workstation of [home, office]) {
    for (const project of workstation.projects || []) {
      if (!projects.has(project.slug)) projects.set(project.slug, project);
    }
  }
  const sharedProjects = [...projects.values()].sort((left, right) => {
    const leftPort = Number(left.port) || Number.MAX_SAFE_INTEGER;
    const rightPort = Number(right.port) || Number.MAX_SAFE_INTEGER;
    return leftPort - rightPort || left.name.localeCompare(right.name);
  });
  elements.workstationDetail.innerHTML = `
    <div class="table-wrap project-comparison-wrap">
      <table class="project-comparison-table">
        <thead>
          <tr class="workstation-group-row">
            <th class="project-heading">Project</th>
            <th><span class="workstation-group">${workstationIndicator(home)}Home</span></th>
            <th><span class="workstation-group">${workstationIndicator(office)}Office</span></th>
            <th>GitHub</th>
            <th>Server</th>
            <th>Service</th>
            <th>Port</th>
            <th class="terminal-heading"><a class="terminal-link terminal-root-link" href="http://127.0.0.1:8092/?project=server" target="_blank" rel="noopener">Terminal</a></th>
          </tr>
        </thead>
        <tbody>
          ${sharedProjects.length ? sharedProjects.map((sharedProject) => {
            const homeProject = workstationProject(home, sharedProject.slug);
            const officeProject = workstationProject(office, sharedProject.slug);
            const commonProject = homeProject || officeProject || sharedProject;
            const serverProject = serverProjectMap.get(sharedProject.slug);
            const displayProject = serverProject || commonProject;
            const detailId = `project-containers-${sharedProject.slug}`;
            const commonStatusProject = [homeProject, officeProject].find((project) => project?.repository?.remote_refresh_status === "success" && project?.comparison?.fresh)
              || [homeProject, officeProject].find((project) => project?.comparison?.fresh)
              || homeProject
              || officeProject;
            return `
              <tr class="project-summary-row">
                <td class="project-cell"><button class="project-toggle" type="button" data-project-toggle="${escapeHtml(sharedProject.slug)}" aria-expanded="false" aria-controls="${escapeHtml(detailId)}"><span>${escapeHtml(displayProject.name)}</span><span class="project-toggle-mark" aria-hidden="true">+</span></button><div class="mobile-terminal">${terminalLink(displayProject)}</div></td>
                <td>${workstationRepositoryCell(homeProject, "local")}</td>
                <td>${workstationRepositoryCell(officeProject, "local")}</td>
                <td>${workstationRepositoryCell(commonStatusProject, "github")}</td>
                <td>${comparisonStatus(commonStatusProject?.comparison?.runtime_status)}<div class="cell-detail">${escapeHtml(shortRevisions(commonStatusProject?.comparison?.deployed_revisions))}</div></td>
                <td>${serviceStatus(commonStatusProject?.comparison?.service_status)}</td>
                <td><strong>${displayProject.port ? escapeHtml(displayProject.port) : "-"}</strong></td>
                <td class="terminal-cell">${terminalLink(displayProject)}</td>
              </tr>
              <tr class="project-container-row" id="${escapeHtml(detailId)}" hidden><td colspan="8">${renderProjectContainers(serverProject)}</td></tr>
            `;
          }).join("") : `<tr><td colspan="8" class="muted">No workstation reports have been received yet.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
  elements.workstationDetail.querySelectorAll("button[data-project-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = document.getElementById(`project-containers-${button.dataset.projectToggle}`);
      if (!row) return;
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      button.querySelector(".project-toggle-mark").textContent = expanded ? "+" : "−";
      row.hidden = expanded;
    });
  });
}

function githubStatus(repository, fresh = true) {
  if (!repository?.upstream) return statusBadge("Unavailable", "neutral");
  if (fresh === false) return statusBadge("Stale report", "neutral");
  if (repository.remote_refresh_status === "failed") return statusBadge("Refresh failed", "warn");
  if (repository.remote_refresh_status !== "success") return statusBadge("Unverified", "neutral");
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
  if (status === "stale") return statusBadge("Stale report", "neutral");
  return statusBadge("Unavailable", "neutral");
}

function backupStatus(backup) {
  if (backup.status === "healthy" && backup.verification_status === "passed") return statusBadge("Protected", "good");
  if (backup.status === "failed") return statusBadge("Backup failed", "bad");
  if (backup.status === "stale") return statusBadge("Backup stale", "warn");
  return statusBadge("Needs verification", "warn");
}

function renderRecovery(backups) {
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
  const resources = Array.isArray(usage.resources) ? usage.resources : [];
  const resourceRows = resources.length
    ? resources.map((resource) => `
      <tr>
        <td><strong>${escapeHtml(resource.label || resource.key)}</strong></td>
        <td>${escapeHtml(formatQuantity(resource.used, resource.unit))}</td>
        <td>${escapeHtml(formatQuantity(resource.free_allowance, resource.unit))}</td>
        <td>${escapeHtml(formatQuantity(resource.free_remaining, resource.unit))}</td>
        <td>${escapeHtml(formatQuantity(resource.projected_month_usage, resource.unit))}</td>
      </tr>
    `).join("")
    : `<tr><td colspan="5" class="muted">Free usage data is not available.</td></tr>`;
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
        <div class="usage-value"><span>Projected month-end cost</span><strong>${formatMoney(usage.projected_cost, usage.currency)}</strong></div>
        <div class="usage-value"><span>Forecast basis</span><strong>${usage.completed_days == null ? "Unavailable" : `${escapeHtml(usage.completed_days)} completed UTC day${usage.completed_days === 1 ? "" : "s"}`}</strong></div>
      </div>
      <div class="usage-section">
        <h3>Ampere A1 monthly free usage</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Resource</th><th>Free used</th><th>Free allowance</th><th>Free remaining</th><th>Month-end projection</th></tr></thead>
            <tbody>${resourceRows}</tbody>
          </table>
        </div>
        <p class="cell-detail">Usage comes from OCI billing records through the latest completed UTC day. Free ranges and overage rates come from Oracle's public price list. Month-end values are estimates, not an Oracle invoice.</p>
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

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    selectPrimaryTab(button.dataset.tab);
    if (button.dataset.tab === "roadmap" && !state.roadmaps) {
      refreshRoadmaps().catch((error) => showToast(error.message));
    }
  });
});

window.addEventListener("popstate", () => selectPrimaryTab(tabFromPath(), false));

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && elements.appShell.hidden === false) refreshOverview();
});

state.refreshTimer = window.setInterval(() => {
  if (!document.hidden && elements.appShell.hidden === false) refreshOverview();
}, 60000);

initialize();
