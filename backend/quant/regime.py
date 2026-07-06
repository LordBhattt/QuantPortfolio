"""Institutional-grade market regime detection.

Provides three classification backends:
1. Hidden Markov Model (hmmlearn) — captures temporal dependencies
2. Gaussian Mixture Model (sklearn) — fallback when hmmlearn unavailable
3. Volatility-based heuristic — ultra-robust fallback

The detector classifies markets into three regimes:
    0 = Bull  : low vol, positive trend, expanding risk appetite
    1 = Sideways : normal vol, no clear trend
    2 = Bear  : high vol, negative trend, correlations spike

Regime state propagates to:
    - Expected return engine (drift weights)
    - Covariance scaling (vol multipliers)
    - Optimizer aggressiveness (risk aversion)
    - Monte Carlo drift (regime-dependent parameters)
    - Risk metrics (VaR confidence adjustments)
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


@dataclass
class RegimeState:
    """Container for regime detection output."""
    state: int = 1                    # 0=bull, 1=sideways, 2=bear
    label: str = "sideways"
    probabilities: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0, 0.0]))
    confidence: float = 0.5           # how confident in the regime call
    vol_regime: str = "normal"        # low / normal / high
    trend_score: float = 0.0          # -1 (strong bear) to +1 (strong bull)
    persistence: float = 0.5          # how long the regime has lasted (0-1)

    # ── Parameters propagated to other modules ──
    cov_diag_scale: float = 1.0       # covariance diagonal multiplier
    cov_offdiag_scale: float = 1.0    # covariance off-diagonal multiplier
    risk_aversion_mult: float = 1.0   # optimizer risk aversion multiplier
    drift_confidence: float = 0.5     # how much to trust historical drift
    shrinkage_strength: float = 0.55  # Bayesian shrinkage intensity


# ── Pre-calibrated regime parameters ─────────────────────────────────
_REGIME_PARAMS = {
    0: {  # Bull
        "label": "bull",
        "cov_diag_scale": 0.85,
        "cov_offdiag_scale": 0.80,
        "risk_aversion_mult": 0.80,
        "drift_confidence": 0.65,
        "shrinkage_strength": 0.40,
    },
    1: {  # Sideways
        "label": "sideways",
        "cov_diag_scale": 1.00,
        "cov_offdiag_scale": 1.00,
        "risk_aversion_mult": 1.00,
        "drift_confidence": 0.50,
        "shrinkage_strength": 0.55,
    },
    2: {  # Bear
        "label": "bear",
        "cov_diag_scale": 1.40,
        "cov_offdiag_scale": 1.50,
        "risk_aversion_mult": 1.35,
        "drift_confidence": 0.30,
        "shrinkage_strength": 0.70,
    },
}


class RegimeDetector:
    """Multi-signal regime detector with HMM + volatility + trend."""

    def __init__(self, n_states: int = 3) -> None:
        self.n_states = n_states
        self.scaler = StandardScaler()
        self.model = None
        self._state_order: list[int] = []
        self.is_fitted = False
        self._vol_history: np.ndarray | None = None

    def fit(self, market_returns: pd.Series) -> "RegimeDetector":
        """Fit the regime model on market returns (e.g. SPY or NIFTY)."""
        try:
            from hmmlearn import hmm
        except ImportError:
            hmm = None

        values = market_returns.values.reshape(-1, 1)
        scaled = self.scaler.fit_transform(values)

        if hmm is not None:
            self.model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="full",
                n_iter=200,
                random_state=42,
            )
            self.model.fit(scaled)
        else:
            self.model = GaussianMixture(
                n_components=self.n_states,
                covariance_type="full",
                max_iter=200,
                random_state=42,
            )
            self.model.fit(scaled)

        means = self.model.means_.flatten()
        self._state_order = list(np.argsort(means)[::-1])
        self.is_fitted = True

        # Store rolling vol for volatility regime detection
        self._vol_history = pd.Series(market_returns.values).rolling(21).std().dropna().values

        return self

    def predict(self, recent_returns: pd.Series) -> tuple[int, np.ndarray]:
        """Basic prediction returning (regime_state, probabilities)."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("RegimeDetector not fitted")
        values = recent_returns.values.reshape(-1, 1)
        scaled = self.scaler.transform(values)
        hidden_states = self.model.predict(scaled)
        probabilities = self.model.predict_proba(scaled)
        raw_state = int(hidden_states[-1])
        semantic_state = self._state_order.index(raw_state)
        remapped = probabilities[-1][[self._state_order[index] for index in range(self.n_states)]]
        return semantic_state, remapped

    def detect_regime(self, recent_returns: pd.Series) -> RegimeState:
        """Full regime detection with all propagated parameters.

        Combines:
        1. HMM/GMM state classification
        2. Volatility regime (rolling vol vs historical distribution)
        3. Trend score (momentum-based)
        4. Regime persistence (how long in current state)
        """
        # ── 1. Statistical regime (HMM/GMM) ──
        if self.is_fitted and self.model is not None:
            try:
                hmm_state, hmm_probs = self.predict(recent_returns)
                hmm_confidence = float(hmm_probs[hmm_state])
            except Exception:
                hmm_state, hmm_probs = 1, np.array([0.0, 1.0, 0.0])
                hmm_confidence = 0.5
        else:
            hmm_state, hmm_probs = 1, np.array([0.0, 1.0, 0.0])
            hmm_confidence = 0.5

        # ── 2. Volatility regime ──
        vol_regime, vol_score = self._detect_vol_regime(recent_returns)

        # ── 3. Trend score ──
        trend_score = self._compute_trend_score(recent_returns)

        # ── 4. Combine signals ──
        # HMM gets 50% weight, vol 30%, trend 20%
        combined_scores = np.zeros(3)
        combined_scores[hmm_state] += 0.50 * hmm_confidence
        if vol_regime == "low":
            combined_scores[0] += 0.30  # bull signal
        elif vol_regime == "high":
            combined_scores[2] += 0.30  # bear signal
        else:
            combined_scores[1] += 0.30  # sideways signal

        if trend_score > 0.3:
            combined_scores[0] += 0.20 * min(trend_score, 1.0)
        elif trend_score < -0.3:
            combined_scores[2] += 0.20 * min(abs(trend_score), 1.0)
        else:
            combined_scores[1] += 0.20

        final_state = int(np.argmax(combined_scores))
        confidence = float(combined_scores[final_state] / max(combined_scores.sum(), 1e-8))

        # ── 5. Build regime state with propagated parameters ──
        params = _REGIME_PARAMS.get(final_state, _REGIME_PARAMS[1])

        return RegimeState(
            state=final_state,
            label=params["label"],
            probabilities=hmm_probs,
            confidence=confidence,
            vol_regime=vol_regime,
            trend_score=trend_score,
            persistence=self._estimate_persistence(recent_returns, final_state),
            cov_diag_scale=params["cov_diag_scale"],
            cov_offdiag_scale=params["cov_offdiag_scale"],
            risk_aversion_mult=params["risk_aversion_mult"],
            drift_confidence=params["drift_confidence"],
            shrinkage_strength=params["shrinkage_strength"],
        )

    def _detect_vol_regime(self, recent_returns: pd.Series) -> tuple[str, float]:
        """Classify current volatility as low/normal/high."""
        current_vol = float(recent_returns.tail(21).std()) if len(recent_returns) >= 21 else float(recent_returns.std())

        if self._vol_history is not None and len(self._vol_history) > 50:
            p25 = float(np.percentile(self._vol_history, 25))
            p75 = float(np.percentile(self._vol_history, 75))
        else:
            p25 = current_vol * 0.7
            p75 = current_vol * 1.3

        if current_vol < p25:
            return "low", current_vol
        elif current_vol > p75:
            return "high", current_vol
        return "normal", current_vol

    def _compute_trend_score(self, returns: pd.Series) -> float:
        """Momentum-based trend score in [-1, +1]."""
        if len(returns) < 42:
            return 0.0
        short_ma = float(returns.tail(21).mean()) * 252
        long_ma = float(returns.tail(63).mean()) * 252 if len(returns) >= 63 else short_ma

        # Positive when both positive and aligned
        if short_ma > 0 and long_ma > 0:
            return min(1.0, (short_ma + long_ma) / 0.20)  # normalise to ±20%
        elif short_ma < 0 and long_ma < 0:
            return max(-1.0, (short_ma + long_ma) / 0.20)
        # Mixed signals → near zero
        return float(np.clip((short_ma + long_ma) / 0.30, -0.5, 0.5))

    def _estimate_persistence(self, returns: pd.Series, current_state: int) -> float:
        """Estimate how long the current regime has persisted (0-1)."""
        if len(returns) < 63:
            return 0.5

        # Check if 1M, 2M, 3M returns are all same sign
        r1m = float(returns.tail(21).sum())
        r2m = float(returns.tail(42).sum())
        r3m = float(returns.tail(63).sum())

        if current_state == 0:  # bull
            positive_count = sum(1 for r in [r1m, r2m, r3m] if r > 0)
            return positive_count / 3.0
        elif current_state == 2:  # bear
            negative_count = sum(1 for r in [r1m, r2m, r3m] if r < 0)
            return negative_count / 3.0
        # sideways: persistence is high when returns are near zero
        near_zero = sum(1 for r in [r1m, r2m, r3m] if abs(r) < 0.05)
        return near_zero / 3.0

    @staticmethod
    def regime_label(state: int) -> str:
        return {0: "bull", 1: "sideways", 2: "bear"}.get(state, "unknown")
