const state = {
  csrfToken: "",
  projects: [],
  selectedProject: "",
  history: [],
  historyIndex: 0,
  running: false,
};

const elements = {
  projectTabs: document.querySelector("#project-tabs"),
  contextPath: document.querySelector("#context-path"),
  transcript: document.querySelector("#transcript"),
  form: document.querySelector("#command-form"),
  input: document.querySelector("#command-input"),
  runButton: document.querySelector("#run-button"),
  prompt: document.querySelector("#prompt"),
  clearButton: document.querySelector("#clear-button"),
  template: document.querySelector("#command-template"),
};

function escapeText(value) {
  return String(value ?? "");
}

function selectedProject() {
  return state.projects.find((project) => project.slug === state.selectedProject);
}

function setProject(slug) {
  const project = state.projects.find((item) => item.slug === slug && item.available);
  if (!project || state.running) return;
  state.selectedProject = project.slug;
  elements.projectTabs.querySelectorAll(".project-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.project === project.slug);
  });
  elements.contextPath.textContent = `/projects/${project.slug}`;
  elements.prompt.textContent = `${project.slug}:$`;
  const url = new URL(window.location.href);
  url.searchParams.set("project", project.slug);
  window.history.replaceState(null, "", url);
  elements.input.focus();
}

function renderProjects() {
  elements.projectTabs.replaceChildren();
  state.projects.forEach((project) => {
    const button = document.createElement("button");
    button.className = "project-tab";
    button.type = "button";
    button.dataset.project = project.slug;
    button.dataset.available = String(project.available);
    button.textContent = project.name;
    button.disabled = !project.available;
    button.addEventListener("click", () => setProject(project.slug));
    elements.projectTabs.append(button);
  });
}

function appendEntry(command) {
  elements.transcript.querySelector(".empty-state")?.remove();
  const entry = elements.template.content.firstElementChild.cloneNode(true);
  entry.classList.add("running");
  entry.querySelector(".entry-prompt").textContent = `${state.selectedProject}:$`;
  entry.querySelector(".entry-command").textContent = command;
  entry.querySelector(".entry-result").textContent = "Running";
  elements.transcript.append(entry);
  elements.transcript.scrollTop = elements.transcript.scrollHeight;
  return entry;
}

function setRunning(running) {
  state.running = running;
  elements.input.disabled = running;
  elements.runButton.disabled = running;
  elements.projectTabs.querySelectorAll(".project-tab").forEach((button) => {
    button.disabled = running || button.dataset.available === "false";
  });
}

async function execute(command) {
  const entry = appendEntry(command);
  setRunning(true);
  try {
    const response = await fetch("/api/execute", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Terminal-CSRF": state.csrfToken,
      },
      body: JSON.stringify({project: state.selectedProject, command}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
    entry.classList.remove("running");
    entry.classList.toggle("failed", !body.ok);
    entry.querySelector(".entry-output").textContent = escapeText(body.output);
    const result = body.timed_out
      ? "Timed out"
      : `Exit ${body.returncode ?? "-"} · ${(body.duration_ms / 1000).toFixed(2)}s`;
    entry.querySelector(".entry-result").textContent = body.truncated ? `${result} · output truncated` : result;
  } catch (error) {
    entry.classList.remove("running");
    entry.classList.add("failed");
    entry.querySelector(".entry-output").textContent = escapeText(error.message);
    entry.querySelector(".entry-result").textContent = "Request failed";
  } finally {
    setRunning(false);
    elements.input.focus();
    elements.transcript.scrollTop = elements.transcript.scrollHeight;
  }
}

async function initialize() {
  try {
    const response = await fetch("/api/session", {cache: "no-store"});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Could not open terminal session.");
    state.csrfToken = body.csrf_token;
    state.projects = body.projects || [];
    renderProjects();
    const requested = new URLSearchParams(window.location.search).get("project");
    const initial = state.projects.find((project) => project.slug === requested && project.available)
      || state.projects.find((project) => project.available);
    if (!initial) throw new Error("No server projects are available.");
    setProject(initial.slug);
    elements.transcript.innerHTML = `<p class="empty-state">${escapeText(initial.name)} ready.</p>`;
  } catch (error) {
    elements.contextPath.textContent = "Disconnected";
    elements.input.disabled = true;
    elements.runButton.disabled = true;
    elements.transcript.innerHTML = "";
    const message = document.createElement("p");
    message.className = "empty-state";
    message.textContent = error.message;
    elements.transcript.append(message);
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const command = elements.input.value.trim();
  if (!command || state.running || !selectedProject()) return;
  state.history.push(command);
  state.historyIndex = state.history.length;
  elements.input.value = "";
  execute(command);
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "ArrowUp" && state.history.length) {
    event.preventDefault();
    state.historyIndex = Math.max(0, state.historyIndex - 1);
    elements.input.value = state.history[state.historyIndex] || "";
  } else if (event.key === "ArrowDown" && state.history.length) {
    event.preventDefault();
    state.historyIndex = Math.min(state.history.length, state.historyIndex + 1);
    elements.input.value = state.history[state.historyIndex] || "";
  }
});

elements.clearButton.addEventListener("click", () => {
  elements.transcript.innerHTML = `<p class="empty-state">${escapeText(selectedProject()?.name || "Terminal")} ready.</p>`;
  elements.input.focus();
});

initialize();
