# Прод и демо — разные compose-проекты, поэтому у них разные тома (факты, прогнозы, часы, postgres).
# Переключение прод ↔ демо не требует ручного удаления state/clock.json и state/worker.json.
# Порты 3000/8000 общие, поэтому одновременно поднят только один стек.

PROD := docker compose -p tram
DEMO := docker compose -p tram-demo -f docker-compose.yml -f compose.demo.yml

# сервис для логов: make logs s=ml-worker
s ?=

.DEFAULT_GOAL := help
.PHONY: help \
	prod prod-restart prod-down prod-reset prod-logs prod-ps prod-status load-history \
	demo demo-resume demo-down demo-logs demo-ps demo-status \
	setup build test test-ml test-backend lint lint-ml lint-backend lint-frontend build-frontend check \
	dev-backend dev-frontend seed clean clean-data docker-prune nuke

help: ## список команд
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------- прод: реальное время, новые CSV кладутся в inbox/ тома ----------

prod: demo-down ## собрать и поднять прод (фронт :3000, API :8000)
	$(PROD) up -d --build
	@echo "frontend http://localhost:3000   swagger http://localhost:8000/docs"

prod-restart: ## пересобрать и перезапустить прод, данные сохраняются
	$(PROD) up -d --build --force-recreate

prod-down: ## остановить прод, тома сохраняются
	$(PROD) down

prod-reset: ## остановить прод и удалить его тома (факты, прогнозы, часы, сценарии)
	@read -p "Удалить тома прода (tram)? [y/N] " ans && [ "$$ans" = y ]
	$(PROD) down -v

prod-logs: ## логи прода: make prod-logs s=ml-worker
	$(PROD) logs -f --tail=200 $(s)

prod-ps: ## состояние контейнеров прода
	$(PROD) ps

prod-status: ## часы, водяной знак, активный прогон и состояние воркера на томе прода
	@$(PROD) exec backend sh -c 'for f in state/clock.json state/watermark.json active.json state/worker.json; do echo "== $$f"; cat /data/$$f 2>/dev/null || echo "(нет)"; echo; done'

load-history: ## полная загрузка train.csv + test.csv в том прода (~3 мин)
	$(PROD) run --rm ingest python -m mtml.ingest load /dataset/train.csv /dataset/test.csv

# ---------- демо: виртуальные часы 28.10.2025 → 04.11.2025, см. compose.demo.yml ----------

demo: prod-down ## демо с нуля: сбросить тома демо, часы пойдут с 28.10.2025 03:00
	$(DEMO) down -v
	$(DEMO) up -d --build
	@echo "frontend http://localhost:3000   swagger http://localhost:8000/docs"

demo-resume: prod-down ## поднять демо, не сбрасывая часы и данные
	$(DEMO) up -d --build

demo-down: ## остановить демо, тома сохраняются
	$(DEMO) down

demo-logs: ## логи демо: make demo-logs s=ml-worker
	$(DEMO) logs -f --tail=200 $(s)

demo-ps: ## состояние контейнеров демо
	$(DEMO) ps

demo-status: ## часы, водяной знак, активный прогон и состояние воркера на томе демо
	@$(DEMO) exec backend sh -c 'for f in state/clock.json state/watermark.json active.json state/worker.json; do echo "== $$f"; cat /data/$$f 2>/dev/null || echo "(нет)"; echo; done'

# ---------- проверки без Docker ----------

setup: ## поставить зависимости для тестов и линтеров: uv (ml), poetry (backend), npm (frontend)
	uv sync --group dev
	cd backend && poetry install --with dev
	cd frontend && npm ci

build: ## собрать все образы, ничего не запуская
	$(PROD) build

test: test-ml test-backend ## все тесты: ml + backend

test-ml: ## тесты ml (uv, группа dev)
	uv run --group dev pytest -q

test-backend: ## тесты backend (poetry)
	cd backend && poetry run pytest -q

lint: lint-ml lint-backend lint-frontend ## все линтеры

lint-ml:
	uvx ruff check ml

lint-backend:
	cd backend && poetry run ruff check app tests

lint-frontend:
	cd frontend && npm run lint

build-frontend: ## tsc + vite build, ловит ошибки типов
	cd frontend && npm run build

check: lint test build-frontend ## всё перед пушем: линтеры, тесты, сборка фронта

# ---------- локальная разработка ----------

dev-backend: ## API без postgres/redis/ML на :8000, синтетический прогноз (dev_standalone.py)
	cd backend && poetry run uvicorn dev_standalone:app --reload --port 8000

dev-frontend: ## vite dev-сервер на :5173; для API на :8000 нужен frontend/.env.local
	cd frontend && npm run dev

seed: ## пересобрать стартовый прогноз ml/seed/ (после смены модели, календаря, CLOCK_START демо)
	uv run --group worker python ml/scripts/build_seed.py

# ---------- очистка ----------

clean: ## кэши python/ruff/pytest и сборка фронта
	find . -type d -name __pycache__ -not -path './.venv/*' -not -path './frontend/node_modules/*' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache backend/.pytest_cache backend/.ruff_cache frontend/dist

clean-data: ## локальный том data/ (прогоны без Docker); dataset/ и ml/seed/ не трогает
	@read -p "Удалить ./data целиком? [y/N] " ans && [ "$$ans" = y ]
	rm -rf data

docker-prune: ## висящие образы и кэш сборки (тома не трогает)
	docker image prune -f
	docker builder prune -f

nuke: ## остановить прод и демо и удалить все их тома
	@read -p "Удалить тома прода и демо? [y/N] " ans && [ "$$ans" = y ]
	$(PROD) down -v --remove-orphans
	$(DEMO) down -v --remove-orphans
