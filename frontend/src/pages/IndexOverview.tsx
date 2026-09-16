import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { IndexPoint } from "../api/types";
import AnimatedNumber from "../components/AnimatedNumber";

function coverageClass(wc: string | null | undefined): string {
  const n = Number(wc ?? 0);
  if (n >= 0.98) return "pill ok";
  if (n >= 0.7) return "pill warn";
  return "pill bad";
}

function Arrow({ up }: { up: boolean }) {
  return up ? (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M6 2.5L9.5 8H2.5L6 2.5Z" fill="currentColor" />
    </svg>
  ) : (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M6 9.5L2.5 4H9.5L6 9.5Z" fill="currentColor" />
    </svg>
  );
}

function withMovingAverage(points: IndexPoint[]) {
  const window: number[] = [];
  return points.map((p) => {
    const v = p.value === null ? null : Number(p.value);
    if (v !== null) {
      window.push(v);
      if (window.length > 7) window.shift();
    }
    const ma = window.length
      ? window.reduce((a, b) => a + b, 0) / window.length
      : null;
    return {
      date: p.date,
      value: v,
      ma,
      coverage: Number(p.weight_covered),
      status: p.status,
    };
  });
}

function ChartBlock({ points }: { points: IndexPoint[] }) {
  const data = withMovingAverage(points);
  const last = [...data].reverse().find((d) => d.value !== null);
  const first = data.find((d) => d.value !== null);
  const perf =
    first?.value != null && last?.value != null
      ? ((last.value - first.value) / first.value) * 100
      : null;

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "var(--sp-4)",
        }}
      >
        <p className="card-title" style={{ margin: 0 }}>
          APIX · Daily · Base fare
        </p>
        {perf !== null && (
          <span className={perf >= 0 ? "delta delta-up" : "delta delta-down"}>
            <Arrow up={perf >= 0} />
            {perf >= 0 ? "+" : "−"}
            {Math.abs(perf).toFixed(2)}%
          </span>
        )}
      </div>

      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
          >
            <defs>
              <linearGradient id="apixFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.42} />
                <stop offset="70%" stopColor="var(--accent-2)" stopOpacity={0.06} />
                <stop offset="100%" stopColor="var(--accent-2)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="apixStroke" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="var(--accent)" />
                <stop offset="55%" stopColor="var(--accent-2)" />
                <stop offset="100%" stopColor="var(--accent-3)" />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="var(--line)"
              strokeDasharray="2 6"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              tickMargin={10}
              minTickGap={40}
              axisLine={false}
              tickLine={false}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              tickMargin={8}
              width={44}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ stroke: "var(--line-strong)", strokeDasharray: "3 3" }}
              contentStyle={{
                background: "var(--bg-2)",
                border: "1px solid var(--line-strong)",
                borderRadius: 12,
                padding: "10px 12px",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                boxShadow: "var(--shadow-lift)",
              }}
              labelStyle={{ color: "var(--muted)", marginBottom: 6 }}
              formatter={(value, name, entry) => {
                const v = value as number | null;
                const cov = (entry?.payload?.coverage ?? 0) as number;
                if (name === "value") {
                  return [
                    v === null ? "withheld" : v.toFixed(3),
                    `index · cov ${(cov * 100).toFixed(1)}%`,
                  ];
                }
                return [v === null ? "—" : (v as number).toFixed(3), "7-day avg"];
              }}
            />

            <Area
              type="monotone"
              dataKey="value"
              stroke="url(#apixStroke)"
              strokeWidth={2}
              fill="url(#apixFill)"
              dot={false}
              isAnimationActive
              animationDuration={900}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="ma"
              stroke="var(--muted)"
              strokeWidth={1.2}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-footer">
        <span className="chart-legend">
          <span className="chart-legend-swatch" /> APIX daily
        </span>
        <span className="chart-legend">
          <span className="chart-legend-swatch muted" /> 7-day average
        </span>
        <span style={{ marginLeft: "auto" }}>
          {data.filter((d) => d.value !== null).length} published days
        </span>
      </div>
    </div>
  );
}

