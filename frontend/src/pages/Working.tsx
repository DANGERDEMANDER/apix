import { motion } from "framer-motion";
import TiltCard from "../components/TiltCard";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
};

const PIPELINE = [
  {
    n: "01",
    name: "Collect",
    emoji: "🛰",
    body:
      "Three-tier scraper hits each route across multiple sources every day. Raw fares land in a quotes table with source, timestamp, and tier.",
  },
  {
    n: "02",
    name: "Clean",
    emoji: "🧼",
    body:
      "Normalize currency, strip taxes and fees, flag outliers, dedupe within a day. Every raw quote either survives into a clean price or is logged with a reason.",
  },
  {
    n: "03",
    name: "Weight",
    emoji: "⚖",
    body:
      "Apply DGCA annual passenger volumes as weights. Busier routes contribute more. Weights are published — you can recompute by hand.",
  },
  {
    n: "04",
    name: "Index",
    emoji: "📈",
    body:
      "Aggregate cleaned fares across the basket, rebased to 100 at the reference period. Coverage is computed alongside the value.",
  },
  {
    n: "05",
    name: "Publish",
    emoji: "🌐",
    body:
      "One row per day lands in index_points. If coverage falls below threshold the value is withheld — never interpolated, never guessed.",
  },
];

const TIERS = [
  {
    tier: "Tier 1",
    name: "HTTP + JSON",
    tone: "kpi-mint" as const,
    speed: "~50 ms",
    body:
      "Direct API calls where the source exposes a JSON endpoint. Fastest, cleanest, cheapest. httpx with connection pooling.",
    tools: ["httpx", "orjson"],
  },
  {
    tier: "Tier 2",
    name: "HTML parsing",
    tone: "kpi-cyan" as const,
    speed: "~400 ms",
    body:
      "Server-rendered pages parsed with a fast HTML selector engine. Handles sites that don't ship a public API but render prices in the initial payload.",
    tools: ["httpx", "selectolax"],
  },
  {
    tier: "Tier 3",
    name: "Browser automation",
    tone: "kpi-gold" as const,
    speed: "3–5 s",
    body:
      "Headless Chromium via Playwright. Renders the page, waits for fare widgets to appear, reads the DOM. Last resort for JS-heavy sites.",
    tools: ["playwright", "chromium"],
  },
];

const STACK = [
  { name: "FastAPI", role: "HTTP API framework", cat: "Backend" },
  { name: "SQLAlchemy 2", role: "Async ORM", cat: "Backend" },
  { name: "asyncpg", role: "Async Postgres driver", cat: "Backend" },
  { name: "Alembic", role: "Schema migrations", cat: "Backend" },
  { name: "Pydantic", role: "Validation + schemas", cat: "Backend" },
  { name: "Playwright", role: "Headless browser", cat: "Collector" },
  { name: "httpx", role: "Async HTTP client", cat: "Collector" },
  { name: "selectolax", role: "Fast HTML parsing", cat: "Collector" },
  { name: "uv", role: "Package manager", cat: "Tooling" },
  { name: "ruff", role: "Linter + formatter", cat: "Tooling" },
  { name: "mypy", role: "Static types", cat: "Tooling" },
  { name: "pytest", role: "Test runner", cat: "Tooling" },
  { name: "React 18", role: "UI framework", cat: "Frontend" },
  { name: "Vite", role: "Build tool", cat: "Frontend" },
  { name: "TanStack Query", role: "Server state", cat: "Frontend" },
  { name: "Recharts", role: "Charts", cat: "Frontend" },
  { name: "Framer Motion", role: "Animation", cat: "Frontend" },
  { name: "PostgreSQL 16", role: "Primary database", cat: "Data" },
];

const LIMITS = [
  "Weights are synthetic placeholders until real DGCA annual volumes are integrated.",
  "Only domestic routes; international is out of scope.",
  "Base-fare definition assumes a fixed fare class — real availability varies by day.",
  "The collector runs on demand; production scheduling is not yet live.",
  "Replay mode uses stored quotes; live mode uses the actual tiered scraper.",
  "No airline-direct scraping — we use public fare aggregators only.",
];

