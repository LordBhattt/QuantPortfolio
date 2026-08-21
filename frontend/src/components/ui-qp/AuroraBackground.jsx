export default function AuroraBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute -top-40 -left-40 h-[32rem] w-[32rem] rounded-full opacity-40 blur-[100px] animate-aurora-drift-1"
        style={{ background: "radial-gradient(circle, hsl(var(--primary) / 0.55), transparent 70%)" }}
      />
      <div
        className="absolute top-1/3 -right-32 h-[28rem] w-[28rem] rounded-full opacity-30 blur-[100px] animate-aurora-drift-2"
        style={{ background: "radial-gradient(circle, #7c3aed55, transparent 70%)" }}
      />
      <div
        className="absolute -bottom-32 left-1/4 h-[26rem] w-[26rem] rounded-full opacity-30 blur-[100px] animate-aurora-drift-3"
        style={{ background: "radial-gradient(circle, hsl(var(--primary-dark) / 0.45), transparent 70%)" }}
      />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(0,0,0,0.06) 1.5px, transparent 1.5px)",
          backgroundSize: "24px 24px",
        }}
      />
    </div>
  );
}
