import { NavLink, Route, Routes } from "react-router-dom";
import Backtest from "./pages/Backtest";
import IndexOverview from "./pages/IndexOverview";
import Working from "./pages/Working";
import ThemeToggle from "./components/ThemeToggle";

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-comet" aria-hidden />
      <div className="brand">
        <h1>APix</h1>
        <span className="brand-tag">v0.4 · beta</span>
      </div>

      <p className="brand-desc">
        Airfare for India&rsquo;s busiest routes, priced every day.{" "}
        <strong>Ten routes.</strong> Weighted by passenger volume.{" "}
        <strong>Rebased to 100.</strong> Nothing hidden.
      </p>

      <div className="live-badge">
        <span className="live-dot" />
        Live · replay mode
      </div>

      <nav>
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Index Overview
        </NavLink>
        <NavLink
          to="/working"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          How it works
        </NavLink>
        <NavLink
          to="/backtest"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Backtest &amp; Accuracy
        </NavLink>
      </nav>

      <div className="sidebar-stats">
        <div className="stat-row">
          <span className="stat-label">Routes</span>
          <span className="stat-value">10</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Base</span>
          <span className="stat-value">2025</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Cadence</span>
          <span className="stat-value">Daily</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Measure</span>
          <span className="stat-value">Base fare</span>
        </div>
      </div>

      <ThemeToggle />
    </aside>
  );
}

export default function App() {
  return (
    <div className="layout">
      <Sidebar />
      <main className="main">
        <Routes>
          <Route path="/" element={<IndexOverview />} />
          <Route path="/working" element={<Working />} />
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
    </div>
  );
}