export default function IndexOverview() {
  const latest = useQuery({
    queryKey: ["index", "latest", "base", "daily"],
    queryFn: () => api.latest("base", "daily"),
  });

  const series = useQuery({
    queryKey: ["index", "base", "daily"],
    queryFn: () => api.index({ measure: "base", frequency: "daily" }),
  });

  const routes = useQuery({
    queryKey: ["routes"],
    queryFn: () => api.routes(),
  });

  const points = series.data?.points ?? [];
  const first = points.find((p) => p.status === "published");
  const last = [...points].reverse().find((p) => p.status === "published");
  const delta =
    first?.value && last?.value
      ? Number(last.value) - Number(first.value)
      : null;

  const heroValue =
    latest.data?.value != null ? Number(latest.data.value) : null;
  const coverage = latest.data?.weight_covered ?? null;

  return (
    <>
      <h2>Index Overview</h2>

      {latest.isError ? (
        <div className="error-banner">
          Could not load latest index: {(latest.error as Error).message}
        </div>
      ) : null}

      <div className="card hero-card">
        <p className="card-title">Current APIX · Base fare</p>
        <div className="hero-row">
          {latest.isLoading ? (
            <span className="skeleton" style={{ width: 240, height: 72 }} />
          ) : (
            <AnimatedNumber
              value={heroValue}
              decimals={2}
              className="big-value"
            />
          )}
          {delta !== null && (
            <span className={delta >= 0 ? "delta delta-up" : "delta delta-down"}>
              <Arrow up={delta >= 0} />
              {delta >= 0 ? "+" : "−"}
              {Math.abs(delta).toFixed(2)}
            </span>
          )}
          {coverage !== null && (
            <span className={coverageClass(coverage)}>
              coverage {(Number(coverage) * 100).toFixed(1)}%
            </span>
          )}
        </div>
        <div
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            marginTop: "var(--sp-3)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {latest.data?.as_of ? `as of ${latest.data.as_of}` : "no published value"}
          {latest.data?.routes_included != null
            ? ` · ${latest.data.routes_included} routes`
            : ""}
        </div>
      </div>

      {series.isLoading ? (
        <div className="card">
          <p className="card-title">APIX · Daily · Base fare</p>
          <span className="skeleton" style={{ width: "100%", height: 300 }} />
        </div>
      ) : series.isError ? (
        <div className="error-banner">
          Could not load series: {(series.error as Error).message}
        </div>
      ) : (
        <ChartBlock points={points} />
      )}

      <div className="card">
        <p className="card-title">Routes in basket</p>
        {routes.isLoading ? (
          <span className="skeleton" style={{ width: "100%", height: 80 }} />
        ) : routes.isError ? (
          <div className="error-banner">Could not load routes.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Route</th>
                <th className="num">DGCA pax · annual</th>
                <th className="num">Weight</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {(routes.data?.routes ?? []).map((r) => (
                <tr key={r.id}>
                  <td className="mono" style={{ fontWeight: 600 }}>
                    {r.label}
                  </td>
                  <td className="num">
                    {r.dgca_pax_annual.toLocaleString("en-IN")}
                  </td>
                  <td className="num">{Number(r.weight).toFixed(6)}</td>
                  <td>
                    <span
                      className={
                        r.weight_source === "dgca-published"
                          ? "pill ok"
                          : "pill warn"
                      }
                    >
                      {r.weight_source}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            marginTop: "var(--sp-4)",
          }}
        >
          Synthetic weights are placeholders pending real DGCA data. See
          METHODOLOGY.md.
        </div>
      </div>

      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          marginTop: "var(--sp-5)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {series.data?.base_period
          ? `Base period: ${series.data.base_period}`
          : ""}
        {series.data?.meta?.mode ? ` · data mode: ${series.data.meta.mode}` : ""}
      </div>
    </>
  );
}
