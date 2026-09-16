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
  index,
  total,
  progress,
}: {
  route: Route;
  index: number;
  total: number;
  progress: MotionValue<number>;
}) {
  const appearAt = 0.08 + (index / Math.max(total - 1, 1)) * 0.78;
  const opacity = useTransform(
    progress,
    [appearAt - 0.08, appearAt, appearAt + 0.35],
    [0, 1, 1],
  );
  const y = useTransform(progress, [appearAt - 0.08, appearAt], [40, 0]);
  const filter = useTransform(
    progress,
    [appearAt - 0.08, appearAt],
    ["blur(8px)", "blur(0px)"],
  );

  const isLeft = index % 2 === 0;
  const topPct = 14 + index * 10;

  return (
    <motion.div
      style={{
        opacity,
        y,
        filter,
        position: "absolute",
        top: `${topPct}%`,
        [isLeft ? "left" : "right"]: "4%",
        width: 224,
        padding: "14px 16px",
        borderRadius: 14,
        background: "rgba(10,14,26,0.78)",
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
          height: 4,
          borderRadius: 999,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <motion.div
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, delay: 0.15 }}
          style={{
            height: "100%",
            width: `${Number(route.weight) * 100 * 4}%`,
            background: "var(--grad-line)",
            transformOrigin: "left center",
            borderRadius: 999,
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 8,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
        }}
      >
        <span style={{ color: "var(--accent-mint)" }}>
          {(route.dgca_pax_annual / 1_000_000).toFixed(1)}M pax
        </span>
        <span style={{ color: "var(--muted)" }}>
          {(Number(route.weight) * 100).toFixed(2)}%
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
    damping: 22,
    restDelta: 0.0005,
  });

  // Plane position tracks the actual SVG path
  const planeX = useMotionValue(80);
  const planeY = useMotionValue(232);
  const planeRotate = useMotionValue(0);
  const trailLength = useTransform(smooth, [0, 0.95], [0, 1]);

  useMotionValueEvent(smooth, "change", (v) => {
    const el = pathRef.current;
    if (!el) return;
    const total = el.getTotalLength();
    const t = Math.max(0, Math.min(1, v));
    const at = t * total;
    const p = el.getPointAtLength(at);
    // small forward sample for heading
    const ahead = el.getPointAtLength(Math.min(at + 6, total));
    planeX.set(p.x);
    planeY.set(p.y);
    const angle = (Math.atan2(ahead.y - p.y, ahead.x - p.x) * 180) / Math.PI;
    planeRotate.set(angle);
  });

  if (!routes.length) return null;
  const visibleRoutes = routes.slice(0, 6);
  const headingOpacity = useTransform(smooth, [0, 0.04, 0.9, 1], [0, 1, 1, 0]);

  return (
    <div
      ref={containerRef}
      style={{ height: "460vh", position: "relative", marginBottom: "var(--sp-7)" }}
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
            top: "5%",
            left: "50%",
            x: "-50%",
            textAlign: "center",
            zIndex: 6,
            pointerEvents: "none",
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
              maxWidth: 520,
            }}
          >
            Scroll to follow the plane. Each stop lights up a route and its
            share of the index.
          </p>
        </motion.div>

        <svg
          viewBox="0 0 1000 400"
          preserveAspectRatio="none"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
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

          {/* faint dotted baseline */}
          <path
            d={PATH_D}
            fill="none"
            stroke="var(--line-strong)"
            strokeWidth="1"
            strokeDasharray="2 8"
            opacity="0.32"
          />

          {/* animated trail that draws in as the plane flies */}
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

          {/* plane — position from getPointAtLength, rotation from tangent */}
          <motion.g
            style={{
              x: planeX,
              y: planeY,
              rotate: planeRotate,
              originX: "50%",
              originY: "50%",
            }}
          >
            <circle r="26" fill="var(--accent-2)" opacity="0.14" />
            <text
              fontSize="26"
              textAnchor="middle"
              dominantBaseline="central"
              style={{ filter: "drop-shadow(0 0 10px var(--accent-2))" }}
            >
              ✈
            </text>
          </motion.g>
        </svg>

        {visibleRoutes.map((r, i) => (
          <RouteCard
            key={r.id}
            route={r}
            index={i}
            total={visibleRoutes.length}
            progress={smooth}
          />
        ))}
      </div>
    </div>
  );
}
