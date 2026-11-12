"""Pretrained return forecaster wrapper.

Provides three forecasting backends:
1. GBM model (sklearn HistGradientBoostingRegressor) - cross-sectional panel model
2. Momentum model (sklearn, loaded from .pkl) - predicts from weekly features
3. LSTM model (PyTorch) - predicts from daily OHLCV time series

Loading priority: gbm > momentum > lstm.

All predictions are annualized, clipped to asset-class bounds, and blended with
historical returns when called through predict_blended().
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)

MODEL_FEATURES = [
    "mean_last4",
    "mean_last8",
    "std_last4",
    "positive_weeks_last4",
    "positive_weeks_last8",
    "max_drop_last4",
]

# ── Long-term return priors for blending ─────────────────────────────
_ASSET_CLASS_PRIOR: dict[str, float] = {
    "stock":  0.11,
    "mf_etf": 0.10,
    "bond":   0.065,
    "gold":   0.09,
    "crypto": 0.08,
}


class ReturnForecaster:
    def __init__(self) -> None:
        self.model = None
        self.device = "cpu"
        self._torch = None
        self.model_kind = "none"
        self._gbm_scaler = None
        self._gbm_enabled = False
        self._gbm_meta: dict = {}

    def load(self, path: str | None = None) -> "ReturnForecaster":
        # Priority 1: GBM model (ml_forecaster_v2.joblib)
        backend_root = Path(__file__).resolve().parents[1]
        gbm_path = backend_root / "models" / "ml_forecaster_v2.joblib"
        gbm_meta_path = backend_root / "models" / "ml_forecaster_v2_meta.json"
        if gbm_path.is_file():
            try:
                gbm_model, gbm_scaler = joblib.load(gbm_path)
                meta: dict = {}
                if gbm_meta_path.is_file():
                    with open(gbm_meta_path) as f:
                        meta = json.load(f)
                gate_passed = meta.get("gate_passed", False)
                oos_ic = meta.get("oos_mean_ic", 0.0)
                ic_tstat = meta.get("oos_ic_tstat", 0.0)
                self.model = gbm_model
                self._gbm_scaler = gbm_scaler
                self._gbm_meta = meta
                self.model_kind = "gbm"
                self._gbm_enabled = gate_passed
                if gate_passed:
                    log.info("GBM forecaster loaded and ENABLED (IC=%.4f, t=%.2f)", oos_ic, ic_tstat)
                else:
                    log.warning(
                        "GBM forecaster loaded but DISABLED (IC=%.4f, t=%.2f < thresholds 0.02/2.0). "
                        "Falling through to momentum model.",
                        oos_ic, ic_tstat,
                    )
                    # Still try momentum as fallback
                    model_path = self._resolve_model_path(path)
                    if model_path is not None:
                        self.model = joblib.load(model_path)
                        self.model_kind = "momentum"
                        self._gbm_enabled = False
                return self
            except Exception as exc:
                log.warning("Failed to load GBM model: %s. Falling through.", exc)

        # Priority 2: momentum .pkl
        model_path = self._resolve_model_path(path)
        if model_path is not None:
            self.model = joblib.load(model_path)
            self.model_kind = "momentum"
            return self

        # Priority 3: LSTM
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("No compatible pretrained forecaster model was found") from exc

        from backend.ml.lstm_model import LSTMForecaster

        weights_path = Path(path or settings.LSTM_WEIGHTS_PATH)
        if not weights_path.is_file():
            raise RuntimeError(f"No pretrained forecaster model found at {weights_path}")

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
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
        self.model_kind = "lstm"
        return self

    def predict(self, price_df: pd.DataFrame, asset_class: str | None = None) -> float:
        """Raw ML prediction (annualized, clipped)."""
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self.model_kind == "gbm" and self._gbm_enabled:
            return self._predict_with_gbm_model(price_df, asset_class)

        if self.model_kind == "gbm" and not self._gbm_enabled:
            # GBM loaded but gated off - fall through to momentum if model is actually momentum
            # (we replaced self.model with momentum when gate not passed)
            if hasattr(self.model, "predict") and not hasattr(self.model, "feature_importances_"):
                return self._predict_with_momentum_model(price_df, asset_class)
            # If model is still the GBM (no momentum fallback), raise
            raise RuntimeError("GBM forecaster did not pass IC gate and no momentum fallback found")

        if self.model_kind == "momentum":
            return self._predict_with_momentum_model(price_df, asset_class)

        if self._torch is None:
            raise RuntimeError("LSTM model requires torch to be available")
        if len(price_df) < settings.LSTM_LOOKBACK_DAYS:
            raise ValueError("insufficient history for LSTM forecast")

        features = self._preprocess_lstm(price_df)
        with self._torch.no_grad():
            tensor = self._torch.tensor(features, dtype=self._torch.float32).unsqueeze(0).to(self.device)
            prediction = self.model(tensor)
            daily_return = float(prediction.squeeze().mean().item())
        annualized = daily_return * 252
        if not np.isfinite(annualized):
            raise ValueError("LSTM forecast is not finite")
        lo, hi = self._clip_bounds(asset_class)
        return float(np.clip(annualized, lo, hi))

    def predict_blended(
        self,
        price_df: pd.DataFrame,
        asset_class: str | None = None,
        ml_weight: float = 0.30,
    ) -> float:
        """Blend ML forecast with historical mean + long-term prior.

        final = ml_weight * ml_pred
              + (1 - ml_weight) * [0.5 * historical + 0.5 * prior]

        This prevents the ML model from single-handedly driving the
        expected return estimate, which caused wildly pessimistic
        or optimistic BL views.
        """
        ml_pred = self.predict(price_df, asset_class)

        # Historical annualized return from log returns
        prices = price_df["close"].astype(float)
        log_rets = np.log(prices / prices.shift(1)).dropna()
        hist_annual = float(log_rets.mean() * 252 + 0.5 * log_rets.var() * 252)

        # Long-term prior
        prior = _ASSET_CLASS_PRIOR.get(asset_class or "", 0.08)

        # Blend historical and prior (equally)
        hist_blend = 0.5 * hist_annual + 0.5 * prior

        # Final blend with ML
        blended = ml_weight * ml_pred + (1.0 - ml_weight) * hist_blend

        # Apply final clipping
        lo, hi = self._clip_bounds(asset_class)
        return float(np.clip(blended, lo, hi))

    def oos_ic_ml_weight(self, default: float = 0.30) -> float:
        """Return BL view confidence scaled by OOS IC (clamped 0.10-0.50)."""
        oos_ic = self._gbm_meta.get("oos_mean_ic", 0.0)
        if self.model_kind == "gbm" and self._gbm_enabled and oos_ic > 0:
            return float(min(0.50, max(0.10, oos_ic * 10.0)))
        return default

    def _predict_with_gbm_model(self, price_df: pd.DataFrame, asset_class: str | None = None) -> float:
        """Predict annualized return using the GBM cross-sectional model."""
        from backend.scripts.train_gbm_forecaster import build_features, FEATURE_COLS

        closes = price_df["close"].astype(float).dropna()
        volumes = price_df["volume"].astype(float) if "volume" in price_df.columns else None

        feats = build_features(closes, volumes, 0.0)  # market_ret=0 for single-asset inference
        if feats is None:
            raise ValueError("Insufficient history for GBM forecast")

        X = np.array([[feats[c] for c in FEATURE_COLS]])
        X_sc = self._gbm_scaler.transform(X)
        pred_scaled = float(self.model.predict(X_sc)[0])

        # pred_scaled is vol-scaled 21d forward return; convert to annualized
        realized_vol = float(closes.pct_change().dropna().tail(21).std())
        pred_raw = pred_scaled * (realized_vol + 1e-8)  # un-vol-scale
        annualized = pred_raw * (252.0 / 21.0)

        if not np.isfinite(annualized):
            raise ValueError("GBM forecast is not finite")
        lo, hi = self._clip_bounds(asset_class)
        return float(np.clip(annualized, lo, hi))

    def _resolve_model_path(self, path: str | None) -> Path | None:
        if path:
            candidate = Path(path)
            return candidate if candidate.is_file() else None

        backend_root = Path(__file__).resolve().parents[1]
        workspace_root = backend_root.parent
        candidates = [
            backend_root / "models" / "momentum_model.pkl",
            backend_root / "ml" / "momentum_model.pkl",
            workspace_root.parent / "Stock_agent" / "models" / "momentum_model.pkl",
            workspace_root / "Stock_agent" / "models" / "momentum_model.pkl",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _clip_bounds(asset_class: str | None) -> tuple[float, float]:
        """Return (lower, upper) annualized-return clip bounds per asset class.

        These bounds prevent extreme predictions from destabilising the
        Black-Litterman model.  They are wide enough to allow meaningful
        signals but narrow enough to prevent nonsensical drift.
        """
        if asset_class in ("crypto",):
            return (-0.20, 0.25)
        if asset_class in ("bond",):
            return (-0.05, 0.10)
        if asset_class in ("gold",):
            return (-0.10, 0.15)
        # stocks, mf_etf, and unknown
        return (-0.20, 0.30)

    def _predict_with_momentum_model(
        self, price_df: pd.DataFrame, asset_class: str | None = None,
    ) -> float:
        feature_frame = self._build_momentum_features(price_df)
        prediction = float(self.model.predict(feature_frame)[0])
        annualized = prediction * 52.0
        if not np.isfinite(annualized):
            raise ValueError("Momentum forecast is not finite")
        lo, hi = self._clip_bounds(asset_class)
        return float(np.clip(annualized, lo, hi))

    def _build_momentum_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        weekly_returns = self._weekly_returns(frame)
        recent_8 = weekly_returns.tail(8)
        recent_4 = recent_8.tail(4)
        if len(recent_8) < 8 or len(recent_4) < 4:
            raise ValueError("insufficient history for weekly momentum forecast")

        features = {
            "mean_last4": float(recent_4.mean()),
            "mean_last8": float(recent_8.mean()),
            "std_last4": float(recent_4.std(ddof=1)),
            "positive_weeks_last4": int((recent_4 > 0).sum()),
            "positive_weeks_last8": int((recent_8 > 0).sum()),
            "max_drop_last4": float(recent_4.min()),
        }
        return pd.DataFrame([features], columns=MODEL_FEATURES)

    def _weekly_returns(self, frame: pd.DataFrame) -> pd.Series:
        if "close" not in frame.columns:
            raise ValueError("price history is missing close prices")

        ordered = frame.copy()
        if not isinstance(ordered.index, pd.DatetimeIndex):
            ordered.index = pd.to_datetime(ordered.index)
        ordered = ordered.sort_index()

        weekly_close = ordered["close"].astype(float).resample("W-FRI").last().dropna()
        weekly_returns = weekly_close.pct_change().dropna()
        if len(weekly_returns) < 8:
            raise ValueError("insufficient history for weekly momentum forecast")
        return weekly_returns

    def _preprocess_lstm(self, frame: pd.DataFrame) -> np.ndarray:
        columns = ["open", "high", "low", "close", "volume"]
        if not set(columns).issubset(frame.columns):
            raise ValueError("price history is missing OHLCV columns")
        array = frame[columns].tail(settings.LSTM_LOOKBACK_DAYS).astype(float).values
        mean = array.mean(axis=0)
        std = array.std(axis=0) + 1e-8
        return (array - mean) / std
