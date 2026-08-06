# Shared DeveloperOS targets for every managed project.
#
# This file is loaded through GNU Make's MAKEFILES environment variable. The
# context and Git targets apply to every repository. Public Docker targets are
# owned here; project Makefiles may provide project-specific targets and
# configure the shared targets through docker-config.

-include docker-config

APP_NAME ?= app
IMAGE_NAME ?= app
BINARY_NAME ?= server
BINARY_GO ?= app
DOCKERHUB_USERNAME ?= user
DOCKERHUB_IMAGE ?= app
DOCKERHUB_TAG ?= latest
DB_CONTAINER ?= db
POSTGRES_USER ?= user
PORT_APP ?= 8080
PORT_DB ?= 5432

DEVOS_COMPOSE_FILE ?= $(firstword $(wildcard docker-compose.yml compose.yml docker-compose.yaml compose.yaml))
DEVOS_BUILD_COMPOSE_FILE ?= $(DEVOS_COMPOSE_FILE)
DEVOS_IMAGE_BUILD_COMPOSE_FILE ?= $(or $(firstword $(wildcard docker-compose.build.yml compose.build.yml docker-compose.build.yaml compose.build.yaml)),$(DEVOS_BUILD_COMPOSE_FILE))
DEVOS_COMPOSE_ENV ?= $(if $(wildcard docker-config),--env-file docker-config) $(if $(wildcard .env),--env-file .env)
DEVOS_COMPOSE = $(strip docker compose $(DEVOS_COMPOSE_ENV) $(if $(DEVOS_COMPOSE_FILE),-f $(DEVOS_COMPOSE_FILE)))
DEVOS_BUILD_COMPOSE = $(strip docker compose $(DEVOS_COMPOSE_ENV) $(if $(DEVOS_BUILD_COMPOSE_FILE),-f $(DEVOS_BUILD_COMPOSE_FILE)))
DEVOS_IMAGE_BUILD_COMPOSE = $(strip docker compose $(DEVOS_COMPOSE_ENV) $(if $(DEVOS_IMAGE_BUILD_COMPOSE_FILE),-f $(DEVOS_IMAGE_BUILD_COMPOSE_FILE)))
DEVOS_RUN_UP_FLAGS ?= up --no-build
DEVOS_IMAGE_PUSH_TARGET ?= developeros-image-push
DEVOS_PULL_IMAGE ?= $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)
DEVOS_PULL_LOCAL_IMAGE ?=
DEVOS_DEPLOY_TARGET ?=
DEVOS_SYNC_PUSH_TARGET ?=
DEVOS_DEPLOY_SYNC ?= none
DEVOS_DEPLOY_GIT_REMOTE ?= origin
DEVOS_DEPLOY_GIT_BRANCH ?= main
DEVELOPEROS_GIT_DASHBOARD ?= X:/Projects/DeveloperOS/04_Tools/git/Invoke-GitDashboard.ps1
DEVELOPEROS_DEPLOY_GIT ?= X:/Projects/DeveloperOS/04_Tools/make/Invoke-DeveloperOSDeployGit.ps1
DEVELOPEROS_CONTEXT_TOOL ?= X:/Projects/DeveloperOS/04_Tools/context/project_context.py
DEVOS_CONTEXT_PYTHON ?= python
CONTEXT_LIMIT ?= 30
CONTEXT_FORMAT ?= text
CONTEXT_REFRESH ?= 0

define DEVELOPEROS_REQUIRE_COMPOSE
$(if $(DEVOS_COMPOSE_FILE),,$(error No Docker Compose file configured in $(CURDIR). Add a standard Compose file or set DEVOS_COMPOSE_FILE in docker-config))
endef

define DEVELOPEROS_REQUIRE_BUILD_COMPOSE
$(if $(DEVOS_BUILD_COMPOSE_FILE),,$(error No Docker build Compose file configured in $(CURDIR). Set DEVOS_BUILD_COMPOSE_FILE in docker-config))
endef

define DEVELOPEROS_REQUIRE_IMAGE_BUILD_COMPOSE
$(if $(DEVOS_IMAGE_BUILD_COMPOSE_FILE),,$(error No image build Compose file configured in $(CURDIR). Set DEVOS_IMAGE_BUILD_COMPOSE_FILE in docker-config))
endef

define DEVELOPEROS_REQUIRE_DEPLOY_TARGET
$(if $(strip $(DEVOS_DEPLOY_TARGET)),,$(error Deployment is not configured in $(CURDIR). Set DEVOS_DEPLOY_TARGET to a project-owned deployment target))
$(if $(filter deploy,$(strip $(DEVOS_DEPLOY_TARGET))),$(error DEVOS_DEPLOY_TARGET must not point to the shared deploy target),)
$(if $(filter none after-deploy,$(strip $(DEVOS_DEPLOY_SYNC))),,$(error DEVOS_DEPLOY_SYNC must be none or after-deploy))
$(if $(and $(filter after-deploy,$(strip $(DEVOS_DEPLOY_SYNC))),$(strip $(DEVOS_SYNC_PUSH_TARGET))),,$(if $(filter after-deploy,$(strip $(DEVOS_DEPLOY_SYNC))),$(error DEVOS_DEPLOY_SYNC=after-deploy requires DEVOS_SYNC_PUSH_TARGET),))
endef

