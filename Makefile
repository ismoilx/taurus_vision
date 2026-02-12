# Taurus Vision - Development Commands
.PHONY: help up down logs build clean restart test

help: ## Show this help message
	@echo "Taurus Vision - Available Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker-compose up -d

up-build: ## Build and start all services
	docker-compose up -d --build

down: ## Stop all services
	docker-compose down

down-v: ## Stop all services and remove volumes
	docker-compose down -v

logs: ## Show logs (all services)
	docker-compose logs -f

logs-backend: ## Show backend logs
	docker-compose logs -f backend

logs-frontend: ## Show frontend logs
	docker-compose logs -f frontend

build: ## Build all images
	docker-compose build

clean: ## Remove all containers, volumes, and images
	docker-compose down -v --rmi all

restart: ## Restart all services
	docker-compose restart

restart-backend: ## Restart backend only
	docker-compose restart backend

restart-frontend: ## Restart frontend only
	docker-compose restart frontend

test: ## Run tests (placeholder)
	@echo "Running tests..."
	cd backend && python -m pytest

shell-backend: ## Enter backend container shell
	docker-compose exec backend sh

shell-db: ## Enter PostgreSQL shell
	docker-compose exec postgres psql -U taurus -d taurus_vision

migrate: ## Run database migrations
	docker-compose exec backend alembic upgrade head

migration: ## Create new migration
	@read -p "Migration name: " name; \
	docker-compose exec backend alembic revision --autogenerate -m "$$name"

status: ## Show service status
	docker-compose ps