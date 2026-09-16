import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import PageBackground from "./components/PageBackground";
import Backtest from "./pages/Backtest";
import Collector from "./pages/Collector";
import IndexOverview from "./pages/IndexOverview";
import Working from "./pages/Working";

export default function App() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("apix.sidebar") === "collapsed";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(
        "apix.sidebar",
        collapsed ? "collapsed" : "expanded",
      );
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <>
      <PageBackground />
      <div className={`layout ${collapsed ? "collapsed" : ""}`}>
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <main className="main">
          <Routes>
            <Route path="/" element={<IndexOverview />} />
            <Route path="/working" element={<Working />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/collector" element={<Collector />} />
          </Routes>
        </main>
      </div>
    </>
  );
}
