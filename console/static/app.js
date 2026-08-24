const UI_STATE_KEY = "developer-os-console-ui-state-v1";
const MEMO_PROJECTS = [
  {slug: "developer-os", name: "OS"},
  {slug: "btest", name: "bTest"},
  {slug: "oa", name: "OA"},
  {slug: "gaia", name: "Gaia"},
];
const PRIMARY_TABS = new Set(["projects", "orchestration", "resources", "roadmap", "recovery", "oracle", "memo"]);

function readUiState() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(UI_STATE_KEY) || "{}");
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  } catch {
    return {};
  }
}

const savedUiState = readUiState();
const emptyMemos = () => Object.fromEntries(MEMO_PROJECTS.map((project) => [project.slug, ""]));
const emptyMemoStates = () => Object.fromEntries(MEMO_PROJECTS.map((project) => [project.slug, "Saved"]));

const state = {
  authenticated: false,
  publicReadOnly: false,
  trustedLocal: false,
  csrfToken: "",
  overview: null,
  roadmaps: null,
  orchestration: null,
  dispatchPreviews: [],
  returnHandoffs: [],
  exactDeliveries: [],
  apiMainlineReturns: [],
  autoSafeContinuePilot: null,
  activityTimeline: [],
  apiMainlineStart: null,
  apiMainlineRun: null,
  apiMainlineStartInputChanged: false,
  activeTab: PRIMARY_TABS.has(savedUiState.activeTab) ? savedUiState.activeTab : "projects",
  activeRoadmap: typeof savedUiState.activeRoadmap === "string" ? savedUiState.activeRoadmap : "",
  activeRoadmapTrack: "overall",
  activeRoadmapTracks: savedUiState.activeRoadmapTracks
    && typeof savedUiState.activeRoadmapTracks === "object"
    && !Array.isArray(savedUiState.activeRoadmapTracks)
    ? savedUiState.activeRoadmapTracks
    : {},
  activeMemoProject: MEMO_PROJECTS.some((project) => project.slug === savedUiState.activeMemoProject)
    ? savedUiState.activeMemoProject
    : "developer-os",
  activeOrchestrationProject: typeof savedUiState.activeOrchestrationProject === "string"
    ? savedUiState.activeOrchestrationProject
    : "developer-os",
  memos: emptyMemos(),
  memoSaveStates: emptyMemoStates(),
  memoSaveTimers: new Map(),
  memoSaveVersions: Object.fromEntries(MEMO_PROJECTS.map((project) => [project.slug, 0])),
  refreshTimer: null,
};

function persistUiState() {
  try {
    window.sessionStorage.setItem(UI_STATE_KEY, JSON.stringify({
      activeTab: state.activeTab,
      activeRoadmap: state.activeRoadmap,
      activeRoadmapTracks: state.activeRoadmapTracks,
      activeMemoProject: state.activeMemoProject,
      activeOrchestrationProject: state.activeOrchestrationProject,
    }));
  } catch {
    // The console remains usable when browser storage is disabled or unavailable.
  }
}

const elements = {
  loginShell: document.querySelector("#login-shell"),
  loginForm: document.querySelector("#login-form"),
  loginError: document.querySelector("#login-error"),
  accessToken: document.querySelector("#access-token"),
  appShell: document.querySelector("#app-shell"),
  workspace: document.querySelector(".workspace"),
  logoutButton: document.querySelector("#logout-button"),
  orchestrationNav: document.querySelector('.nav-item[data-tab="orchestration"]'),
  orchestrationProject: document.querySelector("#orchestration-project"),
  orchestrationModes: document.querySelector("#orchestration-modes"),
  orchestrationControls: document.querySelector("#orchestration-controls"),
  orchestrationStatus: document.querySelector("#orchestration-status"),
  mainlineAuthorityPanel: document.querySelector("#mainline-authority-panel"),
  apiMainlineStartPanel: document.querySelector("#api-mainline-start-panel"),
  apiMainlineStartForm: document.querySelector("#api-mainline-start-form"),
  apiMainlineStartStatus: document.querySelector("#api-mainline-start-status"),
  apiMainlineStartFacts: document.querySelector("#api-mainline-start-facts"),
  apiMainlineApprove: document.querySelector("#api-mainline-approve"),
  apiMainlineCancel: document.querySelector("#api-mainline-cancel"),
  autoSafeContinuePanel: document.querySelector("#auto-safe-continue-panel"),
  autoSafeContinueStatus: document.querySelector("#auto-safe-continue-status"),
  autoSafeContinueFacts: document.querySelector("#auto-safe-continue-facts"),
  activityTimelinePanel: document.querySelector("#activity-timeline-panel"),
  activityTimelineCount: document.querySelector("#activity-timeline-count"),
  activityTimeline: document.querySelector("#activity-timeline"),
  orchestrationNodes: document.querySelector("#orchestration-nodes"),
  orchestrationRoutes: document.querySelector("#orchestration-routes"),
  nodeCount: document.querySelector("#node-count"),
  routeCount: document.querySelector("#route-count"),
  nodeForm: document.querySelector("#node-form"),
  routeForm: document.querySelector("#route-form"),
  dispatchPreviewCount: document.querySelector("#dispatch-preview-count"),
  dispatchPreviews: document.querySelector("#dispatch-previews"),
  dispatchPreviewForm: document.querySelector("#dispatch-preview-form"),
  serverMetrics: document.querySelector("#server-metrics"),
  workstationDetail: document.querySelector("#workstation-detail"),
  roadmapTabs: document.querySelector("#roadmap-tabs"),
  roadmapTrackTabs: document.querySelector("#roadmap-track-tabs"),
  roadmapDetail: document.querySelector("#roadmap-detail"),
  backupSummary: document.querySelector("#backup-summary"),
  timerSummary: document.querySelector("#timer-summary"),
  oracleUsagePanel: document.querySelector("#oracle-usage-panel"),
  memoShell: document.querySelector("#memo-shell"),
  memoProjectList: document.querySelector("#memo-project-list"),
  memoActiveProject: document.querySelector("#memo-active-project"),
  memoSaveState: document.querySelector("#memo-save-state"),
  memoEditor: document.querySelector("#memo-editor"),
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
  if (state.csrfToken && !headers["X-CSRF-Token"] && options.method && options.method !== "GET") {
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
    const error = new Error(body.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
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
    const startup = [
      refreshOverview(),
      loadMemos().then(renderMemo).catch((error) => {
        renderMemo();
        showToast(error.message);
      }),
    ];
    if (!state.publicReadOnly) startup.push(loadOrchestration());
    await Promise.all(startup);
  } catch {
    showLogin();
  }
}

async function copyExactText(value) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const input = document.createElement("textarea");
  input.value = value;
  input.readOnly = true;
  input.style.position = "fixed";
  input.style.opacity = "0";
  input.style.pointerEvents = "none";
  document.body.appendChild(input);
  input.select();
  input.setSelectionRange(0, value.length);
  const copied = document.execCommand("copy");
  input.remove();
  if (!copied) throw new Error("The exact message could not be copied.");
}

