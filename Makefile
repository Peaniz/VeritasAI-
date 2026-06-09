.PHONY: up down build logs ps migrate seed clean proto help

# ─────────── defaults ───────────
COMPOSE=docker compose
SERVICE?=
ENV_FILE=.env

# ─────────── main targets ───────────
up:               ## Start all services
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build

up-infra:         ## Start only infrastructure (no app services)
	$(COMPOSE) --env-file $(ENV_FILE) up -d postgres redis kafka zookeeper minio qdrant

down:             ## Stop all services
	$(COMPOSE) --env-file $(ENV_FILE) down

down-v:           ## Stop all services and remove volumes (DESTRUCTIVE)
	$(COMPOSE) --env-file $(ENV_FILE) down -v

build:            ## Build all service images
	$(COMPOSE) --env-file $(ENV_FILE) build $(SERVICE)

logs:             ## Tail logs (optional: service=auth-service)
	$(COMPOSE) --env-file $(ENV_FILE) logs -f $(SERVICE)

ps:               ## Show running containers
	$(COMPOSE) ps

restart:          ## Restart a service (service=auth-service)
	$(COMPOSE) restart $(SERVICE)

# ─────────── migrations ───────────
migrate:          ## Run DB migrations (service=auth-service)
	$(COMPOSE) exec $(SERVICE) python -m cli migrate

seed:             ## Seed database (service=auth-service)
	$(COMPOSE) exec $(SERVICE) python -m cli seed

migrate-all:      ## Run migrations on all services
	$(COMPOSE) exec auth-service python -m cli migrate
	$(COMPOSE) exec document-service python -m cli migrate
	$(COMPOSE) exec analytics-service python -m cli migrate

# ─────────── proto generation ───────────
proto:            ## Generate gRPC code from proto files
	bash scripts/generate_grpc.sh

# ─────────── dev helpers ───────────
shell:            ## Open shell in a service (service=auth-service)
	$(COMPOSE) exec $(SERVICE) /bin/sh

lint:             ## Run linting across all services
	cd services/auth-service && uv run ruff check src/
	cd services/ai-service && uv run ruff check src/
	cd services/document-service && uv run ruff check src/
	cd services/analytics-service && uv run ruff check src/

# ─────────── frontend ───────────
frontend-install: ## Install frontend deps
	cd frontend && pnpm install

frontend-dev:     ## Start frontend dev server
	cd frontend && pnpm dev

frontend-build:   ## Build frontend for production
	cd frontend && pnpm build

# ─────────── cleanup ───────────
clean:            ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .next -exec rm -rf {} +
	find . -name "*.pyc" -delete

setup:            ## First-time setup
	cp .env.example .env
	$(MAKE) up-infra
	sleep 10
	$(MAKE) migrate-all
	$(MAKE) seed service=auth-service

help:             ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
