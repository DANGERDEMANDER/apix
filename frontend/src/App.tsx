import { NavLink, Route, Routes } from "react-router-dom";
import Backtest from "./pages/Backtest";
import IndexOverview from "./pages/IndexOverview";
import ThemeToggle from "./components/ThemeToggle";

function Sidebar() {
  return (
    <aside className="sidebar">
      <h1>APix</h1>
      <div className="brand-sub">Real-time Airfare Price Index</div>
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
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
    </div>
  );
}
