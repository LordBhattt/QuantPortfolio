"""Offline LSTM training entry point."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings

settings = get_settings()


def create_sequences(features: np.ndarray, lookback: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for index in range(len(features) - lookback - horizon):
        X.append(features[index : index + lookback])
        y.append(features[index + lookback : index + lookback + horizon, 3])
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
    array = price_df[columns].astype(float).values
    mean = array.mean(axis=0)
    std = array.std(axis=0) + 1e-8
    normalized = (array - mean) / std

    lookback = settings.LSTM_LOOKBACK_DAYS
    horizon = settings.LSTM_FORECAST_DAYS
    X, y = create_sequences(normalized, lookback, horizon)
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
    torch.save({"model_state": model.state_dict()}, settings.LSTM_WEIGHTS_PATH)
    print(f"Saved weights to {settings.LSTM_WEIGHTS_PATH}")


if __name__ == "__main__":
    import httpx
    from datetime import datetime, timedelta

    weights_dir = Path(settings.LSTM_WEIGHTS_PATH).parent
    weights_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching 5 years of SPY OHLCV data for LSTM training...")
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=365 * 5)).timestamp())

    try:
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
