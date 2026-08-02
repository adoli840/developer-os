# Shared DeveloperOS make targets for Docker Compose projects.
#
# This file is loaded through GNU Make's MAKEFILES environment variable. Public
# Docker targets are owned here; project Makefiles may provide project-specific
# targets and configure the shared targets through docker-config.

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
DEVOS_IMAGE_PUSH_TARGET ?= developeros-image-push
DEVOS_PULL_IMAGE ?= $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)
DEVOS_PULL_LOCAL_IMAGE ?=
DEVELOPEROS_GIT_DASHBOARD ?= X:/Projects/DeveloperOS/04_Tools/git/Invoke-GitDashboard.ps1

define DEVELOPEROS_REQUIRE_COMPOSE
$(if $(DEVOS_COMPOSE_FILE),,$(error No Docker Compose file configured in $(CURDIR). Add a standard Compose file or set DEVOS_COMPOSE_FILE in docker-config))
endef

define DEVELOPEROS_REQUIRE_BUILD_COMPOSE
$(if $(DEVOS_BUILD_COMPOSE_FILE),,$(error No Docker build Compose file configured in $(CURDIR). Set DEVOS_BUILD_COMPOSE_FILE in docker-config))
endef

define DEVELOPEROS_REQUIRE_IMAGE_BUILD_COMPOSE
$(if $(DEVOS_IMAGE_BUILD_COMPOSE_FILE),,$(error No image build Compose file configured in $(CURDIR). Set DEVOS_IMAGE_BUILD_COMPOSE_FILE in docker-config))
endef

.PHONY: git-check

git-check:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(DEVELOPEROS_GIT_DASHBOARD)"

.PHONY: developeros-help run b-run run-b up down logs docker-build docker-stop docker-logs docker-clean rebuild dh-tag dh-push dh-pull dh-b-push developeros-image-build developeros-image-push server-deploy db-%

developeros-help:
	@echo "DeveloperOS shared Docker targets"
	@echo "  make git-check      Show end-of-day Git dashboard"
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

run:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVOS_COMPOSE) up --no-build

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

db-%:
	docker exec -it $(DB_CONTAINER) psql -U $(POSTGRES_USER) -d $*
