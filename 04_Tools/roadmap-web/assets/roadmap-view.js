(function initializeDeveloperOSRoadmapView(global) {
  "use strict";

  const VERSION = "3.0.1";

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function statusFamily(status) {
    if (status === "Done") return "done";
    if (status === "Blocked" || status === "Paused") return "blocked";
    if (status === "Prohibited" || status === "Cancelled") return "prohibited";
    return "in-progress";
  }

  function blockerClass(item) {
    const status = item.display_status || item.status;
    if (statusFamily(status) !== "blocked") return "";
    return {
      Operator: "blocker-operator",
      Processing: "blocker-processing",
      Future: "blocker-future",
    }[item.blocker_type] || "";
  }

  function detailItems(topic, detailMode) {
    if (detailMode === "derived") return [];
    return Array.isArray(topic.items) ? topic.items : [];
  }

  function statusLegendItem(label, family) {
    return `
      <span class="roadmap-legend-item">
        <i class="roadmap-status-swatch ${family}" aria-hidden="true"></i>
        ${escapeHtml(label)}
      </span>
    `;
  }

  function blockerLegendItem(label, kind) {
    return `
      <span class="roadmap-legend-item">
        <i class="roadmap-blocker-swatch blocker-${kind}" aria-hidden="true"></i>
        ${escapeHtml(label)}
      </span>
    `;
  }

  function orderedList(items) {
    return `<ol class="roadmap-list">${(items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>`;
  }

  function bulletList(items) {
    return `<ul class="roadmap-list">${(items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  }

  function renderDetailItem(item) {
    const description = String(item.description || "No description provided.");
    const family = statusFamily(item.status);
    const blocker = blockerClass(item);
    const ariaLabel = `${item.item}. ${item.status}. ${description}`;
    return `
      <div class="roadmap-detail-item ${family} ${blocker}"
           tabindex="0"
           aria-label="${escapeHtml(ariaLabel)}"
           data-roadmap-description="${escapeHtml(description)}">
        <i class="roadmap-detail-marker" aria-hidden="true"></i>
        <strong>${escapeHtml(item.item)}</strong>
        <span>${escapeHtml(item.status)}</span>
      </div>
    `;
  }

  function renderStage(topic, index, detailMode) {
    const status = topic.display_status || topic.status;
    const description = String(
      topic.description || topic.completion_signal || "No description provided.",
    );
    const blocker = blockerClass({
      status,
      blocker_type: topic.blocker_type,
    });
    const ariaLabel = `${topic.topic}. ${status}. ${description}`;
    return `
      <article class="roadmap-stage ${statusFamily(status)}" role="listitem">
        <div class="roadmap-stage-card ${blocker}"
             tabindex="0"
             aria-label="${escapeHtml(ariaLabel)}"
             data-roadmap-description="${escapeHtml(description)}">
          <span class="roadmap-stage-number" aria-hidden="true">${index + 1}</span>
          <h4>${escapeHtml(topic.topic)}</h4>
          <span class="roadmap-stage-status">${escapeHtml(status)}</span>
        </div>
        <div class="roadmap-stage-items">
          ${detailItems(topic, detailMode).map(renderDetailItem).join("")}
        </div>
      </article>
    `;
  }

  function bindDescriptionTooltips(container) {
    let tooltip = document.querySelector(".roadmap-hovercard");
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.className = "roadmap-hovercard";
      tooltip.setAttribute("role", "tooltip");
      document.body.appendChild(tooltip);
    }

    const hide = () => tooltip.classList.remove("visible");
    const show = (target) => {
      tooltip.textContent = target.dataset.roadmapDescription || "";
      tooltip.classList.add("visible");
      const targetRect = target.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      const left = Math.max(
        12,
        Math.min(targetRect.left, window.innerWidth - tooltipRect.width - 12),
      );
      let top = targetRect.bottom + 8;
      if (top + tooltipRect.height > window.innerHeight - 12) {
        top = Math.max(12, targetRect.top - tooltipRect.height - 8);
      }
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    };

    container.querySelectorAll("[data-roadmap-description]").forEach((item) => {
      item.addEventListener("mouseenter", () => show(item));
      item.addEventListener("mouseleave", hide);
      item.addEventListener("focus", () => show(item));
      item.addEventListener("blur", hide);
    });
  }

  function renderDetail(container, project) {
    if (!container) throw new Error("A roadmap container is required.");
    container.classList.add("devos-roadmap-view");
    if (!project) {
      container.innerHTML = `<section class="roadmap-empty"><h2>No projects configured</h2></section>`;
      return;
    }
    if (project.state !== "available") {
      const label = project.state === "missing" ? "Not available" : "Format mismatch";
      container.innerHTML = `
        <section class="roadmap-empty">
          <div>
            <p class="roadmap-eyebrow">${escapeHtml(project.name)}</p>
            <h2>Standard roadmap view unavailable</h2>
            <p class="roadmap-muted">${escapeHtml(project.message)}</p>
          </div>
          <span class="roadmap-inline-status blocked">${escapeHtml(label)}</span>
        </section>
      `;
      return;
    }

    const latest = project.latest_status_change || {};
    const topics = project.topics || [];
    const stageCount = Math.max(topics.length, 1);
    const stageMinWidth = (stageCount * 218) + (Math.max(stageCount - 1, 0) * 18);
    container.innerHTML = `
      <section class="roadmap-stage-section" aria-label="Roadmap progress">
        <div class="roadmap-stage-scroll">
          <div class="roadmap-stage-track" role="list" style="--roadmap-stage-count: ${stageCount}; --roadmap-stage-min-width: ${stageMinWidth}px">
            ${topics.map((topic, index) => renderStage(topic, index, project.detail_mode)).join("")}
          </div>
        </div>
      </section>

      <aside class="roadmap-legend" aria-label="Roadmap presentation legend">
        <div class="roadmap-legend-group">
          <h3>Item status</h3>
          <div class="roadmap-legend-grid">
            ${statusLegendItem("Done", "done")}
            ${statusLegendItem("In progress", "in-progress")}
            ${statusLegendItem("Blocked", "blocked")}
            ${statusLegendItem("Prohibited", "prohibited")}
          </div>
        </div>
        <div class="roadmap-legend-group">
          <h3>Bottleneck type</h3>
          <div class="roadmap-legend-grid roadmap-blocker-legend">
            ${blockerLegendItem("Operator response", "operator")}
            ${blockerLegendItem("Processing", "processing")}
            ${blockerLegendItem("Future evidence", "future")}
          </div>
        </div>
      </aside>

      <div class="roadmap-columns">
        <section class="roadmap-band"><h3>Current priority</h3>${orderedList(project.current_priority)}</section>
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
        <section class="roadmap-band"><h3>Next status transitions</h3>${orderedList(project.next_status_transitions)}</section>
        <section class="roadmap-band"><h3>Risks and blockers</h3>${bulletList(project.risks_and_blockers)}</section>
      </div>
    `;
    bindDescriptionTooltips(container);
  }

  global.DeveloperOSRoadmapView = Object.freeze({VERSION, renderDetail});
}(window));
