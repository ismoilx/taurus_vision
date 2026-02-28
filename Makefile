# Taurus Vision - Development Commands
.PHONY: help up up-build up-server up-server-build up-prod down down-v logs \
        logs-backend logs-frontend build clean restart restart-backend \
        restart-frontend test shell-backend shell-db migrate migration status

help: ## Show this help message
	@echo "Taurus Vision - Available Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── MUHIT BUYRUQLARI ────────────────────────────────────────────────────────

up: ## Lokal mashinada ishga tushirish (localhost:5173)
	docker compose up -d

up-build: ## Build va lokal ishga tushirish
	docker compose up -d --build

up-server: ## SERVER da ishga tushirish (HTTPS proksi, zxzx.uz)
	docker compose -f docker-compose.yml -f docker-compose.server.yml up -d

up-server-build: ## Build va server da ishga tushirish
	docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build

up-prod: ## Production rejimda ishga tushirish
	docker compose -f docker-compose.prod.yml up -d

up-prod-build: ## Build va production rejimda ishga tushirish
	docker compose -f docker-compose.prod.yml up -d --build

# ── ASOSIY BUYRUQLAR ────────────────────────────────────────────────────────

down: ## Barcha xizmatlarni to'xtatish
	docker compose down

down-v: ## Barcha xizmat va volumelarni o'chirish
	docker compose down -v

logs: ## Barcha xizmatlar logi
	docker compose logs -f

logs-backend: ## Backend logi
	docker compose logs -f backend

logs-frontend: ## Frontend logi
	docker compose logs -f frontend

build: ## Barcha imagelarni build qilish
	docker compose build

clean: ## Container, volume, imagelarni to'liq tozalash
	docker compose down -v --rmi all

restart: ## Barcha xizmatlarni qayta ishga tushirish
	docker compose restart

restart-backend: ## Faqat backendni qayta ishga tushirish
	docker compose restart backend

restart-frontend: ## Faqat frontendni qayta ishga tushirish
	docker compose restart frontend

# ── RIVOJLANTIRISH BUYRUQLARI ───────────────────────────────────────────────

test: ## Backend testlarini ishga tushirish
	@echo "Running tests..."
	cd backend && python -m pytest

shell-backend: ## Backend container shelliga kirish
	docker compose exec backend sh

shell-db: ## PostgreSQL shelliga kirish
	docker compose exec postgres psql -U taurus -d taurus_vision

migrate: ## Database migratsiyalarini bajarish
	docker compose exec backend alembic upgrade head

migration: ## Yangi migratsiya yaratish (nom so'raladi)
	@read -p "Migration name: " name; \
	docker compose exec backend alembic revision --autogenerate -m "$$name"

status: ## Xizmatlar holatini ko'rsatish
	docker compose ps