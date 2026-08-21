import { useEffect, useRef, useState } from "react";

const EASE_OUT_EXPO = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

/** Animates a numeric display value from its previous value to `target` whenever `target` changes. */
export function useCountUp(target, duration = 700) {
  const [value, setValue] = useState(target ?? 0);
  const frameRef = useRef(null);
  const fromRef = useRef(target ?? 0);

  useEffect(() => {
    const numericTarget = Number.isFinite(target) ? target : 0;
    const from = fromRef.current;
    if (from === numericTarget) return undefined;

    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = EASE_OUT_EXPO(progress);
      setValue(from + (numericTarget - from) * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        fromRef.current = numericTarget;
      }
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration]);

  return value;
}
