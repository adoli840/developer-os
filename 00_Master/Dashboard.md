# Master Dashboard

## Purpose

This dashboard provides a workspace-level overview of DeveloperOS operating mode and current governance focus.

It is not a project management database. Project repositories own their own current status, roadmap, TODO, and implementation state.

## Current Operating Mode

The workspace is currently in **inspection-first mode**.

The priority is not new feature development. The priority is to make the active project base stable, understandable, convenient, and efficient before expanding it.

## AI Project Manager Mode

DeveloperOS should act as an AI Project Manager when invoked.

It should review DeveloperOS governance documents and project-owned context before recommending what to work on next.

DeveloperOS should not pressure the developer. It should provide objective evidence, soft challenges, and clear recommendations. The developer always makes the final decision.

## Current Objectives

- Inspect active projects for structural or operational issues.
- Improve developer convenience and workflow efficiency.
- Clarify README files, setup steps, configuration, and verification methods.
- Reduce duplicated features and unnecessary complexity.
- Defer new feature work until inspection results and priorities are clear.
- Build PM-style visibility into governance alignment without duplicating project-owned state.

## Workspace State

Discarded projects have been removed. `X:\Projects` is now organized around maintained project repositories and the `DeveloperOS` governance repository.

`DeveloperOS` is the dedicated Git repository for development operations. Application projects remain outside DeveloperOS and keep their own independence.

## Project Index

The project index should stay lightweight. It may point to active project repositories, but detailed status belongs inside each project.

| Project | Repository | Governance Notes |
|---|---|---|
| TBD | TBD | Fill only when the reference helps workspace-level decisions |

## Active Priorities

1. Stabilize DeveloperOS.
2. Inspect active projects.
3. Identify convenience and efficiency improvements.
4. Verify setup, execution, test, and documentation quality.
5. Use inspection results to refine governance and project-local priorities.
6. Establish Roadmap, ProjectStatus, Metrics, and DailyReview as PM inputs.

## PM Documents

- `PM_Role.md`
- `GitDashboard.md`
- `Roadmap.md`
- `ProjectStatus.md`
- `Metrics.md`
- `DailyReview.md`
- `WeeklyPlan.md`

## Operational Dashboards

- `GitDashboard.md`: end-of-day Git status dashboard for DeveloperOS, Gaia Project, bTest, and OA

## Synchronization Visibility

Git synchronization and project data synchronization must be shown as separate
concepts. Git reports source revision and working-tree state. A project data
contract may additionally report derived synchronization evidence:

- Synchronization set and mode
- Authority or merge-safe classification
- Local-only, remote-only, and conflict counts
- Last verified manifest identity and time
- Last transfer direction and result

DeveloperOS must not copy project payloads, expose credentials or private paths,
or provide unrestricted public transfer controls. Projects without an explicit
data synchronization contract show no data synchronization state.

