import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
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
import TiltCard from "../components/TiltCard";
import FlightPath from "../components/FlightPath";

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

interface TickerRoute {
  id: number;
  label: string;
  dgca_pax_annual: number;
  weight: string;
}

function Ticker({ routes }: { routes: TickerRoute[] }) {
  if (!routes.length) return null;
  const items = [...routes, ...routes];
  return (
    <div className="ticker" aria-label="Live route weights">
      <div className="ticker-track">
        {items.map((r, i) => (
          <span key={`${r.id}-${i}`} className="ticker-item">
            <span className="ticker-label">{r.label}</span>
            <span className="ticker-sep">·</span>
            <span className="ticker-weight">
              {(Number(r.weight) * 100).toFixed(3)}%
            </span>
            <span className="ticker-sep">·</span>
            <span className="ticker-pax">
              {(r.dgca_pax_annual / 1_000_000).toFixed(1)}M pax
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  decimals = 0,
  unit,
  sub,
  tone,
  delay = 0,
}: {
  label: string;
  value: number | null;
  decimals?: number;
  unit?: string;
  sub: string;
  tone: "violet" | "gold" | "mint" | "cyan" | "pink";
  delay?: number;
}) {
  const cls =
    tone === "gold"
      ? "kpi kpi-gold"
      : tone === "mint"
      ? "kpi kpi-mint"
      : tone === "cyan"
      ? "kpi kpi-cyan"
      : tone === "pink"
      ? "kpi kpi-pink"
      : "kpi";
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <TiltCard className={cls} intensity={7}>
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">
          <AnimatedNumber value={value} decimals={decimals} />
          {unit && <span className="unit">{unit}</span>}
        </div>
        <div className="kpi-sub">{sub}</div>
      </TiltCard>
    </motion.div>
  );
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
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "var(--sp-4)",
          gap: "var(--sp-4)",
          flexWrap: "wrap",
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

      <p className="chart-lede">
        Daily readings in bright. A{" "}
        <strong>7-day average in dashed grey</strong> to cut the noise. Hover
        any point to see the day&rsquo;s coverage.
      </p>

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

            <CartesianGrid stroke="var(--line)" strokeDasharray="2 6" vertical={false} />
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
              animationDuration={1200}
              animationEasing="ease-out"
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
    </motion.div>
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
  const above = heroValue !== null && heroValue > 100;

  const routeList = routes.data?.routes ?? [];
  const totalPax = routeList.reduce((a, r) => a + r.dgca_pax_annual, 0);
  const publishedDays = points.filter((p) => p.status === "published").length;
  const maxWeight = routeList.reduce(
    (m, r) => Math.max(m, Number(r.weight)),
    0,
  );
  const topRoute = routeList.find((r) => Number(r.weight) === maxWeight);

  return (
    <>
      <span className="kicker">● Live · Index</span>
      <h2>Index Overview</h2>
      <p className="page-sub">
        The pulse of Indian air travel, in{" "}
        <span className="hl">one number</span>. Ten high-traffic routes.
        Weighted by real passenger volume. Rebased to a fixed reference.
        Published every day — nothing hidden.
      </p>

      {routeList.length > 0 && <Ticker routes={routeList} />}

      {latest.isError ? (
        <div className="error-banner">
          Could not load latest index: {(latest.error as Error).message}
        </div>
      ) : null}

      <div className="kpi-grid">
        <Kpi
          label="Current Index"
          value={heroValue}
          decimals={2}
          tone="violet"
          delay={0}
          sub={above ? "Above the 100 baseline" : "Below the 100 baseline"}
        />
        <Kpi
          label="Coverage"
          value={coverage !== null ? Number(coverage) * 100 : null}
          decimals={1}
          unit="%"
          tone="mint"
          delay={0.06}
          sub="Weight of published routes"
        />
        <Kpi
          label="Published Days"
          value={publishedDays}
          tone="cyan"
          delay={0.12}
          sub="Days with a full reading"
        />
        <Kpi
          label="Annual Pax"
          value={totalPax / 1_000_000}
          decimals={1}
          unit="M"
          tone="gold"
          delay={0.18}
          sub={topRoute ? `Top route: ${topRoute.label}` : "Across the basket"}
        />
      </div>

      <motion.div
        className="card hero-card"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <p className="card-title">Current APIX · Base fare</p>
        <div className="hero-row">
          {latest.isLoading ? (
            <span className="skeleton" style={{ width: 260, height: 64 }} />
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

        <p className="hero-desc">
          {heroValue !== null ? (
            <>
              The basket sits{" "}
              <strong>
                {above ? "above" : "below"} the 100 baseline
              </strong>
              . That&rsquo;s the swing between the first and last published
              days in the visible window, shown as the chip above.
            </>
          ) : (
            "No published reading yet — the collector hasn't run."
          )}
        </p>

        <div
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            marginTop: "var(--sp-4)",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.04em",
          }}
        >
          {latest.data?.as_of
            ? `AS OF ${latest.data.as_of}`
            : "NO PUBLISHED VALUE"}
          {latest.data?.routes_included != null
            ? ` · ${latest.data.routes_included} ROUTES`
            : ""}
        </div>
      </motion.div>

      {/* ─── Scrollytelling flight path ─────────────────────── */}
      {routeList.length > 0 && <FlightPath routes={routeList} />}

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

      <motion.div
        className="card"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <p className="card-title">Routes in basket</p>
        <p className="chart-lede">
          Bigger routes pull harder.{" "}
          <strong>Weight equals share of passenger volume</strong> — so DEL-BOM
          moves the index roughly four times as much as BLR-CCU.
        </p>
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
                <th style={{ textAlign: "right" }}>Weight share</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {routeList.map((r) => {
                const w = Number(r.weight);
                const pct = maxWeight > 0 ? w / maxWeight : 0;
                const isTop = w === maxWeight;
                return (
                  <tr key={r.id}>
                    <td className="mono" style={{ fontWeight: 600 }}>
                      {r.label}
                    </td>
                    <td className="num">
                      {r.dgca_pax_annual.toLocaleString("en-IN")}
                    </td>
                    <td>
                      <div className="wbar">
                        <div className="wbar-track">
                          <div
                            className={isTop ? "wbar-fill top" : "wbar-fill"}
                            style={{ width: `${pct * 100}%` }}
                          />
                        </div>
                        <span className="wbar-num">
                          {(w * 100).toFixed(3)}%
                        </span>
                      </div>
                    </td>
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
                );
              })}
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
      </motion.div>

      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          marginTop: "var(--sp-5)",
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.04em",
        }}
      >
        {series.data?.base_period
          ? `BASE PERIOD · ${series.data.base_period}`
          : ""}
        {series.data?.meta?.mode
          ? ` · DATA MODE · ${series.data.meta.mode.toUpperCase()}`
          : ""}
      </div>
    </>
  );
}
