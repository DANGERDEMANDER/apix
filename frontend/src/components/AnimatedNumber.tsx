import { useEffect, useRef, useState } from "react";

interface Props {
  value: number | null;
  decimals?: number;
  duration?: number;
  className?: string;
}

export default function AnimatedNumber({
  value,
  decimals = 2,
  duration = 900,
  className,
}: Props) {
  const [display, setDisplay] = useState(0);
  const prevRef = useRef(0);

  useEffect(() => {
    if (value === null || Number.isNaN(value)) return;
    const from = prevRef.current;
    const to = value;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else prevRef.current = to;
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  if (value === null || Number.isNaN(value)) {
    return <span className={className}>—</span>;
  }
  return <span className={className}>{display.toFixed(decimals)}</span>;
}
