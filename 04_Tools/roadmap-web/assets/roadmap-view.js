(function initializeDeveloperOSRoadmapView(global) {
  "use strict";

  const VERSION = "2.0.0";

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
    if (item.status !== "Blocked") return "";
    return {
      Operator: "blocker-operator",
      Processing: "blocker-processing",
      Future: "blocker-future",
    }[item.blocker_type] || "";
  }

  function detailItems(topic) {
    if (Array.isArray(topic.items) && topic.items.length) return topic.items;
    const status = statusFamily(topic.status) === "prohibited"
      ? "Prohibited"
      : statusFamily(topic.status) === "blocked"
        ? "Blocked"
        : statusFamily(topic.status) === "done"
          ? "Done"
          : "In Progress";
    return [
      {
        item: "Completion signal",
        status,
        blocker_type: status === "Blocked" ? "Processing" : "None",
        description: topic.completion_signal,
      },
      {
        item: "Next transition",
        status,
        blocker_type: status === "Blocked" ? "Future" : "None",
        description: topic.next_transition,
      },
    ];
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

    const milestone = project.milestone || {};
    const latest = project.latest_status_change || {};
    const topics = project.topics || [];
    container.innerHTML = `
      <section class="roadmap-hero">
        <div class="roadmap-title-block">
          <p class="roadmap-eyebrow">UPDATED ${escapeHtml(project.updated_at)}</p>
          <h2>${escapeHtml(project.title)}</h2>
          <p>${escapeHtml(project.direction)}</p>
        </div>
        <aside class="roadmap-legend" aria-label="Roadmap presentation legend">
          <h3>Item status</h3>
          <div class="roadmap-legend-grid">
            ${statusLegendItem("Done", "done")}
            ${statusLegendItem("In progress", "in-progress")}
            ${statusLegendItem("Blocked", "blocked")}
            ${statusLegendItem("Prohibited", "prohibited")}
          </div>
          <h3 class="roadmap-legend-subtitle">Bottleneck type</h3>
          <div class="roadmap-legend-grid roadmap-blocker-legend">
            ${blockerLegendItem("Operator response", "operator")}
            ${blockerLegendItem("Processing", "processing")}
            ${blockerLegendItem("Future evidence", "future")}
          </div>
        </aside>
      </section>

      <section class="roadmap-milestone-strip">
        <div><span>Current milestone</span><strong>${escapeHtml(milestone.objective)}</strong></div>
        <div><span>Status</span><b class="roadmap-inline-status ${statusFamily(milestone.status)}">${escapeHtml(milestone.status)}</b></div>
        <div><span>Completion signal</span><strong>${escapeHtml(milestone.completion_signal)}</strong></div>
      </section>

      <section class="roadmap-stage-section">
        <div class="roadmap-band-heading"><h3>Roadmap stages</h3><span>${escapeHtml(topics.length)} stages</span></div>
        <div class="roadmap-stage-scroll">
          <div class="roadmap-stage-track" role="list">
            ${topics.map((topic, index) => `
              <article class="roadmap-stage ${statusFamily(topic.status)}" role="listitem">
                <div class="roadmap-stage-card">
                  <span class="roadmap-stage-number" aria-hidden="true">${index + 1}</span>
                  <h4>${escapeHtml(topic.topic)}</h4>
                  <span class="roadmap-stage-status">${escapeHtml(topic.status)}</span>
                </div>
                <div class="roadmap-stage-items">
                  ${detailItems(topic).map(renderDetailItem).join("")}
                </div>
              </article>
            `).join("")}
          </div>
        </div>
      </section>

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
