.PHONY: help up down check test seed demo fmt lint typecheck install

help:
	@echo "Targets: up down check test seed demo fmt lint typecheck install"

install:
	uv sync --all-groups
	uv run pre-commit install

up:
	docker compose up -d --build
	@echo "Waiting for backend /healthz..."
	@for i in $$(seq 1 30); do \
		if curl -sf http://localhost:8000/healthz >/dev/null; then \
			echo "Backend healthy"; exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Backend did not become healthy in 30s" >&2; exit 1

down:
	docker compose down -v

check: lint typecheck test

fmt:
	uv run ruff format backend
	uv run ruff check --fix backend

lint:
	uv run ruff check backend
	uv run ruff format --check backend

typecheck:
	uv run mypy backend/apix backend/tests

test:
	uv run pytest

seed:
	@echo "seed: not implemented until Phase 1 (by design — Rule 1 forbids stubs)"
	@exit 1

demo:
	@echo "demo: not implemented until Phase 8 (by design — Rule 1 forbids stubs)"
	@exit 1