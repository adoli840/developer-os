# Shared Roadmap Web Presentation

## Purpose

This directory is the canonical, framework-neutral browser presentation for
DeveloperOS-governed roadmaps. DeveloperOS and project-local `/roadmap` routes
must use the same versioned assets so the same canonical roadmap has the same
structure, colors, blocker signals, hover descriptions, and responsive
behavior in both locations.

Projects continue to own their roadmap content and parsing adapters.
DeveloperOS owns the common presentation contract and assets.

The default view is progress-card first: project and track navigation stays
outside the renderer, large cards begin immediately below it, and the compact
legend follows the cards. Canonical title, direction, update, and milestone
fields remain available to planning tools but are not rendered above progress.

## Version

The current browser bundle is `3.0.0` and consists of:

- `assets/roadmap-view.js`
- `assets/roadmap-view.css`

Do not modify vendored copies inside an individual project. Change the
canonical assets here, verify them, then reinstall the bundle in each project.

## Data Contract

The renderer accepts the public roadmap object produced by the DeveloperOS
console parser. Each `topics` entry may include:

```json
{
  "topic": "Verified release",
  "status": "In Progress",
  "completion_signal": "The release passes focused verification.",
  "next_transition": "Move to Done after observation.",
  "items": [
    {
      "item": "Release verification",
      "status": "In Progress",
      "blocker_type": "None",
      "description": "Run the focused release checks and retain their evidence."
    }
  ]
}
```

Item status is exactly `Done`, `In Progress`, `Blocked`, or `Prohibited`.
Blocked items use exactly one blocker type: `Operator`, `Processing`, or
`Future`. Other items use `None`.

The canonical Markdown source declares these values in the optional
`Roadmap Details` table defined by
`00_Master/ProjectRoadmapPolicy.md`. Legacy roadmaps remain readable, but the
renderer does not show synthetic completion-signal or next-transition items.
Projects adopting this presentation must declare every material sibling item
explicitly.

## Linked Track Contract

Multi-track projects use `ROADMAPS.json` schema version 2. Every track declares
the root overview topic it expands:

```json
{
  "schema_version": 2,
  "tracks": [
    {
      "slug": "delivery",
      "name": "Delivery",
      "path": "docs/roadmaps/delivery.md",
      "overview_topic": "Delivery"
    }
  ]
}
```

The mapped Overall detail rows must exactly match the linked track topics in
count, order, name, presentation status, and description. Description is the
track topic's completion signal. The parser adds the shared fields below to
each linked track topic so its large card is the same card shown compactly in
Overall:

```json
{
  "topic": "Verified release",
  "status": "Planned",
  "display_status": "In Progress",
  "blocker_type": "None",
  "description": "The release passes focused verification."
}
```

Schema version 1 remains readable during migration, but it represents
independent overview and track summaries and does not guarantee parity.

## Installation

From DeveloperOS on Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\04_Tools\roadmap-web\Install-RoadmapWebAssets.ps1 -ProjectPath X:\Projects\gaia -Destination public\developer-os-roadmap
```

Use the destination appropriate to the project's static-file framework. For a
Go embedded-static application, the destination may instead be a repository
static directory such as `static\developer-os-roadmap`.

Verify that a project copy is byte-for-byte current:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\04_Tools\roadmap-web\Install-RoadmapWebAssets.ps1 -ProjectPath X:\Projects\gaia -Destination public\developer-os-roadmap -Check
```

## Project Integration

1. Parse the project-owned canonical roadmap into the shared public data
   contract, including every `Roadmap Details` row and schema version 2 track
   linkage.
2. Serve the two installed assets unchanged.
3. Load the CSS, then the JavaScript, on the project `/roadmap` page.
4. Call `DeveloperOSRoadmapView.renderDetail(container, roadmap)`.
5. Keep project and track navigation directly above and outside the renderer.
   Do not add a visible title, summary strip, direction, or milestone block
   between the tabs and cards.
6. Do not recreate the roadmap stage or item markup in a project template.
7. Test linked-card parity, desktop and mobile layout, keyboard focus, pointer
   hover, HTML escaping, and asset hash parity.

The renderer is read-only and escapes all text fields before inserting them
into the document.