export default function Working() {
  return (
    <>
      <motion.span className="kicker" {...fadeUp}>
        ● How it works
      </motion.span>
      <motion.h2 {...fadeUp} transition={{ duration: 0.6, delay: 0.05 }}>
        Inside the pipeline
      </motion.h2>
      <motion.p
        className="page-sub"
        {...fadeUp}
        transition={{ duration: 0.6, delay: 0.1 }}
      >
        Five stages turn raw fare observations into a published daily index.
        Every stage writes to its own table, so any number on the dashboard
        can be traced back to the exact quotes that produced it. Nothing is
        hidden — including what we don&rsquo;t know.
      </motion.p>

      {/* ─── Pipeline ─────────────────────────────────────── */}
      <motion.div
        className="card"
        {...fadeUp}
        transition={{ duration: 0.7, delay: 0.15 }}
      >
        <p className="card-title">The pipeline</p>
        <p className="chart-lede">
          Collection → Cleaning → Weighting → Index → Publication. Each stage
          is a separate table and a separate test suite.
        </p>

        <div className="pipeline">
          {PIPELINE.map((s, i) => (
            <div key={s.n} className="pipeline-cell">
              <TiltCard className="stage" intensity={6}>
                <div className="stage-n">{s.n}</div>
                <div className="stage-emoji" aria-hidden>{s.emoji}</div>
                <div className="stage-name">{s.name}</div>
                <div className="stage-body">{s.body}</div>
              </TiltCard>
              {i < PIPELINE.length - 1 && (
                <div className="stage-arrow" aria-hidden>
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {/* ─── Collector tiers ──────────────────────────────── */}
      <motion.div
        className="card"
        {...fadeUp}
        transition={{ duration: 0.7, delay: 0.1 }}
      >
        <p className="card-title">The collector — three-tier escalation</p>
        <p className="chart-lede">
          Not every source needs a full browser. We try the cheapest
          technique first, escalate only on failure. This keeps the
          pipeline fast and gentle on the sources we read.
        </p>

        <div className="tier-list">
          {TIERS.map((t, i) => (
            <motion.div
              key={t.tier}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.6, delay: i * 0.12 }}
            >
              <TiltCard className={`tier ${t.tone}`} intensity={5}>
                <div className="tier-head">
                  <span className="tier-badge">{t.tier}</span>
                  <span className="tier-speed">{t.speed}</span>
                </div>
                <div className="tier-name">{t.name}</div>
                <div className="tier-body">{t.body}</div>
                <div className="tier-tools">
                  {t.tools.map((tool) => (
                    <span key={tool} className="tier-tool mono">
                      {tool}
                    </span>
                  ))}
                </div>
              </TiltCard>
              {i < TIERS.length - 1 && (
                <div className="tier-fallback">
                  <span className="tier-fallback-line" />
                  <span className="tier-fallback-label">
                    on failure · escalate
                  </span>
                  <span className="tier-fallback-line" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* ─── Open source stack ────────────────────────────── */}
      <motion.div
        className="card"
        {...fadeUp}
        transition={{ duration: 0.7, delay: 0.1 }}
      >
        <p className="card-title">Built on open source</p>
        <p className="chart-lede">
          Every dependency is public, auditable, and replaceable. No
          proprietary services hold the pipeline hostage.
        </p>

        <div className="stack-grid">
          {STACK.map((s, i) => (
            <motion.div
              key={s.name}
              className="stack-item"
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.45, delay: i * 0.025 }}
            >
              <div className="stack-cat">{s.cat}</div>
              <div className="stack-name">{s.name}</div>
              <div className="stack-role">{s.role}</div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* ─── Transparency ─────────────────────────────────── */}
      <motion.div
        className="card"
        {...fadeUp}
        transition={{ duration: 0.7, delay: 0.1 }}
      >
        <p className="card-title">Transparency</p>
        <div className="trans-grid">
          <div className="trans-item">
            <div className="trans-head">Coverage</div>
            <p className="trans-body">
              Every index value carries a{" "}
              <strong>weight_covered</strong> figure — the share of the
              basket that actually reported. If 9 of 10 routes respond with
              their full weight, coverage reads 0.94. It&rsquo;s shown on
              every published point.
            </p>
          </div>
          <div className="trans-item">
            <div className="trans-head">Withholding</div>
            <p className="trans-body">
              If coverage drops below the threshold, the day is marked{" "}
              <strong>withheld</strong>. The value column is null. The
              dashboard shows a gap. We never interpolate a day we
              can&rsquo;t measure.
            </p>
          </div>
          <div className="trans-item">
            <div className="trans-head">Reproducibility</div>
            <p className="trans-body">
              Cleaning rules, weight source, and aggregation formula live in{" "}
              <strong>METHODOLOGY.md</strong>. Anyone can recompute today&rsquo;s
              number from the raw quotes without asking us.
            </p>
          </div>
          <div className="trans-item">
            <div className="trans-head">Provenance</div>
            <p className="trans-body">
              Every route carries a{" "}
              <strong>weight_source</strong> tag:{" "}
              <em>dgca-published</em> for real data,{" "}
              <em>dgca-synthetic</em> for placeholders. The dashboard surfaces
              it — no hidden guesses.
            </p>
          </div>
        </div>
      </motion.div>

      {/* ─── Limits ───────────────────────────────────────── */}
      <motion.div
        className="card"
        {...fadeUp}
        transition={{ duration: 0.7, delay: 0.1 }}
      >
        <p className="card-title">What this is not</p>
        <p className="chart-lede">
          An index is only as honest as its stated limits. Here are ours.
        </p>
        <ol className="limits">
          {LIMITS.map((l, i) => (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.4, delay: i * 0.06 }}
            >
              {l}
            </motion.li>
          ))}
        </ol>
      </motion.div>
    </>
  );
}
