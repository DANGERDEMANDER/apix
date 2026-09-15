import { NavLink, Route, Routes } from "react-router-dom";
import Backtest from "./pages/Backtest";
import IndexOverview from "./pages/IndexOverview";

function Sidebar() {
  return (
    <aside className="sidebar">
      <h1>APix</h1>
      <div
        style={{
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          marginBottom: "var(--sp-4)",
        }}
      >
        Real-time Airfare Price Index
      </div>
      <nav>
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Index Overview
        </NavLink>
        <NavLink
          to="/backtest"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Backtest
        </NavLink>
      </nav>
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
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
    </div>
  );
}