async function loadMemos() {
  const result = await request("/api/memos");
  state.memos = emptyMemos();
  for (const item of result.items || []) {
    if (Object.hasOwn(state.memos, item.project) && typeof item.content === "string") {
      state.memos[item.project] = item.content;
    }
  }
  state.memoSaveStates = emptyMemoStates();
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
  elements.orchestrationNav.hidden = state.publicReadOnly;
  if (state.publicReadOnly && state.activeTab === "orchestration") selectPrimaryTab("projects");
}

async function refreshOverview() {
  try {
    state.overview = await request("/api/overview");
    render();
    if (tabFromPath() === "roadmap") await refreshRoadmaps();
  } catch (error) {
    showToast(error.message);
  }
}

function render() {
  if (!state.overview) return;
  renderMetrics(state.overview.system);
  renderWorkstations(state.overview.workstations || [], state.overview.projects || []);
  renderRoadmaps(state.roadmaps);
  renderRecovery(state.overview.backups);
  renderOracleUsage(state.overview.usage);
  renderMemo();
  renderOrchestration();
}

async function loadOrchestration() {
  state.orchestration = await request("/api/orchestration");
  await loadDispatchPreviews();
  await loadApiMainlineStart();
  renderOrchestration();
}

async function loadDispatchPreviews() {
  if (!state.activeOrchestrationProject) return;
  const result = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/dispatch-previews`);
  state.dispatchPreviews = result.previews || [];
  state.returnHandoffs = result.returns || [];
  state.exactDeliveries = result.deliveries || [];
  state.apiMainlineReturns = result.mainline_returns || [];
  state.autoSafeContinuePilot = result.auto_safe_continue_pilot || null;
  state.activityTimeline = result.activity_timeline?.events || [];
}

async function loadApiMainlineStart() {
  if (!state.activeOrchestrationProject) return;
  const result = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/api-mainline-start`);
  state.apiMainlineStart = result.start || null;
  state.apiMainlineRun = result.run || null;
  state.apiMainlineStartInputChanged = false;
}

function activeOrchestrationProject() {
  return state.orchestration?.projects?.find((project) => project.project === state.activeOrchestrationProject)
    || state.orchestration?.projects?.[0]
    || null;
}

function replaceOrchestrationProject(project) {
  if (!state.orchestration || !project) return;
  const index = state.orchestration.projects.findIndex((item) => item.project === project.project);
  if (index >= 0) state.orchestration.projects[index] = project;
  renderOrchestration();
}

function orchestrationStatusKind(status) {
  if (["IDLE", "RUNNING"].includes(status)) return "good";
  if (["WAITING_FOR_USER", "PAUSED", "BLOCKED"].includes(status)) return "warn";
  if (["ERROR", "STOPPED"].includes(status)) return "bad";
  return "neutral";
}

function capabilityKind(health) {
  if (["HEALTHY", "AVAILABLE"].includes(health)) return "good";
  if (health === "DEGRADED") return "warn";
  return "neutral";
}

