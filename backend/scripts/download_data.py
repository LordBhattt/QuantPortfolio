"""Download reproducible price and macro parquet data with a quality report."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from backend.data.universe import PROXIES, UNIVERSE

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "backend" / "data" / "cache"
MACRO = ROOT / "backend" / "data" / "macro"
FRED_SERIES = ("DGS10", "DGS2", "VIXCLS", "BAMLH0A0HYM2", "DEXINUS", "FEDFUNDS")


def download_prices(start: str, end: str) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    quality: list[dict] = []
    for ticker in UNIVERSE:
        source = PROXIES.get(ticker, ticker)
        frame = pd.DataFrame()
        for attempt in range(3):
            try:
                frame = yf.download(source, start=start, end=end, auto_adjust=True, progress=False)
                if not frame.empty:
                    break
            except Exception as exc:
                if attempt == 2:
                    raise RuntimeError(f"Download failed for {ticker}: {exc}") from exc
            time.sleep(2 ** attempt)
        if frame.empty:
            raise RuntimeError(f"No data returned for {ticker} (source {source})")
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        close = frame["Close"].dropna()
        if close.empty:
            raise RuntimeError(f"No close prices returned for {ticker}")
        safe = ticker.replace(".", "_")
        close.to_frame("close").to_parquet(CACHE / f"{safe}_{start}_{end}.parquet")
        quality.append({
            "ticker": ticker,
            "source": source,
            "is_proxy": ticker in PROXIES,
            "first_valid_date": close.index[0].date().isoformat(),
            "last_valid_date": close.index[-1].date().isoformat(),
            "rows": int(close.shape[0]),
            "missing": int(close.isna().sum()),
        })
    return quality


def download_macro() -> list[str]:
    MACRO.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for series in FRED_SERIES:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
        frame = pd.read_csv(url, parse_dates=["observation_date"])
        frame.to_csv(MACRO / f"{series}.csv", index=False)
        saved.append(series)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2005-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--skip-macro", action="store_true")
    args = parser.parse_args()
    quality = download_prices(args.start, args.end)
    macro = [] if args.skip_macro else download_macro()
    report = {"start": args.start, "end": args.end, "prices": quality, "macro": macro}
    (ROOT / "backend" / "data" / "quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
