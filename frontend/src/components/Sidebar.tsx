import { NavLink } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 3 3 5-6" />
    </svg>
  );
}

function IconBook() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z" />
      <path d="M4 17a3 3 0 0 1 3-3h11" />
    </svg>
  );
}

function IconTarget() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    </svg>
  );
}

function IconPlane() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12l20-8-6 20-4-8-10-4z" />
    </svg>
  );
}

const NAV = [
  { to: "/", end: true, label: "Index Overview", Icon: IconChart },
  { to: "/working", end: false, label: "How it works", Icon: IconBook },
  { to: "/backtest", end: false, label: "Backtest", Icon: IconTarget },
];

export default function Sidebar({ collapsed, onToggle }: Props) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-comet" aria-hidden />

      <div className="sidebar-top">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <IconPlane />
          </span>
          <h1 className="brand-name">APix</h1>
          <span className="brand-tag">v0.4</span>
        </div>

        <button
          className="collapse-btn"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
            {collapsed ? <path d="M9 18l6-6-6-6" /> : <path d="M15 18l-6-6 6-6" />}
          </svg>
        </button>
      </div>

      <p className="brand-desc">
        Airfare for India&rsquo;s busiest routes, priced every day.{" "}
        <strong>Ten routes.</strong> Weighted by passenger volume.{" "}
        <strong>Rebased to 100.</strong> Nothing hidden.
      </p>

      <div className="live-badge">
        <span className="live-dot" />
        <span className="live-text">Live · replay mode</span>
      </div>

      <nav>
        {NAV.map(({ to, end, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => (isActive ? "active" : "")}
            title={collapsed ? label : undefined}
          >
            <span className="nav-icon">
              <Icon />
            </span>
            <span className="nav-label">{label}</span>
            <span className="nav-arrow" aria-hidden>
              →
            </span>
          </NavLink>
        ))}
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
