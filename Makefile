# MATOS — entry point ergonómico. Todo va vía docker compose.
# `make help` muestra comandos disponibles.

SHELL := /usr/bin/env bash

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

# servicio por defecto para `make shell`, `make logs`, etc.
s ?= backend

# argumentos pasthrough a CLIs internas (`make new-pueblo args="..."`)
args ?=

# tag para builds (= git short sha si está disponible, si no "latest")
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)

.DEFAULT_GOAL := help

.PHONY: help
help:                ## muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort \
		| awk -F':.*##' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ─── ciclo de vida dev ──────────────────────────────────────────────────────

.PHONY: lock
lock:                ## genera uv.lock + pnpm-lock.yaml (ejecutar 1ª vez)
	./scripts/lock.sh

.PHONY: up
up:                  ## arranca dev (build automático)
	$(COMPOSE) up -d --build

.PHONY: down
down:                ## para dev
	$(COMPOSE) down

.PHONY: restart
restart:             ## reinicia un servicio (s=backend|frontend|caddy)
	$(COMPOSE) restart $(s)

.PHONY: logs
logs:                ## tail logs (s=servicio, default backend)
	$(COMPOSE) logs -f $(s)

.PHONY: shell
shell:               ## shell en servicio (s=backend|frontend, default backend)
	$(COMPOSE) exec $(s) /bin/bash || $(COMPOSE) exec $(s) /bin/sh

.PHONY: ps
ps:                  ## estado de los servicios
	$(COMPOSE) ps

# ─── ciclo de vida prod ─────────────────────────────────────────────────────

.PHONY: up-prod
up-prod:             ## arranca prod (imágenes built)
	$(COMPOSE_PROD) up -d --build

.PHONY: down-prod
down-prod:           ## para prod
	$(COMPOSE_PROD) down

.PHONY: build
build:               ## build imágenes prod tagged con git sha + latest
	MATOS_TAG=$(GIT_SHA) $(COMPOSE_PROD) build
	docker tag matos-backend:$(GIT_SHA) matos-backend:latest
	docker tag matos-frontend:$(GIT_SHA) matos-frontend:latest
	@echo "Built: matos-backend:$(GIT_SHA) matos-frontend:$(GIT_SHA) (+ latest)"

.PHONY: release
release:             ## tag + push a $$REGISTRY (definir en .env)
	./scripts/release.sh $(GIT_SHA)

# ─── tests, lint, format ────────────────────────────────────────────────────

.PHONY: test
test:                ## tests backend + frontend
	$(COMPOSE) exec backend uv run pytest
	$(COMPOSE) exec frontend pnpm test --run || true

.PHONY: lint
lint:                ## lint backend + frontend
	$(COMPOSE) exec backend uv run ruff check .
	$(COMPOSE) exec backend uv run ruff format --check .
	$(COMPOSE) exec frontend pnpm lint || true

.PHONY: format
format:              ## auto-format backend + frontend
	$(COMPOSE) exec backend uv run ruff format .
	$(COMPOSE) exec backend uv run ruff check --fix .
	$(COMPOSE) exec frontend pnpm format || true

# ─── CLI matos ──────────────────────────────────────────────────────────────

.PHONY: cli
cli:                 ## ejecuta CLI matos (args="<subcomando>")
	$(COMPOSE) exec backend uv run matos $(args)

.PHONY: init
init:                ## inicializa archivo/ con _index.json + CCAA ejemplo
	$(COMPOSE) exec backend uv run matos init /data/archivo $(args)

.PHONY: reindex
reindex:             ## reconstruye índice SQLite (≥ fase 2)
	$(COMPOSE) exec backend uv run matos reindex

.PHONY: validate
validate:            ## valida JSONs del archivo (≥ fase 1)
	$(COMPOSE) exec backend uv run matos validate /data/archivo

.PHONY: export-schemas
export-schemas:      ## genera schemas/*.schema.json desde modelos Pydantic
	$(COMPOSE) exec backend uv run matos export-schemas /app/schemas

.PHONY: new-pueblo
new-pueblo:          ## crea pueblo (args="--ccaa X --provincia Y Nombre")
	$(COMPOSE) exec backend uv run matos new-pueblo $(args)

.PHONY: new-item
new-item:            ## crea item (args="<pueblo-path> <fichero|url>")
	$(COMPOSE) exec backend uv run matos new-item $(args)

# ─── backup / restore ───────────────────────────────────────────────────────

.PHONY: backup
backup:              ## tar archivo/ + dump índice → backups/<fecha>.tar.gz
	./scripts/backup.sh

.PHONY: restore
restore:             ## restaura backup (args="<fichero.tar.gz>")
	./scripts/restore.sh $(args)

# ─── documentación ──────────────────────────────────────────────────────────

.PHONY: db-diagram
db-diagram:          ## regenera documentation/db-schema.png desde el .dot
	docker run --rm \
		-v "$(PWD)/documentation:/work" \
		-w /work alpine \
		sh -c "apk add --no-cache graphviz ttf-dejavu fontconfig >/dev/null 2>&1 && \
		       dot -Tpng db-schema.dot -o db-schema.png"
	@echo "  ✓ documentation/db-schema.png"

# ─── limpieza ───────────────────────────────────────────────────────────────

.PHONY: clean
clean:               ## ⚠ borra contenedores y volúmenes (.venv, node_modules, índice)
	@echo "Esto borrará volúmenes (incluye índice SQLite). archivo/ NO se toca."
	@read -p "¿Seguro? [y/N] " r && [[ "$$r" == "y" ]] || exit 1
	$(COMPOSE) down -v

.PHONY: rebuild
rebuild:             ## rebuild forzado de las imágenes dev
	$(COMPOSE) build --no-cache
