# Targets for running this server locally and pushing its configuration to the
# hosting platform. GNU Make 3.81 compatible, which is what macOS ships.

VERCEL_ENV ?= production

# Keys from .env that `make env-push` copies to Vercel. Production
# authenticates with Vercel's OIDC workload identity, so the client id and
# secret stay local. The function refuses to start without the zone URL.
DEPLOY_ENV_VARS ?= KEYCARD_ZONE_URL

.DEFAULT_GOAL := help
.PHONY: help install dev run typecheck clean env-push env-pull env-list

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Run the server with debug logging
	LOG_LEVEL=DEBUG uv run getting-started-mcp

run: ## Run the server
	uv run getting-started-mcp

typecheck: ## Type-check the source
	uv run pyright

clean: ## Remove build and bytecode artifacts
	rm -rf build dist .pytest_cache
	find . -path ./.venv -prune -o -name '__pycache__' -type d -print0 2>/dev/null | xargs -0 rm -rf
	find . -path ./.venv -prune -o -name '*.egg-info' -type d -print0 2>/dev/null | xargs -0 rm -rf

env-push: ## Push DEPLOY_ENV_VARS from .env to Vercel
	@VERCEL_ENV=$(VERCEL_ENV) DEPLOY_ENV_VARS="$(DEPLOY_ENV_VARS)" ./scripts/env-push.sh

env-pull: ## Pull Vercel environment into .env.local
	@command -v vercel >/dev/null 2>&1 || { echo "vercel not found. Install it with: npm i -g vercel"; exit 1; }
	vercel env pull .env.local --environment $(VERCEL_ENV)

env-list: ## List the environment set on the Vercel project
	@command -v vercel >/dev/null 2>&1 || { echo "vercel not found. Install it with: npm i -g vercel"; exit 1; }
	vercel env ls $(VERCEL_ENV)
