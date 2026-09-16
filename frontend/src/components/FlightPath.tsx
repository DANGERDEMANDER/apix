import { useRef } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  useMotionValue,
  useMotionValueEvent,
  type MotionValue,
} from "framer-motion";

interface Route {
  id: number;
  label: string;
  weight: string;
  dgca_pax_annual: number;
}

const PATH_D = "M 80 232 C 280 112, 400 340, 620 150 S 880 280, 920 208";

function RouteCard({
  route,
  maxWeight,
  index,
  total,
  progress,
}: {
  route: Route;
  maxWeight: number;
  index: number;
  total: number;
  progress: MotionValue<number>;
}) {
  const appearAt = 0.06 + (index / Math.max(total - 1, 1)) * 0.82;
  const opacity = useTransform(
    progress,
    [appearAt - 0.08, appearAt, appearAt + 0.4],
    [0, 1, 1],
  );
  const y = useTransform(progress, [appearAt - 0.08, appearAt], [40, 0]);
  const filter = useTransform(
    progress,
    [appearAt - 0.08, appearAt],
    ["blur(8px)", "blur(0px)"],
  );

  const isLeft = index % 2 === 0;
  const topPct = 13 + index * 11;

  const w = Number(route.weight);
  const pct = maxWeight > 0 ? (w / maxWeight) * 100 : 0;
  const isTop = w === maxWeight;

  return (
    <motion.div
      style={{
        opacity,
        y,
        filter,
        position: "absolute",
        top: `${topPct}%`,
        [isLeft ? "left" : "right"]: "3%",
        width: 220,
        padding: "14px 16px",
        borderRadius: 14,
        background: "rgba(10,14,26,0.82)",
        border: "1px solid var(--line-strong)",
        backdropFilter: "blur(14px)",
        boxShadow: "var(--shadow-lift)",
        zIndex: 4,
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: 16,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
        }}
      >
        {route.label.replace("-", " → ")}
      </div>
      <div
        style={{
          marginTop: 10,
          height: 5,
          borderRadius: 999,
          background: "rgba(255,255,255,0.08)",
          overflow: "hidden",
          position: "relative",
        }}
      >
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.9, delay: 0.2 + index * 0.06 }}
          style={{
            height: "100%",
            width: `${pct}%`,
            background: isTop ? "var(--grad-gold)" : "var(--grad-line)",
            boxShadow: isTop ? "0 0 12px rgba(255,201,120,0.55)" : "none",
            transformOrigin: "left center",
            borderRadius: 999,
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 9,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
        }}
      >
        <span style={{ color: "var(--accent-mint)" }}>
          {(route.dgca_pax_annual / 1_000_000).toFixed(1)}M pax
        </span>
        <span style={{ color: isTop ? "var(--accent-gold)" : "var(--muted)" }}>
          {(w * 100).toFixed(2)}%
        </span>
      </div>
    </motion.div>
  );
}

