# DeveloperOS Repository Guidance

DeveloperOS is both the workspace governance provider and a project repository
governed by its own applicable policies.

Before meaningful work in this repository:

1. Read `BOOT.md`.
2. Read `README.md`, `PROJECT_CONTEXT.md`, and `PROJECT_RULES.md`.
3. Read the canonical `ROADMAP.md` and the task-relevant policy documents routed
   by `BOOT.md`.
4. Run `make context TASK="<current request>"` and begin source inspection from
   the selected DeveloperOS area.

For Docker, Compose, image, deployment, or container lifecycle work, read
`00_Master/DockerImageBuildPolicy.md`. Routine starts and restarts reuse images;
only explicit build or release boundaries may build.

Apply the same roadmap, Git safety, coding, verification, language,
and documentation rules used for other DeveloperOS-governed projects. Use
`PROJECT_RULES.md` only for capabilities that are structurally inapplicable to
DeveloperOS.

Before closing a meaningful work unit:

- Run the relevant focused tests.
- Run `make self-check` when governance, shared tooling, project registration,
  or DeveloperOS operating behavior changed.
- Run `make make-check` when the shared Make contract changed.
- Run `make docker-policy-check` when Docker lifecycle, image, or deployment
  commands changed.
- Evaluate the roadmap status-transition triggers in
  `00_Master/ProjectRoadmapPolicy.md`. Update `ROADMAP.md` only when a topic's
  status, scope, priority, completion signal, or material blocker changed.
