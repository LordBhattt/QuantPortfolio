const regimeStyles = {
  bull: "bg-success/10 text-success border-success/30",
  sideways: "bg-warning/10 text-warning border-warning/30",
  bear: "bg-destructive/10 text-destructive border-destructive/30",
};

export default function Badge({ regime = "sideways", label }) {
  const style = regimeStyles[regime] || regimeStyles.sideways;
  const dot =
    regime === "bull" ? "bg-success" : regime === "bear" ? "bg-destructive" : "bg-warning";
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider px-3 py-1 rounded-full border ${style}`}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dot} animate-pulse`} />
      {label || regime}
    </span>
  );
}