export default function FlightPath({ routes }: { routes: Route[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const smooth = useSpring(scrollYProgress, {
    stiffness: 90,
    damping: 24,
    restDelta: 0.0005,
  });

  const planeX = useMotionValue(80);
  const planeY = useMotionValue(232);
  const planeRotate = useMotionValue(0);
  const trailLength = useTransform(smooth, [0, 0.9], [0, 1]);
  const railProgress = useTransform(smooth, [0, 1], ["0%", "100%"]);

  useMotionValueEvent(smooth, "change", (v) => {
    const el = pathRef.current;
    if (!el) return;
    const total = el.getTotalLength();
    const t = Math.max(0, Math.min(1, v));
    const at = t * total;
    const p = el.getPointAtLength(at);
    const ahead = el.getPointAtLength(Math.min(at + 6, total));
    planeX.set(p.x);
    planeY.set(p.y);
    const angle = (Math.atan2(ahead.y - p.y, ahead.x - p.x) * 180) / Math.PI;
    planeRotate.set(angle);
  });

  if (!routes.length) return null;

  const visibleRoutes = routes.slice(0, 6);
  const maxWeight = Math.max(...routes.map((r) => Number(r.weight)));
  const headingOpacity = useTransform(smooth, [0, 0.03, 0.92, 1], [0, 1, 1, 0]);

  return (
    <div
      ref={containerRef}
      style={{ height: "260vh", position: "relative", marginBottom: "var(--sp-7)" }}
    >
      <div
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "hidden",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--line)",
          background:
            "radial-gradient(900px circle at 50% 30%, rgba(139,107,255,0.10), transparent 60%), var(--bg-1)",
        }}
      >
        <motion.div
          style={{
            opacity: headingOpacity,
            position: "absolute",
            top: "6%",
            left: "50%",
            x: "-50%",
            textAlign: "center",
            zIndex: 6,
            pointerEvents: "none",
            width: "100%",
          }}
        >
          <div className="kicker">● The basket</div>
          <h3
            style={{
              margin: "12px 0 0",
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: "-0.02em",
              color: "var(--ink)",
            }}
          >
            Every route, weighted by real traffic
          </h3>
          <p
            style={{
              margin: "8px auto 0",
              fontSize: 14,
              color: "var(--ink-dim)",
              maxWidth: 480,
            }}
          >
            Scroll to follow the plane. Each stop lights up a route and its
            share of the index.
          </p>
        </motion.div>

        {/* Trail SVG — z-index 2, below cards */}
        <svg
          viewBox="0 0 1000 400"
          preserveAspectRatio="none"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 2,
          }}
        >
          <defs>
            <linearGradient id="trailGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--accent)" />
              <stop offset="50%" stopColor="var(--accent-2)" />
              <stop offset="100%" stopColor="var(--accent-3)" />
            </linearGradient>
            <filter id="trailGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <path
            d={PATH_D}
            fill="none"
            stroke="var(--line-strong)"
            strokeWidth="1"
            strokeDasharray="2 8"
            opacity="0.32"
          />

          <motion.path
            ref={pathRef}
            d={PATH_D}
            fill="none"
            stroke="url(#trailGrad)"
            strokeWidth="2"
            strokeLinecap="round"
            filter="url(#trailGlow)"
            style={{ pathLength: trailLength, opacity: 0.95 }}
          />
        </svg>

        {/* Cards */}
        {visibleRoutes.map((r, i) => (
          <RouteCard
            key={r.id}
            route={r}
            maxWeight={maxWeight}
            index={i}
            total={visibleRoutes.length}
            progress={smooth}
          />
        ))}

        {/* Plane SVG — separate layer at z-index 6 so it floats above cards */}
        <svg
          viewBox="0 0 1000 400"
          preserveAspectRatio="none"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 6,
          }}
        >
          <motion.g
            style={{
              x: planeX,
              y: planeY,
              rotate: planeRotate,
              originX: "50%",
              originY: "50%",
            }}
          >
            <circle r="30" fill="var(--accent-2)" opacity="0.18" />
            <circle r="16" fill="var(--accent-2)" opacity="0.10" />
            <text
              fontSize="26"
              textAnchor="middle"
              dominantBaseline="central"
              style={{ filter: "drop-shadow(0 0 12px var(--accent-2))" }}
            >
              ✈
            </text>
          </motion.g>
        </svg>

        {/* Progress rail at the bottom */}
        <div className="fp-rail">
          <motion.div className="fp-rail-fill" style={{ width: railProgress }} />
          <div className="fp-rail-marks">
            {visibleRoutes.map((r, i) => (
              <span
                key={r.id}
                className="fp-rail-mark"
                style={{
                  left: `${((i + 0.5) / visibleRoutes.length) * 100}%`,
                }}
              />
            ))}
          </div>
          <div className="fp-rail-hint">scroll</div>
        </div>
      </div>
    </div>
  );
}
