import { useLocation } from "react-router-dom";

/**
 * Fixed-position layered background. Switches texture based on route.
 * All motion is CSS-driven so React never re-renders during animation.
 */
export default function PageBackground() {
  const { pathname } = useLocation();

  const variant =
    pathname.startsWith("/working")
      ? "working"
      : pathname.startsWith("/backtest")
      ? "backtest"
      : "index";

  return (
    <div className={`page-bg page-bg-${variant}`} aria-hidden>
      {/* Common: aurora wash, tinted per page */}
      <div className="bg-aurora" />

      {/* Index — arcing flight paths + rising pax dots */}
      {variant === "index" && (
        <>
          <svg
            className="bg-arcs"
            viewBox="0 0 1440 900"
            preserveAspectRatio="xMidYMid slice"
          >
            <defs>
              <linearGradient id="arcGrad1" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
                <stop offset="50%" stopColor="var(--accent-2)" stopOpacity="0.55" />
                <stop offset="100%" stopColor="var(--accent-3)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="arcGrad2" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="var(--accent-mint)" stopOpacity="0" />
                <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.42" />
                <stop offset="100%" stopColor="var(--accent-2)" stopOpacity="0" />
              </linearGradient>
            </defs>

            <path
              className="bg-arc bg-arc-1"
              d="M -100 640 Q 400 240, 900 440 T 1600 300"
              fill="none"
              stroke="url(#arcGrad1)"
              strokeWidth="1.4"
              strokeDasharray="6 10"
            />
            <path
              className="bg-arc bg-arc-2"
              d="M -100 300 Q 500 700, 1000 400 T 1600 640"
              fill="none"
              stroke="url(#arcGrad2)"
              strokeWidth="1.2"
              strokeDasharray="4 12"
            />
            <path
              className="bg-arc bg-arc-3"
              d="M -100 500 Q 600 100, 1100 620 T 1600 500"
              fill="none"
              stroke="url(#arcGrad1)"
              strokeWidth="1"
              strokeDasharray="3 14"
            />
          </svg>

          <div className="bg-dots bg-dots-index">
            {Array.from({ length: 22 }).map((_, i) => (
              <span
                key={i}
                style={{
                  left: `${(i * 37) % 100}%`,
                  animationDelay: `${(i * 1.7) % 18}s`,
                  animationDuration: `${14 + (i % 5) * 3}s`,
                }}
              />
            ))}
          </div>
        </>
      )}

      {/* Working — vertical pipeline streams */}
      {variant === "working" && (
        <>
          <div className="bg-streams">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="bg-stream"
                style={{
                  left: `${6 + i * 11}%`,
                  animationDelay: `${(i * 0.9) % 6}s`,
                  animationDuration: `${7 + (i % 3) * 2}s`,
                }}
              >
                {Array.from({ length: 5 }).map((__, j) => (
                  <span
                    key={j}
                    style={{ animationDelay: `${(j * 0.5 + i * 0.3) % 4}s` }}
                  />
                ))}
              </div>
            ))}
          </div>

          <svg
            className="bg-rings"
            viewBox="0 0 1440 900"
            preserveAspectRatio="xMidYMid slice"
          >
            <circle className="bg-ring" cx="720" cy="450" r="180" />
            <circle className="bg-ring bg-ring-2" cx="720" cy="450" r="320" />
            <circle className="bg-ring bg-ring-3" cx="720" cy="450" r="480" />
          </svg>
        </>
      )}

      {/* Backtest — rotating radar sweep + crosshair */}
      {variant === "backtest" && (
        <>
          <div className="bg-radar">
            <div className="bg-radar-sweep" />
            <div className="bg-radar-ring bg-radar-ring-1" />
            <div className="bg-radar-ring bg-radar-ring-2" />
            <div className="bg-radar-ring bg-radar-ring-3" />
            <div className="bg-radar-cross bg-radar-cross-h" />
            <div className="bg-radar-cross bg-radar-cross-v" />
          </div>

          <svg
            className="bg-waves"
            viewBox="0 0 1440 900"
            preserveAspectRatio="xMidYMid slice"
          >
            <path
              className="bg-wave bg-wave-1"
              d="M 0 450 Q 360 380, 720 450 T 1440 450"
              fill="none"
              stroke="var(--accent-3)"
              strokeWidth="1"
              opacity="0.35"
            />
            <path
              className="bg-wave bg-wave-2"
              d="M 0 500 Q 360 430, 720 500 T 1440 500"
              fill="none"
              stroke="var(--accent-2)"
              strokeWidth="1"
              opacity="0.28"
            />
            <path
              className="bg-wave bg-wave-3"
              d="M 0 550 Q 360 480, 720 550 T 1440 550"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="1"
              opacity="0.22"
            />
          </svg>
        </>
      )}

      {/* Common: fine grain noise overlay */}
      <div className="bg-grain" />
    </div>
  );
}
