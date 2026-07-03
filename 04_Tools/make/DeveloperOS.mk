# Shared DeveloperOS make targets for Docker Compose projects.
#
# This file is intended to be loaded through GNU Make's MAKEFILES environment
# variable, so individual projects do not need duplicate Makefiles for common
# Docker workflows.

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

DEVELOPEROS_COMPOSE_FILE := $(firstword $(wildcard docker-compose.yml compose.yml docker-compose.yaml compose.yaml))
DEVELOPEROS_COMPOSE_ENV := $(if $(wildcard docker-config),--env-file docker-config) $(if $(wildcard .env),--env-file .env)
DEVELOPEROS_COMPOSE := $(strip docker compose $(DEVELOPEROS_COMPOSE_ENV) $(if $(DEVELOPEROS_COMPOSE_FILE),-f $(DEVELOPEROS_COMPOSE_FILE)))
DEVELOPEROS_LOCAL_MAKEFILE := $(firstword $(wildcard GNUmakefile makefile Makefile))
DEVELOPEROS_GIT_DASHBOARD ?= X:/Projects/DeveloperOS/04_Tools/git/Invoke-GitDashboard.ps1

define DEVELOPEROS_REQUIRE_COMPOSE
$(if $(DEVELOPEROS_COMPOSE_FILE),,$(error No Docker Compose file found in $(CURDIR). Expected docker-compose.yml, compose.yml, docker-compose.yaml, or compose.yaml))
endef

.PHONY: git-check

git-check:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "$(DEVELOPEROS_GIT_DASHBOARD)"

ifeq ($(DEVELOPEROS_LOCAL_MAKEFILE),)

.PHONY: developeros-help run b-run run-b up down logs docker-build docker-stop docker-logs docker-clean rebuild dh-tag dh-push dh-pull dh-b-push server-deploy db-%

developeros-help:
	@echo "DeveloperOS shared Docker targets"
	@echo "  make git-check      Show end-of-day Git dashboard"
	@echo "  make run            Start Docker Compose"
	@echo "  make b-run          Start Docker Compose with build"
	@echo "  make run-b          Alias for b-run"
	@echo "  make up             Start Docker Compose in the background"
	@echo "  make down           Stop Docker Compose and remove orphans"
	@echo "  make logs           Follow Docker Compose logs"
	@echo "  make docker-build   Build Docker Compose services"
	@echo "  make rebuild        Rebuild and restart services"
	@echo "  make dh-b-push      Build, tag, and push Docker Hub image"
	@echo "  make dh-pull        Pull Docker Hub image"

run:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) up

b-run:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) up --build

run-b: b-run

up:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) up -d

down:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) down --remove-orphans

logs:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) logs -f

docker-build:
	$(DEVELOPEROS_REQUIRE_COMPOSE)
	$(DEVELOPEROS_COMPOSE) build

docker-stop: down

docker-logs: logs

docker-clean: down
	docker system prune -af --volumes

rebuild: down docker-build up

dh-tag:
	docker tag $(IMAGE_NAME) $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-push: dh-tag
	docker push $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-pull:
	docker pull $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

dh-b-push: docker-build dh-tag
	docker push $(DOCKERHUB_USERNAME)/$(DOCKERHUB_IMAGE):$(DOCKERHUB_TAG)

server-deploy: dh-pull up

db-%:
	docker exec -it $(DB_CONTAINER) psql -U $(POSTGRES_USER) -d $*

endif
