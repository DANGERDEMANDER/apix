// Minimal fetch wrapper against /api/v1. Vite dev proxy forwards /api/*
// to the backend at 127.0.0.1:8000 (see vite.config.ts).

import type {
  BacktestResponse,
  IndexLatestResponse,
  IndexResponse,
  Measure,
  Frequency,
  RoutesResponse,
} from "./types";

const BASE = "/api/v1";

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`${r.status} ${r.statusText}: ${text}`);
  }
  return (await r.json()) as T;
}

export interface IndexQuery {
  measure?: Measure;
  frequency?: Frequency;
  from?: string;
  to?: string;
}

export const api = {
  async index(q: IndexQuery = {}): Promise<IndexResponse> {
    const p = new URLSearchParams();
    if (q.measure) p.set("measure", q.measure);
    if (q.frequency) p.set("frequency", q.frequency);
    if (q.from) p.set("from", q.from);
    if (q.to) p.set("to", q.to);
    const qs = p.toString();
    return getJson<IndexResponse>(`/index${qs ? `?${qs}` : ""}`);
  },

  async latest(measure: Measure = "base", frequency: Frequency = "daily"): Promise<IndexLatestResponse> {
    return getJson<IndexLatestResponse>(
      `/index/latest?measure=${measure}&frequency=${frequency}`,
    );
  },

  async routes(): Promise<RoutesResponse> {
    return getJson<RoutesResponse>("/routes");
  },

  async backtest(): Promise<BacktestResponse> {
    return getJson<BacktestResponse>("/backtest");
  },
};

