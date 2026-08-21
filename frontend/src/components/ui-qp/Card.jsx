import { useRef, useState } from "react";

const TILT_DEGREES = 7;

export default function Card({ children, className = "", hover = true, tilt = false, as: Tag = "div" }) {
  const ref = useRef(null);
  const [tiltStyle, setTiltStyle] = useState({});

  const handleMouseMove = (event) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    const rotateX = (0.5 - y) * TILT_DEGREES;
    const rotateY = (x - 0.5) * TILT_DEGREES;
    setTiltStyle({
      transform: `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(0)`,
      "--sheen-x": `${x * 100}%`,
      "--sheen-y": `${y * 100}%`,
    });
  };

  const handleMouseLeave = () => {
    setTiltStyle({ transform: "perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0)" });
  };

  return (
    <Tag
      ref={tilt ? ref : undefined}
      onMouseMove={tilt ? handleMouseMove : undefined}
      onMouseLeave={tilt ? handleMouseLeave : undefined}
      style={tilt ? { ...tiltStyle, transition: "transform 150ms ease-out", transformStyle: "preserve-3d" } : undefined}
      className={`relative bg-card rounded-xl border border-black/[0.08] shadow-card ${
        hover ? "hover:shadow-card-hover transition-shadow duration-300" : ""
      } ${tilt ? "will-change-transform" : ""} ${className}`}
    >
      {tilt && (
        <div
          className="pointer-events-none absolute inset-0 rounded-xl opacity-0 hover:opacity-100 transition-opacity duration-300"
          style={{
            background: "radial-gradient(circle at var(--sheen-x, 50%) var(--sheen-y, 50%), hsl(var(--primary) / 0.12), transparent 60%)",
          }}
        />
      )}
      {children}
    </Tag>
  );
}
