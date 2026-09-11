COMPOSE ?= docker compose
.DEFAULT_GOAL := help

.PHONY: help check-compose up down logs restart build db-reset seed migrate migration import-fixtures bootstrap-scott db-shell test lint

up down logs restart build db-reset seed migrate migration db-shell test lint: | check-compose

check-compose:
	@$(COMPOSE) version >/dev/null 2>&1 || { \
		echo 'Docker Compose is unavailable. On Fedora, install it with: sudo dnf install docker-compose'; \
		echo 'For another Compose provider, set COMPOSE="your compose command".'; \
		exit 1; \
	}

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "%-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build if needed and start the API and database with hot reload
	$(COMPOSE) up --build --detach --wait db object-storage api fixture-importer
	$(COMPOSE) run --rm object-storage-init

down: ## Stop containers and keep database data
	$(COMPOSE) down

logs: ## Follow API and database logs
	$(COMPOSE) logs --follow

restart: ## Restart the API, applying migrations and seeds again
	$(COMPOSE) restart api

build: ## Rebuild the API after dependency changes
	$(COMPOSE) build api

db-reset: ## DELETE the local database volume, then migrate and reseed
	$(COMPOSE) down --volumes
	$(COMPOSE) up --build --detach --wait db object-storage api fixture-importer
	$(COMPOSE) run --rm object-storage-init

seed: ## Add missing demo data without overwriting existing records
	$(COMPOSE) exec api python -m api.seed

migrate: ## Apply all pending migrations
	$(COMPOSE) exec api alembic upgrade head

migration: ## Generate a migration: make migration message="add fixtures"
	@test -n "$(message)" || (echo 'Usage: make migration message="add fixtures"'; exit 1)
	$(COMPOSE) exec --user "$$(id -u):$$(id -g)" api alembic revision --autogenerate -m "$(message)"

import-fixtures: ## Run the FA Full-Time fixture importer once
	$(COMPOSE) exec api python -m api.import_fixtures

bootstrap-scott: ## Clear development data and create Scott's owner workspace
	$(COMPOSE) exec api python scripts/bootstrap_scott.py

db-shell: ## Open psql in the database container
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

test: ## Run tests against a temporary PostgreSQL database
	$(COMPOSE) exec api pytest

lint: ## Check Python lint and formatting
	$(COMPOSE) exec api ruff check .
	$(COMPOSE) exec api ruff format --check .
