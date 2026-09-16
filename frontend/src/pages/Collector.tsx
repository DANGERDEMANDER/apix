import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ProgressLine {
  id: number;
  route: string;
  tier: string;
  status: string;
  detail: string;
  elapsed_ms: number;
}

interface CsvRow {
  date: string;
  route: string;
  source: string;
  fare_inr: string;
  captured_at: string;
}

export default function Collector() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [lines, setLines] = useState<ProgressLine[]>([]);
  const [running, setRunning] = useState(false);
  const [csvRows, setCsvRows] = useState<CsvRow[]>([]);
  const [csvTotal, setCsvTotal] = useState(0);
  const [csvPath, setCsvPath] = useState("");
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildResult, setRebuildResult] = useState<any>(null);
  const [dbState, setDbState] = useState<any>(null);

  async function refreshCsv() {
    try {
      const r = await fetch("/api/v1/collect/preview?limit=30");
      const d = await r.json();
      setCsvRows(d.rows || []);
      setCsvTotal(d.total || 0);
      setCsvPath(d.path || "");
    } catch {}
  }

  async function refreshDb() {
    try {
      const r = await fetch("/api/v1/collect/db-state");
      setDbState(await r.json());
    } catch {}
  }

  useEffect(() => {
    refreshCsv();
    refreshDb();
  }, []);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(refreshCsv, 2000);
    return () => clearInterval(t);
  }, [running]);

  async function start() {
    setLines([]);
    setRebuildResult(null);
    const r = await fetch("/api/v1/collect/start", { method: "POST" });
    const { job_id } = await r.json();
    setJobId(job_id);
    setRunning(true);
  }

  async function rebuild() {
    setRebuilding(true);
    setRebuildResult(null);
    try {
      const r = await fetch("/api/v1/collect/rebuild", { method: "POST" });
      setRebuildResult(await r.json());
      refreshCsv();
      refreshDb();
    } catch (e) {
      setRebuildResult({ error: String(e) });
    } finally {
      setRebuilding(false);
    }
  }

  useEffect(() => {
    if (!jobId) return;
    const es = new EventSource(`/api/v1/collect/stream/${jobId}`);
    es.addEventListener("progress", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setLines((prev) => [...prev.slice(-40), { id: Date.now() + Math.random(), ...data }]);
    });
    es.addEventListener("end", () => {
      es.close();
      setRunning(false);
      refreshCsv();
      refreshDb();
    });
    es.onerror = () => { es.close(); setRunning(false); };
    return () => es.close();
  }, [jobId]);

  const counts = lines.reduce<Record<string, number>>((acc, l) => {
    acc[l.status] = (acc[l.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <span className="kicker">● Live collector</span>
      <h2>Collection Run</h2>
      <p className="page-sub">
        Scrape live fares, then click <strong>Rebuild everything</strong> to
        push the CSV through the full pipeline (quotes → clean → index).
        After rebuild, refresh Index Overview to see the new data.
      </p>

      {dbState && (
        <div className="card" style={{ padding: "12px 16px" }}>
          <div style={{ display: "flex", gap: 20, fontSize: 12, fontFamily: "var(--font-mono)", flexWrap: "wrap" }}>
            <span><span style={{ color: "var(--muted)" }}>routes </span><strong>{dbState.routes}</strong></span>
            <span><span style={{ color: "var(--muted)" }}>sources </span><strong>{dbState.sources}</strong></span>
            <span><span style={{ color: "var(--muted)" }}>quotes </span><strong>{dbState.quotes}</strong></span>
            <span><span style={{ color: "var(--muted)" }}>clean </span><strong>{dbState.clean_prices}</strong></span>
            <span><span style={{ color: "var(--accent-mint)" }}>index_points </span><strong>{dbState.index_points}</strong></span>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <button onClick={start} disabled={running}>{
            running ? "Collecting…" : "Start collection"}</button>
          <button onClick={rebuild} disabled={rebuilding}>{
            rebuilding ? "Rebuilding…" : "Rebuild everything"}</button>
          <span className="pill ok">done {counts.done ?? 0}</span>
          <span className="pill bad">errors {counts.error ?? 0}</span>
          <span className="pill" style={{ marginLeft: "auto" }}>CSV rows: {csvTotal}</span>
        </div>

        <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--muted)", marginBottom: 12, wordBreak: "break-all" }}>
          {csvPath || "(csv path unknown)"}
        </div>

        <div className="log-stream">
          <AnimatePresence initial={false}>
            {lines.map((l) => (
              <motion.div
                key={l.id}
                className={`log-line log-${l.status}`}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25 }}
              >
                <span className="log-tier" style={{ color: "var(--accent-gold)" }}>{l.tier || "—"}</span>
                <span className="log-route">{l.route || "·"}</span>
                <span className="log-status">{l.status}</span>
                <span className="log-detail">{l.detail}</span>
                {l.elapsed_ms > 0 && <span className="log-time">{l.elapsed_ms}ms</span>}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      {rebuildResult && (
        <div className="card">
          <p className="card-title">Rebuild result</p>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, whiteSpace: "pre-wrap", color: "var(--ink-dim)", maxHeight: 400, overflow: "auto" }}>
            {JSON.stringify(rebuildResult, null, 2)}
          </div>
        </div>
      )}

      <div className="card">
        <p className="card-title">reference.csv · last 30 rows</p>
        {csvRows.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 13, padding: "12px 0" }}>
            {running ? "Waiting for the first route…" : "No rows yet."}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Route</th><th>Source</th>
                  <th className="num">Fare (INR)</th><th>Captured</th>
                </tr>
              </thead>
              <tbody>
                {csvRows.map((r, i) => (
                  <tr key={i}>
                    <td className="mono">{r.date}</td>
                    <td className="mono" style={{ fontWeight: 600 }}>{r.route}</td>
                    <td>{r.source}</td>
                    <td className="num mono">₹{Number(r.fare_inr).toLocaleString("en-IN")}</td>
                    <td className="mono" style={{ color: "var(--muted)", fontSize: 11 }}>
                      {String(r.captured_at).slice(11, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
