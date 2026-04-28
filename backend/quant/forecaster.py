"""LSTM-based return forecaster wrapper."""

import numpy as np
import pandas as pd

from backend.config import get_settings

settings = get_settings()


class ReturnForecaster:
    def __init__(self) -> None:
        self.model = None
        self.device = "cpu"
        self._torch = None

    def load(self, path: str | None = None) -> "ReturnForecaster":
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required for the LSTM forecaster") from exc

        from backend.ml.lstm_model import LSTMForecaster

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        weights_path = path or settings.LSTM_WEIGHTS_PATH
        model = LSTMForecaster(
            input_size=5,
            hidden_size=128,
            num_layers=2,
            dropout=0.2,
            forecast_horizon=settings.LSTM_FORECAST_DAYS,
        )
        checkpoint = torch.load(weights_path, map_location=self.device)
        model.load_state_dict(checkpoint["model_state"])
        model.to(self.device)
        model.eval()
        self.model = model
        return self

    def predict(self, price_df: pd.DataFrame) -> float:
        if self.model is None or self._torch is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        if len(price_df) < settings.LSTM_LOOKBACK_DAYS:
            raise ValueError("insufficient history for LSTM forecast")
        features = self._preprocess(price_df)
        with self._torch.no_grad():
            tensor = self._torch.tensor(features, dtype=self._torch.float32).unsqueeze(0).to(self.device)
            prediction = self.model(tensor)
            daily_return = float(prediction.squeeze().mean().item())
        return daily_return * 252

    def _preprocess(self, frame: pd.DataFrame) -> np.ndarray:
        columns = ["open", "high", "low", "close", "volume"]
        if not set(columns).issubset(frame.columns):
            raise ValueError("price history is missing OHLCV columns")
        array = frame[columns].tail(settings.LSTM_LOOKBACK_DAYS).astype(float).values
        mean = array.mean(axis=0)
        std = array.std(axis=0) + 1e-8
        return (array - mean) / std
