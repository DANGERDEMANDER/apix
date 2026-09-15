import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";

function fmt(v: number, decimals = 2): string {
  return v.toFixed(decimals);
}

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div style={{ minWidth: 130 }}>
      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div className="big-value" style={{ fontSize: "var(--fs-xl)", marginTop: 2 }}>
        {value}
        {unit ? <span style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{unit}</span> : null}
      </div>
    </div>
  );
}

export default function Backtest() {
  const q = useQuery({ queryKey: ["backtest"], queryFn: () => api.backtest() });

  if (q.isLoading) {
    return <span className="skeleton" style={{ width: "100%", height: 240 }} />;
  }
  if (q.isError) {
    return (
      <div className="error-banner">
        Could not load backtest: {(q.error as Error).message}
      </div>
    );
  }
  const data = q.data;
  if (!data) return null;

  const chartData = data.rows.map((r) => ({
    month: r.month,
    APix: r.apix_pct_of_base,
    DGCA: r.dgca_pct_of_base,
  }));

  return (
    <>
      <h2 style={{ margin: "0 0 var(--sp-4)", fontSize: "var(--fs-xl)" }}>Backtest</h2>

      <div className="card">
        <p className="card-title">Summary</p>
        <div style={{ display: "flex", gap: "var(--sp-5)", flexWrap: "wrap" }}>
          <Stat label="Months" value={String(data.metrics.n_months)} />
          <Stat label="MAPE" value={fmt(data.metrics.mape_pct)} unit="%" />
          <Stat label="Pearson r" value={fmt(data.metrics.pearson_r, 4)} />
          <Stat label="Spearman rho" value={fmt(data.metrics.spearman_rho, 4)} />
          <Stat label="Direction match" value={fmt(data.metrics.direction_match_pct, 1)} unit="%" />
        </div>
      </div>

      <div className="card">
        <p className="card-title">APix vs DGCA reference — rebased to 100 at first common month</p>
        <div style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 11, fill: "var(--muted)" }}
                width={48}
                label={{
                  value: "Relative to first month = 100",
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
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="APix"
                stroke="var(--accent)"
                strokeWidth={1.6}
                dot={{ r: 3 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="DGCA"
                stroke="var(--muted)"
                strokeWidth={1.4}
                strokeDasharray="4 4"
                dot={{ r: 3 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <p className="card-title">Month-by-month</p>
        <table>
          <thead>
            <tr>
              <th>Month</th>
              <th className="num">APix</th>
              <th className="num">DGCA</th>
              <th className="num">APix % of base</th>
              <th className="num">DGCA % of base</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.month}>
                <td className="mono">{r.month}</td>
                <td className="num">{fmt(r.apix_value)}</td>
                <td className="num">{fmt(r.dgca_value)}</td>
                <td className="num">{fmt(r.apix_pct_of_base)}</td>
                <td className="num">{fmt(r.dgca_pct_of_base)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            marginTop: 8,
          }}
        >
          {data.provenance_note}
        </div>
      </div>
    </>
  );
}
