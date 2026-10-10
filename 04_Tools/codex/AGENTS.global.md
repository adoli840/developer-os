<!-- BEGIN DEVELOPEROS MANAGED GUIDANCE -->
# DeveloperOS Workspace Guidance

For the DeveloperOS repository and projects that explicitly opt in:

- Before meaningful work, opted-in projects read `X:\Projects\DeveloperOS\BOOT.md`
  and follow its task routing and precedence rules. Independent projects use
  their own local instructions.
- When an opted-in repository has `PROJECT_AREAS.json`, it may run
  `make context TASK="<current request>"` before broad source inspection. Start
  with the selected files and expand only when a real dependency crosses the
  declared area.
- For opted-in Docker, Compose, image, deployment, or container lifecycle work, read
  `X:\Projects\DeveloperOS\00_Master\DockerImageBuildPolicy.md`. Routine
  starts and restarts must reuse existing images with `--no-build`; build only
  at an explicit build or immutable release boundary.
- Opted-in projects treat
  `X:\Projects\DeveloperOS\00_Master\ProjectRoadmapPolicy.md` as the
  roadmap status-transition rule.
- Before meaningful work in an opted-in project, read
  `X:\Projects\DeveloperOS\02_AI\ModelRoutingPolicy.md` and record a
  `Luna`, `Luna to Sol`, or `Sol` recommendation with its reason and review
  boundary, plus the route sequence for each natural work stage.
  Project-local rules may raise the minimum route.
- For high-impact or high-reversal-cost work in an opted-in project, read
  `X:\Projects\DeveloperOS\02_AI\DevelopmentProtocol.md` and apply the
  GPT-User-Codex seven-step protocol. Small, clear, reversible changes may use
  the abbreviated path described there.
- For multi-stage work in an opted-in project, present the route sequence first. Ask the developer to
  confirm a model change with `luna` or `sol`, complete the useful work for the
  confirmed route, and request the next confirmation only at a natural
  handoff boundary. Optimize work order, not the number of model changes.
- Opted-in projects evaluate roadmap transitions after meaningful work without waiting for a
  separate request. Update the canonical roadmap only when a topic's status,
  scope, priority, completion signal, or material blocker changes. Use an
  existing project-specific roadmap or generator before creating a root
  `ROADMAP.md`.
- Keep project state in the project repository. Do not copy project roadmaps
  into DeveloperOS.

These defaults do not apply to independent projects. Project-local
instructions may choose a stricter process or a different canonical roadmap.
<!-- END DEVELOPEROS MANAGED GUIDANCE -->
