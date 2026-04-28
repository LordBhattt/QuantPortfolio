export default function CorrelationMatrix({ tickers = [], matrix = {} }) {
  const getColor = (val) => {
    if (val === 1) return "bg-foreground text-background";
    if (val > 0.6) return "bg-primary/30 text-foreground";
    if (val > 0.3) return "bg-primary/15 text-foreground";
    if (val > 0) return "bg-primary/5 text-muted-foreground";
    if (val > -0.3) return "bg-destructive/5 text-muted-foreground";
    return "bg-destructive/15 text-destructive";
  };

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-1 min-w-[420px]"
        style={{ gridTemplateColumns: `minmax(80px, auto) repeat(${tickers.length}, minmax(48px, 1fr))` }}
      >
        <div />
        {tickers.map((t) => (
          <div key={t} className="text-[10px] font-mono text-muted-foreground text-center py-1 truncate">
            {t}
          </div>
        ))}
        {tickers.map((rowT) => (
          <Row key={rowT} rowT={rowT} tickers={tickers} matrix={matrix} getColor={getColor} />
        ))}
      </div>
    </div>
  );
}

function Row({ rowT, tickers, matrix, getColor }) {
  return (
    <>
      <div className="text-[10px] font-mono text-muted-foreground py-1 pr-2 truncate flex items-center">{rowT}</div>
      {tickers.map((colT) => {
        const val = matrix[rowT]?.[colT] ?? 0;
        return (
          <div
            key={colT}
            className={`aspect-square flex items-center justify-center font-mono text-[10px] rounded ${getColor(val)}`}
            title={`${rowT} / ${colT}: ${val.toFixed(2)}`}
          >
            {val.toFixed(2)}
          </div>
        );
      })}
    </>
  );
}
