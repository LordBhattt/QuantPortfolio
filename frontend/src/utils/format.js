const INR_SYMBOL = "\u20B9";

export function formatINR(value) {
  const numeric = Number(value);
  if (value == null || Number.isNaN(numeric)) return `${INR_SYMBOL}\u2014`;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(numeric);
}

export function formatINRCompact(value) {
  const numeric = Number(value);
  if (value == null || Number.isNaN(numeric)) return `${INR_SYMBOL}\u2014`;
  const abs = Math.abs(numeric);
  const sign = numeric < 0 ? "-" : "";
  if (abs >= 1e7) return `${sign}${INR_SYMBOL}${(abs / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `${sign}${INR_SYMBOL}${(abs / 1e5).toFixed(2)} L`;
  return formatINR(numeric);
}

export function formatSignedINR(value) {
  const numeric = Number(value);
  if (value == null || Number.isNaN(numeric)) return `${INR_SYMBOL}\u2014`;
  return `${numeric >= 0 ? "+" : "-"}${formatINR(Math.abs(numeric))}`;
}

export function formatSignedINRCompact(value) {
  const numeric = Number(value);
  if (value == null || Number.isNaN(numeric)) return `${INR_SYMBOL}\u2014`;
  return `${numeric >= 0 ? "+" : "-"}${formatINRCompact(Math.abs(numeric))}`;
}

export function formatPct(value, decimals = 2) {
  const numeric = Number(value);
  if (value == null || Number.isNaN(numeric)) return "\u2014%";
  return `${numeric >= 0 ? "+" : ""}${(numeric * 100).toFixed(decimals)}%`;
}
