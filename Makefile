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

smoke-phase-2: ## Phase-2 acceptance: Graphiti SDK in-process + entity types + read/write contract
	@echo "🧪 Phase-2 smoke: full unit suite + Graphiti SDK construction..."
	uv run pytest -q
	@echo "🧠 Verifying Graphiti client + onboarding agent compile cleanly..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t','GEMINI_API_KEY':'t','REDIS_URL':'redis://localhost:6379'}); from src.app.services.graphiti import get_graphiti, ENTITY_TYPES; from src.agents.onboarding_agent.agent import onboarding_agent; print('graphiti backed by:', type(get_graphiti().llm_client).__name__); print('entity types registered:', len(ENTITY_TYPES))"
	@echo "🐳 Validating docker-compose syntax (graphiti container should be GONE)..."
	docker compose config -q
	@if docker compose config 2>/dev/null | grep -q 'image: zepai/graphiti'; then \
		echo "❌ standalone zepai/graphiti container still in compose"; exit 1; \
	fi
	@echo "✅ Phase-2 smoke passed."

smoke-phase-4: ## Phase-4 acceptance: Food agent + supervisor + /ws/agent + REST CRUD
	@echo "🧪 Phase-4 smoke: full unit suite (incl. allergy filter)..."
	uv run pytest -q
	@echo "🍽️  Verifying food agent + supervisor + mcp service compile cleanly..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t','GEMINI_API_KEY':'t','REDIS_URL':'redis://localhost:6379'}); from src.agents.food_agent import food_agent, RecommendationList; from src.app.services.mcp_service import mcp_service; print('food agent name:', food_agent.name); print('schema fields:', list(RecommendationList.model_fields.keys())); print('mock catalog size:', len(__import__('src.app.services.mcp_service', fromlist=['_MOCK_CATALOG'])._MOCK_CATALOG))"
	@echo "🛣️  Verifying /ws/agent + REST food routes registered..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t','GEMINI_API_KEY':'t'}); from src.app.main import app; paths = [r.path for r in app.routes if hasattr(r, 'path')]; required = ['/api/v1/ws/agent', '/api/v1/food/restaurants', '/api/v1/food/restaurants/{restaurant_id}', '/api/v1/food/orders']; missing = [p for p in required if p not in paths]; assert not missing, f'missing routes: {missing}'; print('all phase-4 routes registered')"
	@echo "🐳 Validating docker-compose syntax..."
	docker compose config -q
	@echo "✅ Phase-4 smoke passed."

smoke-phase-3: ## Phase-3 acceptance: Profile agent + UserContextSnapshot + /users/me/context route
	@echo "🧪 Phase-3 smoke: full unit suite..."
	uv run pytest -q
	@echo "🧑 Verifying profile_agent + service compile cleanly..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t','GEMINI_API_KEY':'t','REDIS_URL':'redis://localhost:6379'}); from src.agents.profile_agent import profile_agent, UserContextSnapshot; from src.app.services.profile_service import profile_service; from src.app.services.social_service import social_service; from src.app.services.travel_service import travel_service; print('profile agent name:', profile_agent.name); print('snapshot import OK'); print('services:', type(profile_service).__name__, type(social_service).__name__, type(travel_service).__name__)"
	@echo "🛣️  Verifying /users/me/context route is registered..."
	@uv run python -c "import os; os.environ.update({'ENVIRONMENT':'development','SECRET_KEY':'t','GROQ_API_KEY':'t','NEO4J_PASSWORD':'t','GEMINI_API_KEY':'t'}); from src.app.main import app; paths = [r.path for r in app.routes if hasattr(r, 'path')]; assert '/api/v1/users/me/context' in paths, f'/users/me/context missing; got {paths}'; print('users route registered:', '/api/v1/users/me/context' in paths)"
	@echo "🐳 Validating docker-compose syntax..."
	docker compose config -q
	@echo "✅ Phase-3 smoke passed."

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
