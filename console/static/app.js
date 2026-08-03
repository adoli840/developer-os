const state = {
  authenticated: false,
  publicReadOnly: false,
  trustedLocal: false,
  csrfToken: "",
  overview: null,
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
  resourceTime: document.querySelector("#resource-time"),
  workstationDetail: document.querySelector("#workstation-detail"),
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
  renderWorkstations(state.overview.workstations || []);
  renderRecovery(state.overview.backups);
  renderUsage(state.overview.usage);
  const collectedAt = state.overview.system.collected_at;
  elements.resourceTime.textContent = collectedAt
    ? `Collected ${new Date(collectedAt * 1000).toLocaleString()}`
    : "Collection time unavailable";
}

function tabFromPath() {
  return "resources";
}

function selectPrimaryTab(tab, updateHistory = true) {
  const button = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (!button) return;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".tab-view").forEach((view) => view.classList.toggle("active", view.id === `tab-${tab}`));
  if (updateHistory) {
    const nextPath = "/";
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

function workstationStatus(workstation) {
  if (workstation.status === "online") return statusBadge("Online", "good");
  if (workstation.status === "offline") return statusBadge("Offline", "neutral");
  if (workstation.status === "never_reported") return statusBadge("Not connected", "warn");
  return statusBadge("Invalid report", "bad");
}

function renderWorkstations(workstations) {
  if (!workstations.length) {
    elements.workstationDetail.innerHTML = "";
    return;
  }
  elements.workstationDetail.innerHTML = workstations.map((workstation) => {
    const lastReport = formatDate(workstation.last_report_at);
    const staleReport = workstation.status === "offline";
    const detailDescription = staleReport
      ? `Stale snapshot from ${lastReport}. Local and GitHub values are historical; comparisons are unavailable.`
      : workstation.online
        ? "Live local state."
        : workstation.last_report_at
          ? `Last known state from ${lastReport}.`
          : "No report has been received yet.";
    return `
      <section class="surface">
        <div class="surface-heading">
          <div><h2>${escapeHtml(workstation.name)} repositories</h2><p>${escapeHtml(detailDescription)}</p></div>
          ${workstationStatus(workstation)}
        </div>
        <div class="table-wrap">
          <table class="project-comparison-table">
            <thead><tr><th>Project</th><th>Local</th><th>GitHub</th><th>Server</th><th>Service</th><th>Port</th><th>Terminal</th></tr></thead>
            <tbody>
              ${workstation.projects.length ? workstation.projects.map((project) => `
                <tr>
                  <td><strong>${escapeHtml(project.name)}</strong><div class="mobile-terminal">${terminalLink(project)}</div></td>
                  <td>${repositoryStatus(project)}<div class="cell-detail">${escapeHtml(shortRevision(project.repository?.revision))}</div></td>
                  <td>${githubStatus(project.repository, project.comparison?.fresh)}<div class="cell-detail">${escapeHtml(project.repository?.remote_revision ? shortRevision(project.repository.remote_revision) : project.repository?.upstream || "-")}</div></td>
                  <td>${comparisonStatus(project.comparison?.runtime_status)}<div class="cell-detail">${escapeHtml(shortRevisions(project.comparison?.deployed_revisions))}</div></td>
                  <td>${serviceStatus(project.comparison?.service_status)}</td>
                  <td><strong>${project.port ? escapeHtml(project.port) : "-"}</strong></td>
                  <td class="terminal-cell">${terminalLink(project)}</td>
                </tr>
              `).join("") : `<tr><td colspan="7" class="muted">No ${escapeHtml(workstation.name)} report has been received yet.</td></tr>`}
            </tbody>
          </table>
        </div>
      </section>
    `;
  }).join("");
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
