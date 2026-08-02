# Docker Image Build Minimization Policy

## Purpose

This policy keeps Docker image builds intentional, cached, and uncommon across
DeveloperOS-governed projects. Starting, restarting, testing, or inspecting an
existing stack must not silently rebuild images.

## Default Lifecycle Contract

Routine lifecycle commands reuse existing images:

- `make run` starts the standard stack in the foreground with `--no-build`.
- `make up` starts the standard stack in the background with `--no-build`.
- Restart, status, log, and one-shot runtime commands do not build images.
- Project-specific Compose `up` commands must state `--no-build` explicitly.

If a required image is missing, the routine command must fail clearly. Use an
explicit build command instead of making every normal start a possible build.

## Explicit Build Contract

Builds are allowed only at a named build or release boundary:

- `make docker-build` performs one cached Compose build without starting the
  stack.
- `make b-run` performs one cached build and then starts with `--no-build`.
- `make rebuild` stops the stack, performs one cached build, and starts with
  `--no-build`.
- A project-specific stack uses the same shape: a `*-build` target and a
  `*-b-run` or `*-rebuild` target that builds once before a no-build start.
- Image publication and deployment commands may build an immutable image for
  the exact release revision.

Do not combine normal startup with `docker compose up --build`. Separating the
build from startup makes the build decision visible and prevents a second build
request during the same operation.

## When A Build Is Required

Build when at least one of these conditions is true:

- The required image does not exist locally or has the wrong architecture.
- A Dockerfile, `.dockerignore`, build target, base image selection, build
  argument, or operating-system package list changed.
- A dependency or lock file copied into the image changed.
- Source or generated artifacts copied into the image changed and are not
  supplied through a bind mount at runtime.
- An explicit immutable release image must be produced for a new revision.

A build is normally unnecessary for:

- Source changes delivered through a development bind mount.
- Runtime environment or configuration changes read when a container starts.
- Container restart, status, logs, database access, or other operational work.
- Documentation-only changes.

Inspect the Compose `build`, `image`, and `volumes` definitions when the correct
choice is unclear.

## Cache And Cleanup Rules

- Keep Docker's build cache enabled. Do not use `--no-cache` by default.
- Do not add `--pull` to routine local builds. Refresh base images only during
  deliberate dependency or release maintenance.
- Preserve reusable images and volumes during ordinary cleanup. Do not run
  system-wide image pruning as part of a project lifecycle target.
- Use destructive pruning only as an explicit disk-recovery operation after
  confirming what will be removed.

## Deployment Rule

Deployment is an explicit release boundary. It may build and publish one
immutable image for the exact Git revision, or pull that image when it already
exists. Compose must deploy the selected image with `--no-build`; databases and
other durable services must not be rebuilt merely because the application is
released.

## Enforcement

`04_Tools/make/DeveloperOS.mk` owns the shared lifecycle behavior.
`make docker-policy-check` statically checks DeveloperOS, OA, Gaia, and bTest
for ambiguous Compose starts, build-on-start commands, unsafe cache bypass, and
system-wide pruning. `make make-check` runs the same policy check after the
shared Make contract test.

Project exceptions must be narrow, explicit in `PROJECT_RULES.md`, and explain
why no-build startup cannot apply. Convenience is not an exception.

## DeveloperOS Self-Application

DeveloperOS has no root Docker Compose application. Its console runs directly
under Python during development and systemd in deployment, so its routine image
build count is zero. This is the strongest applicable form of the policy, not
an excuse to create a placeholder container. If a root container application is
added later, it must adopt the shared no-build lifecycle contract.
