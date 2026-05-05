"""Market regime detector with an optional HMM backend."""

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


class RegimeDetector:
    def __init__(self, n_states: int = 3) -> None:
        self.n_states = n_states
        self.scaler = StandardScaler()
        self.model = None
        self._state_order: list[int] = []
        self.is_fitted = False

    def fit(self, market_returns: pd.Series) -> "RegimeDetector":
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
        return self

    def predict(self, recent_returns: pd.Series) -> tuple[int, np.ndarray]:
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

    @staticmethod
    def regime_label(state: int) -> str:
        return {0: "bull", 1: "sideways", 2: "bear"}.get(state, "unknown")