function splitNodeIds(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function renderCodexBinding(transport) {
  if (!transport) return "";
  const binding = transport.workspace_binding;
  return `
    <dl class="codex-binding-detail">
      <dt>Development Client</dt><dd>${escapeHtml(transport.development_client || "Codex Desktop")}</dd>
      <dt>Orchestration Runtime</dt><dd>${escapeHtml(transport.orchestration_runtime || "Unavailable")}</dd>
      <dt>Dispatch</dt><dd>${escapeHtml((transport.dispatch_status || "LOCKED").replaceAll("_", " / "))}</dd>
      ${binding ? `
        <dt>Workspace</dt><dd>${escapeHtml(binding.windows_workspace)} ↔ ${escapeHtml(binding.wsl_workspace)}</dd>
        <dt>Git</dt><dd>${escapeHtml(binding.git_branch)} @ ${escapeHtml(binding.git_head.slice(0, 12))} · ${binding.git_status_entry_count} status entries</dd>
        <dt>External-change guard</dt><dd>${escapeHtml(binding.workspace_guard)}</dd>
      ` : `<dt>Workspace</dt><dd>Unbound</dd>`}
    </dl>
  `;
}

function renderOrchestration() {
  if (!state.orchestration) return;
  const projects = state.orchestration.projects || [];
  if (!projects.some((project) => project.project === state.activeOrchestrationProject)) {
    state.activeOrchestrationProject = projects[0]?.project || "";
  }
  persistUiState();
  elements.orchestrationProject.innerHTML = projects.map((project) => `
    <option value="${escapeHtml(project.project)}"${project.project === state.activeOrchestrationProject ? " selected" : ""}>${escapeHtml(MEMO_PROJECTS.find((item) => item.slug === project.project)?.name || project.project)}</option>
  `).join("");
  const project = activeOrchestrationProject();
  if (!project) return;

  const modes = state.orchestration.selectable_modes || [];
  elements.orchestrationModes.innerHTML = `
    ${modes.map((mode) => `<button class="mode-option${project.mode === mode ? " active" : ""}" type="button" data-orchestration-mode="${escapeHtml(mode)}" aria-pressed="${project.mode === mode}">${escapeHtml(mode.replaceAll("_", " "))}</button>`).join("")}
    <button class="mode-option locked" type="button" disabled title="Pilot locked until cumulative cost cap approval">AUTO SAFE-CONTINUE PILOT</button>
  `;
  elements.orchestrationControls.innerHTML = [
    ["ENABLE", "Enable", project.orchestration_enabled && project.status !== "STOPPED"],
    ["PAUSE", "Pause", !project.orchestration_enabled || ["DISABLED", "STOPPED", "PAUSED"].includes(project.status)],
    ["RESUME", "Resume", project.status !== "PAUSED"],
    ["STOP", "Stop", project.mode === "OFF" || ["DISABLED", "STOPPED"].includes(project.status)],
  ].map(([action, label, disabled]) => `<button class="button${action === "STOP" ? " danger" : ""}" data-orchestration-action="${action}" type="button"${disabled ? " disabled" : ""}>${label}</button>`).join("");

  elements.orchestrationStatus.innerHTML = [
    ["Status", statusBadge(project.status, orchestrationStatusKind(project.status))],
    ["Mode", escapeHtml(project.mode.replaceAll("_", " "))],
    ["Current cycle", escapeHtml(project.current_cycle || "None")],
    ["Last Gate", escapeHtml(project.last_gate || "None")],
    ["Waiting reason", escapeHtml(project.waiting_reason || "None")],
  ].map(([label, value]) => `<div class="orchestration-status-item"><span>${label}</span><strong>${value}</strong></div>`).join("");

  const mainline = project.mainline_state;
  const bootstrap = mainline?.api_mainline?.bootstrap_candidate || {};
  elements.mainlineAuthorityPanel.hidden = !mainline;
  elements.mainlineAuthorityPanel.innerHTML = mainline ? `
    <div class="mainline-authority-heading">
      <div><span>Mainline authority</span><strong>${escapeHtml(
        mainline.authority === "BTEST_MAINLINE_API"
          ? "DeveloperOS API Mainline (ON)"
          : "Native GPT (OFF)"
      )}</strong></div>
      ${statusBadge(mainline.api_mainline.status.replaceAll("_", " "), "neutral")}
    </div>
    <div class="mainline-authority-facts">
      <div><span>API Mainline</span><strong>${mainline.api_mainline.conversation_initialized ? "Initialized" : "Not initialized"}</strong></div>
      <div><span>Current Gate</span><strong>${escapeHtml(mainline.api_mainline.current_gate || "None")}</strong></div>
      <div><span>Current destination</span><strong>${escapeHtml(mainline.api_mainline.current_destination || "None")}</strong></div>
      <div><span>Capabilities</span><strong>${Object.entries(mainline.api_mainline.capabilities).map(([name, status]) => `${escapeHtml(name)}: ${escapeHtml(status.replaceAll("_", " "))}`).join(" / ")}</strong></div>
      <div><span>Bootstrap candidate</span><strong>${escapeHtml(bootstrap.status || "NOT PREPARED")}</strong></div>
      <div><span>Bootstrap model / cap</span><strong>${bootstrap.model ? `${escapeHtml(bootstrap.model)} / $${escapeHtml(bootstrap.proposed_hard_cap_usd || "-")}` : "Unavailable"}</strong></div>
      <div><span>Canonical state</span><strong><code>${escapeHtml((bootstrap.canonical_state_sha256 || "").slice(0, 16) || "Unavailable")}</code></strong></div>
      <div><span>Live initialization</span><strong>LOCKED / USER APPROVAL REQUIRED</strong></div>
    </div>
  ` : "";

  const apiAuthorityActive = project.project === "btest"
    && project.orchestration_enabled
    && mainline?.authority === "BTEST_MAINLINE_API";
  const start = state.apiMainlineStart || {};
  const run = state.apiMainlineRun || {};
  const startStatus = state.apiMainlineStartInputChanged && start.status === "READY"
    ? "STALE / INPUT CHANGED"
    : (start.status || "NOT PREPARED");
  elements.apiMainlineStartPanel.hidden = project.project !== "btest";
  elements.apiMainlineStartStatus.textContent = startStatus.replaceAll("_", " ");
  elements.apiMainlineStartFacts.innerHTML = `
    <dt>Authority</dt><dd>${apiAuthorityActive ? "BTEST_MAINLINE_API" : "API MAINLINE REQUIRED"}</dd>
    <dt>Estimated maximum</dt><dd>${start.proposed_hard_cap_usd ? `$${escapeHtml(start.proposed_hard_cap_usd)}` : "Calculated on Start"}</dd>
    <dt>Candidate</dt><dd><code>${escapeHtml((start.candidate_file_sha256 || "").slice(0, 16) || "Not prepared")}</code></dd>
    <dt>Live initialization</dt><dd>${escapeHtml(run.status || "USER APPROVAL REQUIRED")}</dd>
    <dt>Mainline action</dt><dd>${escapeHtml(run.parsed_action || "None")}</dd>
    <dt>Destination</dt><dd>${escapeHtml(run.destination || "None")}</dd>
    <dt>User required</dt><dd>${run.parsed_action === "USER_REQUIRED" ? "Yes" : "No"}</dd>
  `;
  elements.apiMainlineStartForm.querySelector('button[type="submit"]').disabled = !apiAuthorityActive;
  const approvalReady = apiAuthorityActive && startStatus === "READY" && start.approval_state === "USER_APPROVAL_REQUIRED";
  elements.apiMainlineApprove.hidden = !approvalReady;
  elements.apiMainlineCancel.hidden = !approvalReady;

  const pilot = state.autoSafeContinuePilot || {};
  const cost = pilot.cost_preflight || {};
  elements.autoSafeContinuePanel.hidden = project.project !== "btest";
  elements.autoSafeContinueStatus.textContent = (cost.status || pilot.live_auto_run || "LOCKED").replaceAll("_", " ");
  elements.autoSafeContinueFacts.innerHTML = `
    <dt>Live execution</dt><dd>${escapeHtml(pilot.live_auto_run || "LOCKED")}</dd>
    <dt>Maximum cycles</dt><dd>${escapeHtml(String(pilot.max_auto_cycles ?? 2))}</dd>
    <dt>Per-call worst case</dt><dd>${cost.per_call_hard_worst_case_usd ? `$${escapeHtml(cost.per_call_hard_worst_case_usd)}` : "Preflight required"}</dd>
    <dt>Cumulative worst case</dt><dd>${cost.cumulative_hard_worst_case_usd ? `$${escapeHtml(cost.cumulative_hard_worst_case_usd)}` : "Preflight required"}</dd>
    <dt>Recommended pilot cap</dt><dd>${cost.recommended_pilot_cap_usd ? `$${escapeHtml(cost.recommended_pilot_cap_usd)}` : "User decision required"}</dd>
    <dt>Retries / fallback</dt><dd>0 / 0</dd>
  `;

  const timeline = state.activityTimeline || [];
  elements.activityTimelinePanel.hidden = project.project !== "btest";
  elements.activityTimelineCount.textContent = String(timeline.length);
  elements.activityTimeline.innerHTML = timeline.length ? timeline.map((event) => {
    const detail = event.detail || {};
    const attention = event.status === "USER_REQUIRED" || detail.gate === "USER_REQUIRED";
    return `
      <details class="timeline-row${attention ? " needs-user" : ""}">
        <summary>
          <time>${escapeHtml(new Date(event.timestamp).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}))}</time>
          <span>${escapeHtml(event.source)}</span>
          <span class="timeline-arrow" aria-hidden="true">→</span>
          <span>${escapeHtml(event.destination)}</span>
          <strong>${escapeHtml(event.event_type.replaceAll("_", " "))}</strong>
          ${statusBadge(event.status, attention ? "warn" : "neutral")}
        </summary>
        <dl class="timeline-detail">
          <dt>Handoff</dt><dd>${escapeHtml(detail.handoff_id || "None")}</dd>
          <dt>Gate</dt><dd>${escapeHtml(detail.gate || "None")}</dd>
          <dt>Message</dt><dd>${escapeHtml(detail.message_preview || "No preview")}</dd>
          <dt>Tokens / cost</dt><dd>${escapeHtml(detail.token_usage ? JSON.stringify(detail.token_usage) : "Unavailable")} / ${detail.cost_usd ? `$${escapeHtml(detail.cost_usd)}` : "Unavailable"}</dd>
          <dt>Hashes</dt><dd><code>${escapeHtml(JSON.stringify(detail.hashes || {}))}</code></dd>
        </dl>
      </details>
    `;
  }).join("") : '<p class="empty-state">No orchestration activity</p>';

  elements.nodeCount.textContent = String(project.nodes.length);
  elements.orchestrationNodes.innerHTML = project.nodes.length ? project.nodes.map((node) => `
    <article class="node-row">
      <div class="node-main"><strong>${escapeHtml(node.display_name)}</strong><span>${escapeHtml(node.node_id)} · ${escapeHtml(node.role)}${node.authority_status ? ` · ${escapeHtml(node.authority_status)}` : ""}</span></div>
      <div class="node-transport"><span>${escapeHtml(node.transport_kind.replaceAll("_", " "))}</span>${statusBadge(node.capabilities.health, capabilityKind(node.capabilities.health))}</div>
      <div class="node-capabilities"><span>Read ${node.capabilities.can_read ? "Yes" : "No"}</span><span>Write ${node.capabilities.can_write ? "Yes" : "No"}</span><span>Capture ${node.capabilities.capture_message ? "Yes" : "No"}</span><span>${node.transport_configured ? "Configured" : "No reference"}</span>${node.codex_transport ? `<span>${escapeHtml(node.codex_transport.connection_status)}</span><span>${escapeHtml(node.codex_transport.binding_status)}</span><span>${escapeHtml(node.codex_transport.protocol_version || "Protocol unavailable")}</span><span>${escapeHtml(node.codex_transport.last_transport_health_check || "Not checked")}</span>` : ""}</div>
      ${node.codex_transport ? `<div class="capability-tags">${Object.entries(node.codex_transport.features || {}).map(([name, status]) => `<span title="${escapeHtml(status)}">${escapeHtml(name.replaceAll("_", " "))}</span>`).join("")}</div>` : ""}
      ${renderCodexBinding(node.codex_transport)}
      <div class="row-actions"><button class="button quiet" data-node-toggle="${escapeHtml(node.node_id)}" data-enabled="${node.enabled}" type="button">${node.enabled ? "Disable" : "Enable"}</button><button class="icon-button danger" data-node-delete="${escapeHtml(node.node_id)}" type="button" title="Delete node" aria-label="Delete ${escapeHtml(node.display_name)}">×</button></div>
    </article>
  `).join("") : '<p class="empty-state">No nodes</p>';

  elements.routeCount.textContent = String(project.routes.length);
  elements.orchestrationRoutes.innerHTML = project.routes.length ? project.routes.map((route) => `
    <article class="route-row">
      <span class="route-id">${escapeHtml(route.route_id)}</span>
      <strong>${escapeHtml(route.source_node_id)} <span aria-hidden="true">→</span> ${escapeHtml(route.destination_node_id)}</strong>
      <span>${escapeHtml(route.handoff_type)}</span>
      ${statusBadge(route.enabled ? "Enabled" : "Disabled", route.enabled ? "good" : "neutral")}
      <button class="icon-button danger" data-route-delete="${escapeHtml(route.route_id)}" type="button" title="Delete route" aria-label="Delete ${escapeHtml(route.route_id)}">×</button>
    </article>
  `).join("") : '<p class="empty-state">No routes</p>';

  const options = project.nodes.filter((node) => node.enabled).map((node) => `<option value="${escapeHtml(node.node_id)}">${escapeHtml(node.display_name)}</option>`).join("");
  elements.routeForm.elements.source_node_id.innerHTML = options;
  elements.routeForm.elements.destination_node_id.innerHTML = options;
  const codexRoutes = project.routes.filter((route) => {
    const destination = project.nodes.find((node) => node.node_id === route.destination_node_id);
    return route.enabled && destination?.enabled && destination.transport_kind === "CODEX_THREAD";
  });
  elements.dispatchPreviewForm.elements.route_id.innerHTML = codexRoutes.map((route) => `<option value="${escapeHtml(route.route_id)}">${escapeHtml(route.source_node_id)} to ${escapeHtml(route.destination_node_id)}</option>`).join("");
  elements.dispatchPreviewForm.querySelector('button[type="submit"]').disabled = codexRoutes.length === 0;
  elements.dispatchPreviewCount.textContent = String(state.dispatchPreviews.length);
  elements.dispatchPreviews.innerHTML = state.dispatchPreviews.length ? state.dispatchPreviews.map((preview) => {
    const returnHandoff = state.returnHandoffs.find((item) => item.source_dispatch_id === preview.handoff_id);
    const delivery = returnHandoff
      ? state.exactDeliveries.find((item) => item.return_id === returnHandoff.return_id)
      : null;
    const apiReturnHandoff = state.returnHandoffs.find((item) => (
      item.source_dispatch_id === preview.handoff_id
      && item.destination_node_id === "BTEST_MAINLINE_API"
    ));
    const apiMainlineReturn = apiReturnHandoff
      ? state.apiMainlineReturns.find((item) => item.return_id === apiReturnHandoff.return_id)
      : null;
    const displayState = preview.display_state || preview.state;
    const canApproveAndSend = project.mode === "SEMI_AUTO"
      && displayState === "PREPARED"
      && preview.approve_and_send_allowed
      && Boolean(preview.envelope_sha256);
    const canReject = preview.state === "PREPARED" && Boolean(preview.envelope_sha256);
    const statusKind = preview.state === "COMPLETED" || preview.state === "DISPATCHABLE"
      ? "good"
      : preview.state === "FAILED" || preview.state === "REJECTED" || displayState === "STALE_PREPARED_HANDOFF" ? "bad" : "neutral";
    return `
      <article class="dispatch-preview-row">
        <div class="dispatch-preview-heading"><strong>${escapeHtml(preview.handoff_id)}</strong>${statusBadge(preview.state === "SENT" ? "Codex Working" : displayState, statusKind)}</div>
        <p class="dispatch-task-summary">${escapeHtml(preview.task_summary || "No task summary")}</p>
        <dl class="dispatch-envelope-detail">
          <dt>Source</dt><dd>${escapeHtml(preview.source_node_id || "Unavailable")}</dd>
          <dt>Destination</dt><dd>${escapeHtml(preview.destination_node_id)}</dd>
          <dt>Route</dt><dd>${escapeHtml(preview.route_id || "Unavailable")}</dd>
          <dt>Workspace</dt><dd>${escapeHtml(preview.workspace || "Unavailable")}</dd>
          <dt>Branch / HEAD</dt><dd>${escapeHtml(preview.branch || "-")} / ${escapeHtml((preview.head || "").slice(0, 12) || "-")}</dd>
          <dt>Status fingerprint</dt><dd><code>${escapeHtml((preview.workspace_fingerprint_sha256 || "").slice(0, 16) || "Unavailable")}</code> · ${escapeHtml(String(preview.workspace_status_entry_count ?? "-"))} entries</dd>
          <dt>Workspace guard</dt><dd>${escapeHtml(preview.workspace_guard || "Unavailable")}</dd>
          <dt>Task hash</dt><dd><code>${escapeHtml((preview.task_content_sha256 || "").slice(0, 16) || "Unavailable")}</code></dd>
          <dt>Payload hash</dt><dd><code>${escapeHtml((preview.payload_sha256 || "").slice(0, 16) || "Unavailable")}</code></dd>
          <dt>Envelope</dt><dd><code>${escapeHtml((preview.envelope_sha256 || "").slice(0, 16) || "Unavailable")}</code></dd>
          <dt>Approval</dt><dd>${escapeHtml(preview.approval_state || "PENDING")}</dd>
          <dt>Duplicate send</dt><dd>${escapeHtml(preview.duplicate_send_status || "UNKNOWN")}</dd>
          <dt>Dispatch status</dt><dd>${escapeHtml(preview.dispatch_status || preview.state)}</dd>
          <dt>Actual send</dt><dd>${escapeHtml(preview.state === "SENT" ? "IN PROGRESS" : preview.actual_send_count ? "CONSUMED" : "LOCKED")}</dd>
        </dl>
        ${preview.task_message ? `<pre class="dispatch-response">${escapeHtml(preview.task_message)}</pre>` : ""}
        ${(canApproveAndSend || canReject) ? `<div class="dispatch-decision-actions">${canApproveAndSend ? `<button class="button primary" type="button" data-dispatch-approve-send="${escapeHtml(preview.handoff_id)}" data-envelope-sha256="${escapeHtml(preview.envelope_sha256)}">Approve &amp; Send</button>` : ""}${canReject ? `<button class="button danger" type="button" data-dispatch-reject="${escapeHtml(preview.handoff_id)}" data-envelope-sha256="${escapeHtml(preview.envelope_sha256)}">Reject</button>` : ""}</div>` : ""}
        ${preview.response_text ? `<p class="dispatch-response">${escapeHtml(preview.response_text)}</p>` : preview.error_code ? `<p class="dispatch-response">${escapeHtml(preview.error_code)}</p>` : ""}
        ${returnHandoff ? `<dl class="dispatch-envelope-detail return-handoff-detail">
          <dt>Codex result</dt><dd>Captured</dd>
          <dt>Return destination</dt><dd>${escapeHtml(returnHandoff.destination_node_id)}</dd>
          <dt>Transport capability</dt><dd>${escapeHtml(returnHandoff.transport_capability?.status || "UNSUPPORTED")}</dd>
          <dt>Return envelope</dt><dd>${escapeHtml(returnHandoff.delivery_status)}</dd>
          ${delivery ? `<dt>Source dispatch</dt><dd>${escapeHtml(delivery.source_dispatch_id)}</dd>
          <dt>Result hash</dt><dd><code>${escapeHtml(delivery.result_content_sha256.slice(0, 16))}</code></dd>
          <dt>Delivery state</dt><dd>${escapeHtml(delivery.state)}</dd>` : ""}
        </dl>${delivery ? `<div class="dispatch-decision-actions">
          ${delivery.state === "PREPARED" ? `<button class="button primary" type="button" data-delivery-copy="${escapeHtml(delivery.delivery_id)}" data-packet-sha256="${escapeHtml(delivery.delivery_packet_sha256)}">Copy Exact Message</button>` : ""}
          ${delivery.state === "COPIED" ? `<button class="button primary" type="button" data-delivery-mark="${escapeHtml(delivery.delivery_id)}" data-packet-sha256="${escapeHtml(delivery.delivery_packet_sha256)}">Mark Delivered</button>` : ""}
          ${["PREPARED", "COPIED"].includes(delivery.state) ? `<button class="button danger" type="button" data-delivery-cancel="${escapeHtml(delivery.delivery_id)}" data-packet-sha256="${escapeHtml(delivery.delivery_packet_sha256)}">Cancel</button>` : ""}
        </div>` : ""}` : ""}
        ${apiMainlineReturn ? `<dl class="dispatch-envelope-detail return-handoff-detail">
          <dt>Codex result</dt><dd>Captured</dd>
          <dt>Return to Mainline</dt><dd>${escapeHtml(apiMainlineReturn.state)}</dd>
          <dt>Destination</dt><dd>BTEST_MAINLINE_API</dd>
          <dt>Transport capability</dt><dd>${escapeHtml(apiMainlineReturn.transport_capability)}</dd>
          <dt>Exact result hash</dt><dd><code>${escapeHtml(apiMainlineReturn.exact_result_sha256.slice(0, 16))}</code></dd>
          <dt>Duplicate state</dt><dd>${escapeHtml(apiMainlineReturn.duplicate_status)}</dd>
          <dt>Approval</dt><dd>${escapeHtml(apiMainlineReturn.approval_state || "USER_APPROVAL_REQUIRED")}</dd>
          <dt>Actual Mainline send</dt><dd>${apiMainlineReturn.actual_mainline_send_count ? "CONSUMED" : "LOCKED"}</dd>
          ${apiMainlineReturn.parsed_action ? `<dt>Mainline action</dt><dd>${escapeHtml(apiMainlineReturn.parsed_action)}</dd>` : ""}
          ${apiMainlineReturn.gate ? `<dt>Gate</dt><dd>${escapeHtml(apiMainlineReturn.gate)}</dd>` : ""}
          ${apiMainlineReturn.destination ? `<dt>Destination</dt><dd>${escapeHtml(apiMainlineReturn.destination)}</dd>` : ""}
          ${apiMainlineReturn.next_handoff_state ? `<dt>Next Codex handoff</dt><dd>${escapeHtml(apiMainlineReturn.next_handoff_state)}</dd>` : ""}
          ${apiMainlineReturn.decision_packet_state ? `<dt>Decision packet</dt><dd>${escapeHtml(apiMainlineReturn.decision_packet_state)}</dd>` : ""}
        </dl>${apiMainlineReturn.state === "PREPARED" && apiMainlineReturn.duplicate_status === "UNCONSUMED" ? `<div class="dispatch-decision-actions"><button class="button primary" type="button" data-mainline-return-approve="${escapeHtml(apiMainlineReturn.return_id)}" data-candidate-sha256="${escapeHtml(apiMainlineReturn.candidate_sha256)}" data-manifest-sha256="${escapeHtml(apiMainlineReturn.approval_manifest_sha256)}">Approve Return to Mainline</button></div>` : ""}` : ""}
      </article>
    `;
  }).join("") : '<p class="empty-state">No previews</p>';
}

async function mutateOrchestration(path, options) {
  const result = await request(path, options);
  replaceOrchestrationProject(result.project);
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
  state.activeRoadmapTrack = state.activeRoadmapTracks[state.activeRoadmap] || "overall";
  persistUiState();
  elements.roadmapTabs.innerHTML = projects.map((project) => {
    const active = project.slug === state.activeRoadmap;
    return `<button class="roadmap-tab${active ? " active" : ""}" data-roadmap="${escapeHtml(project.slug)}" role="tab" aria-selected="${active}" type="button">${escapeHtml(project.name)}</button>`;
  }).join("");
  elements.roadmapTabs.querySelectorAll("button[data-roadmap]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeRoadmap = button.dataset.roadmap;
      state.activeRoadmapTrack = state.activeRoadmapTracks[state.activeRoadmap] || "overall";
      persistUiState();
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
    state.activeRoadmapTracks[state.activeRoadmap] = state.activeRoadmapTrack;
    persistUiState();
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
  state.activeRoadmapTracks[state.activeRoadmap] = state.activeRoadmapTrack;
  persistUiState();
  elements.roadmapTrackTabs.hidden = false;
  elements.roadmapTrackTabs.innerHTML = choices.map((choice) => {
    const active = choice.slug === state.activeRoadmapTrack;
    return `<button class="roadmap-track-tab${active ? " active" : ""}" data-roadmap-track="${escapeHtml(choice.slug)}" role="tab" aria-selected="${active}" type="button">${escapeHtml(choice.name)}</button>`;
  }).join("");
  elements.roadmapTrackTabs.querySelectorAll("button[data-roadmap-track]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeRoadmapTrack = button.dataset.roadmapTrack;
      state.activeRoadmapTracks[state.activeRoadmap] = state.activeRoadmapTrack;
      persistUiState();
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
  if (window.location.pathname.replace(/\/$/, "") === "/roadmap") return "roadmap";
  if (window.location.pathname.replace(/\/$/, "") === "/oracle") return "oracle";
  if (window.location.pathname.replace(/\/$/, "") === "/orchestration") return "orchestration";
  return PRIMARY_TABS.has(state.activeTab) && state.activeTab !== "roadmap"
    ? state.activeTab
    : "projects";
}

function selectPrimaryTab(tab, updateHistory = true) {
  const button = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (!button) return;
  state.activeTab = tab;
  persistUiState();
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".tab-view").forEach((view) => view.classList.toggle("active", view.id === `tab-${tab}`));
  elements.workspace.classList.toggle("full-width-workspace", ["projects", "orchestration", "resources", "memo"].includes(tab));
  if (updateHistory) {
    const nextPath = tab === "roadmap" ? "/roadmap" : tab === "oracle" ? "/oracle" : tab === "orchestration" ? "/orchestration" : "/";
    if (window.location.pathname !== nextPath) window.history.pushState({tab}, "", nextPath);
  }
}

function renderMetrics(system) {
  const metrics = [
    {key: "cpu", label: "CPU", value: Number.isFinite(system.cpu_percent) ? `${system.cpu_percent}%` : `${system.cpu_count || "-"} cores`, percent: system.cpu_percent || 0},
    {key: "memory", label: "Memory", value: formatBytes(system.memory.used), detail: `of ${formatBytes(system.memory.total)}`, percent: system.memory.percent || 0},
    {key: "disk", label: "Disk", value: formatBytes(system.disk.used), detail: `${formatBytes(system.disk.free)} free`, percent: system.disk.percent || 0},
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
  const sortedRows = sortResourceItems(rows);
  return `
    <div class="resource-breakdown">
      ${sortedRows.map((row) => `
        <article class="resource-row${row.slug === "other" ? " residual" : ""}">
          <div class="resource-row-heading"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(formatValue(row.value))}</span></div>
          <div class="resource-components">
            ${sortResourceItems(row.components || []).map((component) => `
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

function sortResourceItems(items) {
  return [...items].sort((left, right) => {
    const valueDifference = resourceItemValue(right) - resourceItemValue(left);
    return valueDifference || String(left?.name || "").localeCompare(String(right?.name || ""));
  });
}

function resourceItemValue(item) {
  const value = Number(item?.value);
  return Number.isFinite(value) ? value : 0;
}

function renderMemo() {
  const active = MEMO_PROJECTS.find((project) => project.slug === state.activeMemoProject) || MEMO_PROJECTS[0];
  state.activeMemoProject = active.slug;
  persistUiState();
  elements.memoProjectList.querySelectorAll("button[data-memo-project]").forEach((button) => {
    const selected = button.dataset.memoProject === active.slug;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  elements.memoActiveProject.textContent = active.name;
  elements.memoEditor.setAttribute("aria-label", `${active.name} memo`);
  if (elements.memoEditor.value !== state.memos[active.slug]) {
    elements.memoEditor.value = state.memos[active.slug];
  }
  elements.memoSaveState.textContent = state.memoSaveStates[active.slug] || "Saved";
}

function queueActiveMemoSave() {
  const project = state.activeMemoProject;
  state.memos[project] = elements.memoEditor.value;
  state.memoSaveVersions[project] += 1;
  state.memoSaveStates[project] = "Saving";
  elements.memoSaveState.textContent = "Saving";
  window.clearTimeout(state.memoSaveTimers.get(project));
  state.memoSaveTimers.set(project, window.setTimeout(() => {
    state.memoSaveTimers.delete(project);
    saveMemo(project).catch(() => {});
  }, 450));
}

async function saveMemo(project) {
  const content = state.memos[project];
  const version = state.memoSaveVersions[project];
  try {
    await request(`/api/memos/${encodeURIComponent(project)}`, {
      method: "PUT",
      body: JSON.stringify({content}),
    });
    if (state.memoSaveVersions[project] === version) {
      state.memoSaveStates[project] = "Saved";
      if (state.activeMemoProject === project) elements.memoSaveState.textContent = "Saved";
    }
  } catch (error) {
    state.memoSaveStates[project] = "Not saved";
    if (state.activeMemoProject === project) elements.memoSaveState.textContent = "Not saved";
    showToast(error.message);
    throw error;
  }
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
  if (repo.behind > 0) return statusBadge(`${repo.behind} behind`, "behind");
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

function backupPolicyLabel(value) {
  if (!value) return "Pending first backup";
  if (value === "multi-container-excluding-market.klines-data") return "All DBs except Kline rows";
  if (value === "sqlite-full") return "Full memo database";
  return "Full database";
}

function renderRecovery(backups) {
  const backupItems = backups?.items || [];
  elements.backupSummary.innerHTML = `
    <div class="surface-heading"><div><h2>Database protection</h2><p>Daily backups with integrity or isolated restore verification.</p></div></div>
    <div class="backup-list">
      ${backupItems.length ? backupItems.map((backup) => `
        <div class="backup-row">
          <div><strong>${escapeHtml(backup.name)}</strong><span>${escapeHtml(backup.message)}</span></div>
          <div>${backupStatus(backup)}<span>${formatBytes(backup.size_bytes)}</span></div>
          <dl>
            <dt>Backup</dt><dd>${escapeHtml(formatDate(backup.last_success_at))}</dd>
            <dt>Verification</dt><dd>${escapeHtml(formatDate(backup.last_verification_at))}</dd>
            <dt>Policy</dt><dd>${escapeHtml(backupPolicyLabel(backup.backup_policy))}</dd>
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

function renderOracleUsage(usagePayload) {
  const usage = Array.isArray(usagePayload?.providers)
    ? usagePayload.providers.find((provider) => provider.provider === "Oracle Cloud")
    : null;
  if (!usage) {
    elements.oracleUsagePanel.innerHTML = '<section class="surface oracle-usage-surface"><p class="muted">Oracle usage data is not configured.</p></section>';
    return;
  }
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
    : '<tr><td colspan="5" class="muted">Free usage data is not available.</td></tr>';
  const serviceCosts = Array.isArray(usage.service_costs) ? usage.service_costs : [];
  const serviceRows = serviceCosts.length
    ? serviceCosts.map((service) => `
      <tr><td>${escapeHtml(service.name || "Other")}</td><td>${escapeHtml(formatMoney(service.cost, service.currency || usage.currency))}</td></tr>
    `).join("")
    : '<tr><td colspan="2" class="muted">No billable service cost is available.</td></tr>';
  elements.oracleUsagePanel.innerHTML = `
    <section class="surface oracle-usage-surface">
      <p class="eyebrow">ORACLE CLOUD</p>
      <h2>${usage.status === "snapshot" ? "Oracle infrastructure usage" : "Oracle usage data is not configured"}</h2>
      <p class="muted">${escapeHtml(usage.message)}</p>
      <div class="oracle-usage-grid">
        <div class="oracle-usage-value"><span>Current cost</span><strong>${formatMoney(usage.cost, usage.currency)}</strong></div>
        <div class="oracle-usage-value"><span>Projected month-end cost</span><strong>${formatMoney(usage.projected_cost, usage.currency)}</strong></div>
        <div class="oracle-usage-value"><span>Forecast basis</span><strong>${usage.completed_days == null ? "Unavailable" : `${escapeHtml(usage.completed_days)} completed UTC day${usage.completed_days === 1 ? "" : "s"}`}</strong></div>
      </div>
      <div class="oracle-usage-section">
        <h3>Ampere A1 monthly free usage</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>Resource</th><th>Free used</th><th>Free allowance</th><th>Free remaining</th><th>Month-end projection</th></tr></thead>
          <tbody>${resourceRows}</tbody>
        </table></div>
        <p class="cell-detail">Usage comes from OCI billing records through the latest completed UTC day. Free ranges and overage rates come from Oracle's public price list. Month-end values are estimates, not an Oracle invoice.</p>
      </div>
      <details class="oracle-usage-details">
        <summary>Cost by service</summary>
        <div class="table-wrap"><table><thead><tr><th>Service</th><th>Cost</th></tr></thead><tbody>${serviceRows}</tbody></table></div>
      </details>
      <p class="cell-detail">Last update: ${escapeHtml(usage.updated_at || "Unavailable")}</p>
    </section>
  `;
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

elements.logoutButton.addEventListener("click", async () => {
  try {
    await request("/api/logout", {method: "POST", body: "{}"});
  } finally {
    state.authenticated = false;
    state.csrfToken = "";
    showLogin();
  }
});

elements.memoProjectList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-memo-project]");
  if (!button) return;
  state.activeMemoProject = button.dataset.memoProject;
  renderMemo();
  elements.memoEditor.focus();
});

elements.memoEditor.addEventListener("input", queueActiveMemoSave);

elements.orchestrationProject.addEventListener("change", async () => {
  state.activeOrchestrationProject = elements.orchestrationProject.value;
  persistUiState();
  try {
    await loadDispatchPreviews();
    await loadApiMainlineStart();
  } catch (error) {
    showToast(error.message);
  }
  renderOrchestration();
});

elements.apiMainlineStartForm.elements.initial_request.addEventListener("input", () => {
  if (state.apiMainlineStart?.status === "READY") {
    state.apiMainlineStartInputChanged = true;
    renderOrchestration();
  }
});

elements.apiMainlineStartForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.apiMainlineStartForm);
  try {
    const result = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/api-mainline-start`, {
      method: "POST",
      body: JSON.stringify({initial_request: form.get("initial_request")}),
    });
    state.apiMainlineStart = result.start;
    state.apiMainlineStartInputChanged = false;
    renderOrchestration();
    showToast("API Mainline candidate prepared. Live initialization remains approval-locked.");
  } catch (error) {
    showToast(error.message);
  }
});

async function decideApiMainlineStart(action) {
  const start = state.apiMainlineStart || {};
  const button = action === "approve" ? elements.apiMainlineApprove : elements.apiMainlineCancel;
  button.disabled = true;
  if (action === "approve") {
    state.apiMainlineRun = {status: "SENDING"};
    renderOrchestration();
  }
  try {
    const result = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/api-mainline-start/${action}`, {
      method: "POST",
      body: JSON.stringify({
        candidate_file_sha256: start.candidate_file_sha256,
        approval_manifest_sha256: start.approval_manifest_sha256,
      }),
    });
    state.apiMainlineRun = result.run;
    await loadApiMainlineStart();
    renderOrchestration();
    showToast(action === "approve" ? "API Mainline turn completed." : "API Mainline candidate cancelled.");
  } catch (error) {
    await loadApiMainlineStart().catch(() => {});
    renderOrchestration();
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

elements.apiMainlineApprove.addEventListener("click", () => decideApiMainlineStart("approve"));
elements.apiMainlineCancel.addEventListener("click", () => decideApiMainlineStart("cancel"));

elements.orchestrationModes.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-orchestration-mode]");
  if (!button) return;
  try {
    await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/mode`, {
      method: "POST",
      body: JSON.stringify({mode: button.dataset.orchestrationMode}),
    });
  } catch (error) {
    showToast(error.message);
  }
});

elements.orchestrationControls.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-orchestration-action]");
  if (!button) return;
  try {
    await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/control`, {
      method: "POST",
      body: JSON.stringify({action: button.dataset.orchestrationAction}),
    });
  } catch (error) {
    showToast(error.message);
  }
});

elements.nodeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.nodeForm);
  const payload = {
    node_id: form.get("node_id"),
    display_name: form.get("display_name"),
    role: form.get("role"),
    transport_kind: form.get("transport_kind"),
    transport_ref: form.get("transport_ref"),
    enabled: true,
    allowed_sources: splitNodeIds(form.get("allowed_sources")),
    allowed_destinations: splitNodeIds(form.get("allowed_destinations")),
  };
  try {
    await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/nodes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.nodeForm.reset();
  } catch (error) {
    showToast(error.message);
  }
});

elements.orchestrationNodes.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("button[data-node-delete]");
  const toggleButton = event.target.closest("button[data-node-toggle]");
  if (!deleteButton && !toggleButton) return;
  const nodeId = deleteButton?.dataset.nodeDelete || toggleButton.dataset.nodeToggle;
  try {
    if (deleteButton) {
      await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/nodes/${encodeURIComponent(nodeId)}`, {
        method: "DELETE",
        body: "{}",
      });
    } else {
      await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/nodes/${encodeURIComponent(nodeId)}`, {
        method: "PUT",
        body: JSON.stringify({enabled: toggleButton.dataset.enabled !== "true"}),
      });
    }
  } catch (error) {
    showToast(error.message);
  }
});

elements.routeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.routeForm);
  const payload = {
    route_id: form.get("route_id"),
    source_node_id: form.get("source_node_id"),
    destination_node_id: form.get("destination_node_id"),
    handoff_type: form.get("handoff_type"),
    enabled: true,
  };
  try {
    await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/routes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.routeForm.reset();
    renderOrchestration();
  } catch (error) {
    showToast(error.message);
  }
});

elements.dispatchPreviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.dispatchPreviewForm);
  try {
    const result = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/dispatch-preview`, {
      method: "POST",
      body: JSON.stringify({
        handoff_id: form.get("handoff_id"),
        route_id: form.get("route_id"),
        message: form.get("message"),
      }),
    });
    replaceOrchestrationProject(result.project);
    await loadDispatchPreviews();
    elements.dispatchPreviewForm.reset();
    renderOrchestration();
  } catch (error) {
    showToast(error.message);
  }
});

