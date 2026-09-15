// Response shapes for /api/v1 (mirror of backend apix/api/schemas.py).

export type Measure = "base" | "total";
export type Frequency = "daily" | "weekly" | "monthly";
export type IndexStatus = "published" | "insufficient_coverage" | "no_data";

export interface Meta {
  generated_at: string;
  mode: string;
  data_quality: string | null;
}

export interface IndexPoint {
  date: string;
  value: string | null;
  weight_covered: string;
  routes_included: number;
  status: IndexStatus;
  withheld_reason: string | null;
}

export interface IndexResponse {
  meta: Meta;
  measure: Measure;
  frequency: Frequency;
  base_period: string;
  points: IndexPoint[];
}

export interface IndexLatestResponse {
  meta: Meta;
  measure: Measure;
  as_of: string | null;
  value: string | null;
  weight_covered: string | null;
  routes_included: number | null;
  status: IndexStatus;
}

export interface RouteOut {
  id: number;
  label: string;
  origin_iata: string;
  destination_iata: string;
  dgca_pax_annual: number;
  weight: string;
  weight_period: string;
  weight_source: string;
  weight_source_note: string;
  is_active: boolean;
}

export interface RoutesResponse {
  meta: Meta;
  routes: RouteOut[];
}

export interface BacktestMonthRow {
  month: string;
  apix_value: number;
  dgca_value: number;
  apix_pct_of_base: number;
  dgca_pct_of_base: number;
}

export interface BacktestMetricsOut {
  n_months: number;
  mape_pct: number;
  pearson_r: number;
  spearman_rho: number;
  direction_match_pct: number;
}

export interface BacktestResponse {
  meta: Meta;
  rows: BacktestMonthRow[];
  metrics: BacktestMetricsOut;
  provenance_note: string;
}
