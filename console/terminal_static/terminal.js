const state = {
  projects: [],
  selectedProject: "",
  socket: null,
  terminal: null,
  fitAddon: null,
};

const elements = {
  projectTabs: document.querySelector("#project-tabs"),
  contextPath: document.querySelector("#context-path"),
  terminalViewport: document.querySelector("#terminal-viewport"),
  connection: document.querySelector("#connection-state"),
  copyButton: document.querySelector("#copy-button"),
  pasteButton: document.querySelector("#paste-button"),
  clearButton: document.querySelector("#clear-button"),
};

function showActionResult(button, label) {
  const original = button.dataset.label || button.textContent;
  button.dataset.label = original;
  button.textContent = label;
  window.setTimeout(() => {
    button.textContent = original;
    delete button.dataset.label;
  }, 1200);
}

async function writeClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard copy is unavailable.");
}

async function copySelection() {
  const selection = state.terminal?.getSelection() || "";
  if (!selection) {
    showActionResult(elements.copyButton, "Select text");
    state.terminal?.focus();
    return;
  }
  try {
    await writeClipboard(selection);
    showActionResult(elements.copyButton, "Copied");
  } catch {
    showActionResult(elements.copyButton, "Copy failed");
  } finally {
    state.terminal?.focus();
  }
}

async function pasteClipboard() {
  try {
    if (!navigator.clipboard?.readText) throw new Error("Clipboard paste is unavailable.");
    const text = await navigator.clipboard.readText();
    if (text) state.terminal.paste(text);
    showActionResult(elements.pasteButton, text ? "Pasted" : "Clipboard empty");
  } catch {
    showActionResult(elements.pasteButton, "Paste blocked");
  } finally {
    state.terminal?.focus();
  }
}

function selectedProject() {
  return state.projects.find((project) => project.slug === state.selectedProject);
}

function setConnection(label, connected) {
  elements.connection.lastChild.textContent = ` ${label}`;
  elements.connection.classList.toggle("connected", connected);
}

function send(message) {
  if (state.socket?.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify(message));
  }
}

function sendSize() {
  send({type: "resize", columns: state.terminal.cols, rows: state.terminal.rows});
}

function connectProject(project) {
  if (state.socket) {
    state.socket.close(1000, "Project changed");
  }
  state.terminal.reset();
  state.terminal.writeln(`Connecting to ${project.name}...`);
  setConnection("Connecting", false);

  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${scheme}//${window.location.host}/api/terminal?project=${encodeURIComponent(project.slug)}`;
  const socket = new WebSocket(url);
  socket.binaryType = "arraybuffer";
  state.socket = socket;

  socket.addEventListener("open", () => {
    if (state.socket !== socket) return;
    state.terminal.reset();
    setConnection("PTY connected", true);
    sendSize();
    state.terminal.focus();
  });
  socket.addEventListener("message", (event) => {
    if (state.socket !== socket) return;
    state.terminal.write(event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data);
  });
  socket.addEventListener("close", () => {
    if (state.socket !== socket) return;
    setConnection("Disconnected", false);
    state.terminal.writeln("\r\n[Terminal session closed]");
  });
  socket.addEventListener("error", () => {
    if (state.socket !== socket) return;
    setConnection("Connection failed", false);
  });
}

function setProject(slug) {
  const project = state.projects.find((item) => item.slug === slug && item.available);
  if (!project || state.selectedProject === project.slug && state.socket?.readyState === WebSocket.OPEN) return;
  state.selectedProject = project.slug;
  elements.projectTabs.querySelectorAll(".project-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.project === project.slug);
  });
  elements.contextPath.textContent = `/projects/${project.slug}`;
  const url = new URL(window.location.href);
  url.searchParams.set("project", project.slug);
  window.history.replaceState(null, "", url);
  connectProject(project);
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

function initializeTerminal() {
  state.terminal = new Terminal({
    cursorBlink: false,
    cursorStyle: "block",
    cursorInactiveStyle: "block",
    fontFamily: '"Cascadia Mono", Consolas, "Liberation Mono", monospace',
    fontSize: 14,
    lineHeight: 1.15,
    scrollback: 5000,
    theme: {
      background: "#0b0e11",
      foreground: "#d5dad8",
      cursor: "#4ad69a",
      cursorAccent: "#0b0e11",
      selectionBackground: "#285f4a",
    },
  });
  state.fitAddon = new FitAddon.FitAddon();
  state.terminal.loadAddon(state.fitAddon);
  state.terminal.open(elements.terminalViewport);
  state.fitAddon.fit();
  state.terminal.attachCustomKeyEventHandler((event) => {
    if (event.type !== "keydown") return true;
    const commandModifier = event.ctrlKey || event.metaKey;
    const copyShortcut = commandModifier && event.shiftKey && event.code === "KeyC"
      || event.ctrlKey && !event.shiftKey && event.code === "Insert";
    const pasteShortcut = commandModifier && event.shiftKey && event.code === "KeyV"
      || event.shiftKey && !event.ctrlKey && event.code === "Insert";
    if (copyShortcut) {
      void copySelection();
      return false;
    }
    if (pasteShortcut) {
      void pasteClipboard();
      return false;
    }
    return true;
  });
  state.terminal.onData((data) => send({type: "input", data}));
  state.terminal.onResize(() => sendSize());
  new ResizeObserver(() => state.fitAddon.fit()).observe(elements.terminalViewport);
}

async function initialize() {
  initializeTerminal();
  try {
    const response = await fetch("/api/session", {cache: "no-store"});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Could not open terminal session.");
    state.projects = body.projects || [];
    renderProjects();
    const requested = new URLSearchParams(window.location.search).get("project");
    const initial = state.projects.find((project) => project.slug === requested && project.available)
      || state.projects.find((project) => project.available);
    if (!initial) throw new Error("No server projects are available.");
    setProject(initial.slug);
  } catch (error) {
    elements.contextPath.textContent = "Disconnected";
    setConnection("Unavailable", false);
    state.terminal.writeln(`\r\n${error.message}`);
  }
}

elements.clearButton.addEventListener("click", () => {
  state.terminal.clear();
  state.terminal.focus();
});
elements.copyButton.addEventListener("click", () => void copySelection());
elements.pasteButton.addEventListener("click", () => void pasteClipboard());

window.addEventListener("beforeunload", () => state.socket?.close());

initialize();
