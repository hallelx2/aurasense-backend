# Aurasense Backend Makefile

.PHONY: help install dev build test deploy logs clean

# Default environment
ENV ?= development

# Server configuration (using SSH alias)
SERVER_HOST ?= aurasense
SERVER_USER ?= root

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies locally (uv-managed)
	@echo "🔧 Installing dependencies via uv..."
	uv sync --group dev

dev: ## Start development environment
	@echo "🚀 Starting development environment..."
	docker compose up --build

dev-local: ## Run backend locally (with Docker databases)
	@echo "🚀 Starting databases only..."
	docker compose up neo4j redis -d
	@echo "🐍 Starting backend locally (Graphiti runs in-process)..."
	uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

build: ## Build Docker images
	@echo "🏗️ Building Docker images..."
	docker compose build

test: ## Run tests
	@echo "🧪 Running tests..."
	uv run pytest -q

smoke-phase-0: ## Phase-0 acceptance: import + settings + production-refusal
	@echo "🧪 Phase-0 smoke: import, settings, prod-default refusal..."
	uv run pytest -q tests/test_imports.py
	@echo "🐳 Validating docker-compose syntax..."
	docker compose config -q
	@echo "✅ Phase-0 smoke passed."

smoke-phase-1: ## Phase-1 acceptance: foundation + onboarding-on-BaseAgent
	@echo "🧪 Phase-1 smoke: full unit suite + main app import..."
	uv run pytest -q
	@echo "🔌 Verifying main.py + WS route load cleanly..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t'}); import src.app.main; print('main app routes:', len(src.app.main.app.routes))"
	@echo "🐳 Validating docker-compose syntax..."
	docker compose config -q
	@echo "✅ Phase-1 smoke passed."

deploy: ## Deploy to production server
	@echo "🚀 Deploying to $(ENV) environment..."
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh $(ENV)

deploy-setup: ## Setup server for first deployment (use OVERWRITE_NGINX=1 to force Nginx config overwrite)
	@echo "🔧 Setting up server..."
	chmod +x scripts/server-setup.sh
	scp scripts/server-setup.sh $(SERVER_USER)@$(SERVER_HOST):/tmp/
	ssh $(SERVER_USER)@$(SERVER_HOST) "chmod +x /tmp/server-setup.sh && OVERWRITE_NGINX=$(OVERWRITE_NGINX) /tmp/server-setup.sh"

ssh: ## SSH into production server
	@echo "🔗 Connecting to server..."
	ssh $(SERVER_USER)@$(SERVER_HOST)

logs: ## View production logs
	@echo "📋 Viewing production logs..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd /var/www/aurasense-backend && docker compose logs -f --tail=100"

status: ## Check production status
	@echo "🔍 Checking production status..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd /var/www/aurasense-backend && docker compose ps"

restart: ## Restart production services
	@echo "🔄 Restarting production services..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd /var/www/aurasense-backend && docker compose restart"

backup: ## Create production backup
	@echo "💾 Creating production backup..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd /var/www && tar -czf aurasense-backup-$(shell date +%Y%m%d_%H%M%S).tar.gz aurasense-backend"

clean: ## Clean up local Docker resources
	@echo "🧹 Cleaning up..."
	docker compose down -v
	docker system prune -f

clean-server: ## Clean up server Docker resources
	@echo "🧹 Cleaning up server..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "cd /var/www/aurasense-backend && docker compose down -v && docker system prune -f"

env-check: ## Check current environment variables
	@echo "📄 Current environment variables:"
	@if [ -f ".env" ]; then \
		echo "✅ .env file exists"; \
		echo "Key variables:"; \
		grep -E "^(NEO4J_|CORS_|ENVIRONMENT)" .env || echo "No key variables found"; \
	else \
		echo "❌ .env file not found"; \
	fi

env-setup: ## Setup .env file for development
	@echo "🔧 Setting up environment file..."
	chmod +x scripts/setup-env.sh
	./scripts/setup-env.sh

ssl: ## Setup SSL certificate
	@echo "🔒 Setting up SSL certificate..."
	ssh $(SERVER_USER)@$(SERVER_HOST) "certbot --nginx -d $(DOMAIN)"