elements.dispatchPreviews.addEventListener("click", async (event) => {
  const approveMainlineReturn = event.target.closest("button[data-mainline-return-approve]");
  if (approveMainlineReturn) {
    approveMainlineReturn.disabled = true;
    approveMainlineReturn.textContent = "Sending...";
    try {
      await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/api-mainline-returns/${encodeURIComponent(approveMainlineReturn.dataset.mainlineReturnApprove)}/approve`, {
        method: "POST",
        body: JSON.stringify({
          candidate_sha256: approveMainlineReturn.dataset.candidateSha256,
          approval_manifest_sha256: approveMainlineReturn.dataset.manifestSha256,
        }),
      });
      await loadDispatchPreviews();
      renderOrchestration();
    } catch (error) {
      await loadDispatchPreviews().catch(() => {});
      renderOrchestration();
      showToast(error.message);
    }
    return;
  }
  const copyDelivery = event.target.closest("button[data-delivery-copy]");
  const markDelivery = event.target.closest("button[data-delivery-mark]");
  const cancelDelivery = event.target.closest("button[data-delivery-cancel]");
  const deliveryButton = copyDelivery || markDelivery || cancelDelivery;
  if (deliveryButton) {
    deliveryButton.disabled = true;
    const deliveryId = copyDelivery?.dataset.deliveryCopy || markDelivery?.dataset.deliveryMark || cancelDelivery.dataset.deliveryCancel;
    try {
      let action = markDelivery ? "delivered" : cancelDelivery ? "cancel" : "copied";
      if (copyDelivery) {
        const content = await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/deliveries/${encodeURIComponent(deliveryId)}/content`, {
          method: "POST",
          body: JSON.stringify({delivery_packet_sha256: deliveryButton.dataset.packetSha256}),
        });
        await copyExactText(content.exact_message);
      }
      await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/deliveries/${encodeURIComponent(deliveryId)}/${action}`, {
        method: "POST",
        body: JSON.stringify({delivery_packet_sha256: deliveryButton.dataset.packetSha256}),
      });
      await loadDispatchPreviews();
      renderOrchestration();
    } catch (error) {
      deliveryButton.disabled = false;
      showToast(error.message);
    }
    return;
  }
  const approve = event.target.closest("button[data-dispatch-approve-send]");
  const reject = event.target.closest("button[data-dispatch-reject]");
  const button = approve || reject;
  if (!button) return;
  button.disabled = true;
  const handoffId = approve?.dataset.dispatchApproveSend || reject.dataset.dispatchReject;
  const action = approve ? "approve-send" : "reject";
  if (approve) approve.textContent = "Sending...";
  try {
    await request(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/dispatch-previews/${encodeURIComponent(handoffId)}/${action}`, {
      method: "POST",
      body: JSON.stringify({envelope_sha256: button.dataset.envelopeSha256}),
    });
    await loadDispatchPreviews();
    renderOrchestration();
  } catch (error) {
    button.disabled = false;
    showToast(error.message);
  }
});

elements.orchestrationRoutes.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-route-delete]");
  if (!button) return;
  try {
    await mutateOrchestration(`/api/orchestration/${encodeURIComponent(state.activeOrchestrationProject)}/routes/${encodeURIComponent(button.dataset.routeDelete)}`, {
      method: "DELETE",
      body: "{}",
    });
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    selectPrimaryTab(button.dataset.tab);
    if (button.dataset.tab === "roadmap" && !state.roadmaps) {
      refreshRoadmaps().catch((error) => showToast(error.message));
    }
    if (button.dataset.tab === "orchestration" && !state.orchestration && !state.publicReadOnly) {
      loadOrchestration().catch((error) => showToast(error.message));
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
