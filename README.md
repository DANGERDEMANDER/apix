# APix — Real-time Airfare Price Index for India

SIH 2026 Problem Statement 26056 — MoSPI / National Statistical Office.

APix collects domestic airfare quotes for a fixed basket of routes across
multiple advance-purchase windows, cleans and normalises them, and computes
a weighted price index at daily, weekly, and monthly frequency. It exposes
a public read API and an operator dashboard, and backtests monthly index
values against a DGCA reference table.

## Quickstart

Prerequisites: Python 3.11, Node.js 20+, PostgreSQL 17.

    # 1. Backend
    uv sync --all-groups
    uv run alembic upgrade head
    uv run apix seed
    uv run apix collect --mode synthetic --from 2025-08-01 --to 2025-11-30 --seed 2026
    uv run apix index --from 2025-08-01 --to 2025-11-30
    uv run apix backtest

    # 2. API server (one terminal)
    uv run uvicorn apix.main:app --host 127.0.0.1 --port 8000

    # 3. Frontend (another terminal)
    cd frontend
    npm install
    npm run dev

Then open http://localhost:5173/ — the Index Overview page.

## Architecture

    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │  Synthetic /    │──▶│  fare_quotes    │──▶│  clean_fares    │
    │  replay / live  │   │  (raw, frozen)  │   │  (validated)    │
    │  collectors     │   └─────────────────┘   └─────────────────┘
    └─────────────────┘                                    │
                                                            ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │  FastAPI        │◀──│  index_values   │◀──│  daily_route_   │
    │  /api/v1/*      │   │  (daily/weekly/ │   │  price          │
    │                 │   │   monthly)      │   │                 │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  React + Vite   │
    │  dashboard      │
    └─────────────────┘

The statistical core lives in `backend/apix/index/`. It is pure functions
on data structures, fully unit-tested, and readable in under five minutes.

## Documentation

- [METHODOLOGY.md](METHODOLOGY.md) — the formula, every assumption, every
  known limitation. Read this first.
- [ETHICS.md](ETHICS.md) — what the collector does and does not do, and why
  we declined some of the PS's requests.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — a 5-minute walkthrough for a judge.

## CLI

    apix seed                                       # load routes and sources
    apix collect --mode synthetic --from --to       # generate fare quotes
    apix index --from --to                          # compute APix index
    apix backtest                                   # compare monthly APix vs DGCA

## API endpoints

    GET /healthz                                     # liveness + DB status
    GET /api/v1/routes                               # basket with weights
    GET /api/v1/index?measure=&frequency=&from=&to= # index values
    GET /api/v1/index/latest                         # most recent value
    GET /api/v1/index/{date}/contributions           # per-route contribution
    GET /api/v1/backtest                             # DGCA comparison metrics

Full OpenAPI spec at `/docs`.

## What this build is and is not

This is a working prototype built for demonstration purposes. The
statistical core (window aggregation, missing-route re-normalisation,
withholding rule, backtest metrics) is production-grade. The collection
layer's live mode is disabled by default and the demo runs on synthetic
data. The DGCA reference values are synthetic placeholders. Every one of
these choices is documented at the point where it matters.

## Tests

    uv run pytest -q

63 tests covering the data model, synthetic generator, cleaning pipeline,
index engine, backtest metrics, and API endpoints.

## Licence and provenance

Synthetic data is used throughout this demo. See [METHODOLOGY.md](METHODOLOGY.md)
for what is real and what is not.
