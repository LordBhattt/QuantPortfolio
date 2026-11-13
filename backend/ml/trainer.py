"""Offline LSTM training entry point."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yfinance as yf

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings

settings = get_settings()


def create_sequences(features: np.ndarray, target: np.ndarray, lookback: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for index in range(len(features) - lookback - horizon + 1):
        X.append(features[index : index + lookback])
        y.append(target[index + lookback : index + lookback + horizon])
    return np.array(X), np.array(y)


def train(price_df: pd.DataFrame, epochs: int = 100, lr: float = 1e-3) -> None:
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise RuntimeError("torch is required to train the LSTM model") from exc

    from backend.ml.lstm_model import LSTMForecaster

    columns = ["open", "high", "low", "close", "volume"]
    prices = price_df[columns].astype(float).replace(0.0, np.nan).ffill().dropna()
    raw = np.column_stack([
        np.log(prices[column] / prices[column].shift(1))
        for column in columns[:4]
    ] + [np.log(prices["volume"] / prices["volume"].shift(1).replace(0.0, np.nan))])
    raw = pd.DataFrame(raw, index=prices.index).replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    target = raw[:, 3]
    split = max(settings.LSTM_LOOKBACK_DAYS + settings.LSTM_FORECAST_DAYS, int(len(raw) * 0.8))
    mean = raw[:split].mean(axis=0)
    std = raw[:split].std(axis=0) + 1e-8
    normalized = (raw - mean) / std

    lookback = settings.LSTM_LOOKBACK_DAYS
    horizon = settings.LSTM_FORECAST_DAYS
    X, y = create_sequences(normalized, target, lookback, horizon)
    dataset = TensorDataset(
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
    )
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    model = LSTMForecaster(forecast_horizon=horizon)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    for epoch in range(epochs):
        model.train()
        losses = []
        for batch_x, batch_y in loader:
            prediction = model(batch_x)
            loss = criterion(prediction, batch_y)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.item()))
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch + 1}/{epochs} loss={np.mean(losses):.6f}")

    Path(settings.LSTM_WEIGHTS_PATH).parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state": model.state_dict(),
        "feature_mean": mean.tolist(),
        "feature_std": std.tolist(),
        "feature_definition": "daily log OHLCV changes; target is forward close log return",
        "train_rows": int(split),
    }, settings.LSTM_WEIGHTS_PATH)
    print(f"Saved weights to {settings.LSTM_WEIGHTS_PATH}")


if __name__ == "__main__":
    import httpx
    from datetime import datetime, timedelta

    weights_dir = Path(settings.LSTM_WEIGHTS_PATH).parent
    weights_dir.mkdir(parents=True, exist_ok=True)

    try:
        cache_files = sorted((PROJECT_ROOT / "backend" / "data" / "cache").glob("SPY_*.parquet"))
        if cache_files:
            cached = pd.read_parquet(cache_files[-1])
            df = cached.rename(columns={column: column.lower() for column in cached.columns})
            if not {"open", "high", "low", "volume"}.issubset(df.columns):
                fetched = yf.download("SPY", period="5y", auto_adjust=True, progress=False)
                if isinstance(fetched.columns, pd.MultiIndex):
                    fetched.columns = fetched.columns.get_level_values(0)
                df = fetched.rename(columns={column: column.lower() for column in fetched.columns})
            df = df[["open", "high", "low", "close", "volume"]].dropna()
        else:
            print("Fetching 5 years of SPY OHLCV data for LSTM training...")
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=365 * 5)).timestamp())
            response = httpx.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/SPY",
                params={"period1": start, "period2": end, "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            quote = result["indicators"]["quote"][0]
            df = pd.DataFrame(
                {
                    "open": quote["open"],
                    "high": quote["high"],
                    "low": quote["low"],
                    "close": quote["close"],
                    "volume": quote["volume"],
                }
            ).dropna()

        if len(df) < 200:
            raise ValueError(f"Not enough data: only {len(df)} rows fetched")

        print(f"Fetched {len(df)} trading days. Starting training (60 epochs)...")
        train(df, epochs=60, lr=1e-3)
        print("LSTM training complete.")
        print(f"Weights saved to {settings.LSTM_WEIGHTS_PATH}")
        print("The backend will load these automatically on next startup.")
    except httpx.TimeoutException:
        print("Yahoo Finance timed out. Check internet connection and retry.")
        raise SystemExit(1)
    except Exception as exc:
        print(f"Training failed: {exc}")
        print("The app still works without LSTM -- optimization uses Black-Litterman equilibrium returns.")
        print("Retry this step once you have stable internet access.")
        raise SystemExit(1)