define DEVELOPEROS_REQUIRE_SYNC_TARGET
$(if $(filter sync,$(strip $(DEVOS_SYNC_PUSH_TARGET))),$(error DEVOS_SYNC_PUSH_TARGET must not point to the shared sync target),)
endef

.PHONY: git-check context

git-check:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(DEVELOPEROS_GIT_DASHBOARD)"

context:
	@$(DEVOS_CONTEXT_PYTHON) "$(DEVELOPEROS_CONTEXT_TOOL)" --project-root "$(CURDIR)" $(if $(strip $(TASK)),--task "$(TASK)",) $(if $(strip $(AREA)),--area "$(AREA)",) --limit "$(CONTEXT_LIMIT)" --format "$(CONTEXT_FORMAT)" $(if $(filter 1 true yes,$(CONTEXT_REFRESH)),--refresh,)

.PHONY: developeros-help run b-run run-b up down logs docker-build docker-stop docker-logs docker-clean rebuild dh-tag dh-push dh-pull dh-b-push developeros-image-build developeros-image-push server-deploy sync deploy db-%

developeros-help:
	@echo "DeveloperOS shared targets"
	@echo "  make git-check      Show end-of-day Git dashboard"
	@echo "  make context TASK=...  Select task-relevant project context"
	@echo "  make run            Start with existing images (foreground)"
	@echo "  make b-run          Build once, then start without another build"
	@echo "  make run-b          Alias for b-run"
	@echo "  make up             Start with existing images (background)"
	@echo "  make down           Stop Docker Compose and remove orphans"
	@echo "  make logs           Follow Docker Compose logs"
	@echo "  make docker-build   Build Docker Compose services"
	@echo "  make rebuild        Stop, build once, and start services"
	@echo "  make dh-b-push      Build, tag, and push Docker Hub image"
	@echo "  make dh-pull        Pull Docker Hub image"
	@echo "  make sync           Push an explicitly configured data set to the server"
	@echo "  make deploy         Push committed Git work, deploy, then optionally sync"

run:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVOS_COMPOSE) $(DEVOS_RUN_UP_FLAGS)

b-run:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(MAKE) --no-print-directory docker-build
	$(DEVOS_COMPOSE) up --no-build

run-b: b-run

up:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVOS_COMPOSE) up -d --no-build

down:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVOS_COMPOSE) down --remove-orphans

logs:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVOS_COMPOSE) logs -f

docker-build:
	$(DEVELOPEROS_REQUIRE_BUILD_COMPOSE)
	$(DEVOS_BUILD_COMPOSE) build

docker-stop: down

docker-logs: logs

docker-clean: down
	@echo "Project stack removed; reusable images and volumes were preserved."

rebuild:
	$(MAKE) --no-print-directory down
	$(MAKE) --no-print-directory docker-build
	$(MAKE) --no-print-directory up

dh-tag:
	docker tag $(IMAGE_NAME) $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-push: dh-tag
	docker push $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-pull:
	docker pull $(DEVOS_PULL_IMAGE)
	$(if $(strip $(DEVOS_PULL_LOCAL_IMAGE)),docker tag $(DEVOS_PULL_IMAGE) $(DEVOS_PULL_LOCAL_IMAGE),@echo Image pull complete.)

developeros-image-build:
	$(DEVELOPEROS_REQUIRE_IMAGE_BUILD_COMPOSE)
	$(DEVOS_IMAGE_BUILD_COMPOSE) build

developeros-image-push: developeros-image-build dh-tag
	docker push $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-b-push:
	$(MAKE) --no-print-directory $(DEVOS_IMAGE_PUSH_TARGET)

server-deploy: dh-pull up

sync:
	$(DEVELOPEROS_REQUIRE_SYNC_TARGET)
	$(if $(strip $(DEVOS_SYNC_PUSH_TARGET)),$(MAKE) --no-print-directory $(DEVOS_SYNC_PUSH_TARGET),@echo "Data synchronization is not configured for this project; skipped.")

deploy:
	$(DEVELOPEROS_REQUIRE_DEPLOY_TARGET)
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(DEVELOPEROS_DEPLOY_GIT)" -Remote "$(DEVOS_DEPLOY_GIT_REMOTE)" -Branch "$(DEVOS_DEPLOY_GIT_BRANCH)"
	$(MAKE) --no-print-directory $(DEVOS_DEPLOY_TARGET)
	$(if $(filter after-deploy,$(strip $(DEVOS_DEPLOY_SYNC))),$(MAKE) --no-print-directory sync,@echo "Post-deploy data synchronization is not enabled; skipped.")

db-%:
	docker exec -it $(DB_CONTAINER) psql -U $(POSTGRES_USER) -d $*
