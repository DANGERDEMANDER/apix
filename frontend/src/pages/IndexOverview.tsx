import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { IndexPoint } from "../api/types";

function fmt(v: string | null | undefined): string {
  if (v === null || v === undefined) return "?";
  return Number(v).toFixed(2);
}

function coverageClass(wc: string): string {
  const n = Number(wc);
  if (n >= 0.98) return "pill ok";
  if (n >= 0.7) return "pill warn";
  return "pill bad";
}

function ChartBlock({ points }: { points: IndexPoint[] }) {
  const data = points.map((p) => ({
    date: p.date,
    value: p.value === null ? null : Number(p.value),
    coverage: Number(p.weight_covered),
    status: p.status,
  }));

  return (
    <div className="card">
      <p className="card-title">APIX - DAILY (BASE FARE)</p>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              tickMargin={6}
              minTickGap={32}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              tickMargin={6}
              width={48}
              label={{
                value: "Index (base = 100)",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 10, fill: "var(--muted)" },
              }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                fontSize: 12,
              }}
              formatter={(value: number | null, _name, entry) => {
                const c = entry?.payload?.coverage as number | undefined;
                return [
                  value === null ? "withheld" : value.toFixed(4),
                  c !== undefined ? `coverage ${(c * 100).toFixed(1)}%` : "",
                ];
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--accent)"
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div
        style={{
          display: "flex",
          gap: 1,
          marginTop: 6,
          height: 8,
          alignItems: "stretch",
        }}
        title="Coverage per day ? green = full, amber = warning, red = below threshold"
      >
        {data.map((d, i) => {
          const c = d.coverage;
          const bg =
            c >= 0.98 ? "var(--down)" : c >= 0.7 ? "var(--warn)" : "var(--up)";
          return (
            <div
              key={i}
              style={{ flex: 1, background: bg, borderRadius: 1 }}
              title={`${d.date} ? coverage ${(c * 100).toFixed(1)}%`}
            />
          );
        })}
      </div>
      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          marginTop: 4,
        }}
      >
        Coverage strip beneath chart. Each mark is one published day.
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
    first && last && first.value && last.value
      ? Number(last.value) - Number(first.value)
      : null;

  return (
    <>
      <h2 style={{ margin: "0 0 var(--sp-4)", fontSize: "var(--fs-xl)" }}>
        Index Overview
      </h2>

      {latest.isError ? (
        <div className="error-banner">
          Could not load latest index: {(latest.error as Error).message}
        </div>
      ) : null}

      <div className="card">
        <p className="card-title">CURRENT APIX - BASE FARE</p>
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--sp-4)" }}>
          <span className="big-value">
            {latest.isLoading ? <span className="skeleton" /> : fmt(latest.data?.value)}
          </span>
          {delta !== null ? (
            <span className={delta >= 0 ? "delta-up" : "delta-down"}>
              {delta >= 0 ? "?" : "?"} {Math.abs(delta).toFixed(4)}
            </span>
          ) : null}
          {latest.data ? (
            <span className={coverageClass(latest.data.weight_covered ?? "0")}>
              coverage {((Number(latest.data.weight_covered ?? 0)) * 100).toFixed(1)}%
            </span>
          ) : null}
        </div>
        <div
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            marginTop: 4,
          }}
        >
          {latest.data?.as_of ? `as of ${latest.data.as_of}` : "no published value"}
          {latest.data?.routes_included !== null && latest.data?.routes_included !== undefined
            ? ` - ${latest.data.routes_included} routes`
            : ""}
        </div>
      </div>

      {series.isLoading ? (
        <div className="card">
          <p className="card-title">APIX - DAILY (BASE FARE)</p>
          <span className="skeleton" style={{ width: "100%", height: 240 }} />
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
          <span className="skeleton" style={{ width: "100%" }} />
        ) : routes.isError ? (
          <div style={{ color: "var(--up)" }}>Could not load routes.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Route</th>
                <th className="num">DGCA pax (annual)</th>
                <th className="num">Weight</th>
                <th>Weight source</th>
              </tr>
            </thead>
            <tbody>
              {(routes.data?.routes ?? []).map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.label}</td>
                  <td className="num">{r.dgca_pax_annual.toLocaleString("en-IN")}</td>
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
            marginTop: 8,
          }}
        >
          Synthetic weights are placeholders pending real DGCA data. See METHODOLOGY.md.
        </div>
      </div>

      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          marginTop: "var(--sp-5)",
        }}
      >
        {series.data?.base_period
          ? `Base period: ${series.data.base_period}`
          : ""}
        {series.data?.meta?.mode ? ` - data mode: ${series.data.meta.mode}` : ""}
      </div>
    </>
  );
}




