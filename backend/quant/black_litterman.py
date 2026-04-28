"""Black-Litterman return blending."""

from dataclasses import dataclass

import numpy as np


@dataclass
class BLInputs:
    cov: np.ndarray
    market_weights: np.ndarray
    risk_aversion: float
    tau: float
    P: np.ndarray | None
    Q: np.ndarray | None
    Omega: np.ndarray | None


def _regularized_inverse(matrix: np.ndarray, jitter: float = 1e-8) -> np.ndarray:
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        return np.linalg.inv(matrix + jitter * np.eye(matrix.shape[0]))


def implied_equilibrium_returns(
    cov: np.ndarray,
    market_weights: np.ndarray,
    risk_aversion: float = 2.5,
) -> np.ndarray:
    return risk_aversion * cov @ market_weights


def build_omega_from_confidence(
    P: np.ndarray,
    cov: np.ndarray,
    tau: float,
    confidences: np.ndarray,
) -> np.ndarray:
    k = P.shape[0]
    omega = np.zeros((k, k))
    for index in range(k):
        p_i = P[index : index + 1, :]
        prior_variance = float(p_i @ (tau * cov) @ p_i.T)
        confidence = float(np.clip(confidences[index], 0.01, 0.99))
        omega[index, index] = prior_variance * (1.0 - confidence) / confidence
    return omega


def black_litterman_returns(inputs: BLInputs) -> np.ndarray:
    cov = inputs.cov
    tau = inputs.tau
    implied = implied_equilibrium_returns(cov, inputs.market_weights, inputs.risk_aversion)

    if inputs.P is None or inputs.Q is None or inputs.Omega is None:
        return implied

    tau_sigma_inv = _regularized_inverse(tau * cov)
    omega_inv = _regularized_inverse(inputs.Omega)
    A = tau_sigma_inv + inputs.P.T @ omega_inv @ inputs.P
    b = tau_sigma_inv @ implied + inputs.P.T @ omega_inv @ inputs.Q
    return np.linalg.solve(A, b)


def posterior_covariance(inputs: BLInputs) -> np.ndarray:
    if inputs.P is None or inputs.Omega is None:
        return inputs.cov
    tau_sigma_inv = _regularized_inverse(inputs.tau * inputs.cov)
    omega_inv = _regularized_inverse(inputs.Omega)
    matrix = tau_sigma_inv + inputs.P.T @ omega_inv @ inputs.P
    return np.linalg.inv(matrix)
