"""Pretrained return forecaster wrapper.

Loads a momentum model (sklearn, from a .pkl) that predicts from weekly
price-history features.

All predictions are:
- Annualized
- Clipped to asset-class-specific bounds
- Blended with historical returns when called through `predict_blended()`
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

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
        self.model_kind = "none"

    def load(self, path: str | None = None) -> "ReturnForecaster":
        model_path = self._resolve_model_path(path)
        if model_path is None:
            raise RuntimeError("No compatible pretrained forecaster model was found")
        self.model = joblib.load(model_path)
        self.model_kind = "momentum"
        return self

    def predict(self, price_df: pd.DataFrame, asset_class: str | None = None) -> float:
        """Raw ML prediction (annualized, clipped)."""
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        return self._predict_with_momentum_model(price_df, asset_class)

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
