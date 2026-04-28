import Card from "./Card";

export default function StatCard({ label, value, sub, delta, deltaPositive, accent, className = "" }) {
  const stripe =
    accent === "danger"
      ? "border-l-4 border-l-destructive"
      : accent === "warning"
      ? "border-l-4 border-l-warning"
      : accent === "success"
      ? "border-l-4 border-l-success"
      : "";
  return (
    <Card className={`p-5 ${stripe} ${className}`}>
      <div className="text-[11px] font-sans font-medium tracking-[0.12em] uppercase text-muted-foreground">
        {label}
      </div>
      <div className="mt-3 text-3xl font-mono font-medium tracking-tight text-foreground">{value}</div>
      {sub && <div className="mt-1 text-xs font-mono text-muted-foreground">{sub}</div>}
      {delta !== undefined && (
        <div className={`mt-2 text-xs font-mono ${deltaPositive ? "text-success" : "text-destructive"}`}>
          {deltaPositive ? "+" : ""}
          {delta}
        </div>
      )}
    </Card>
  );
}
