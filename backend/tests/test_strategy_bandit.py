import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cvxpy")

from backend.quant.strategy_bandit import RegimeStrategyBandit, run_adaptive_bandit_backtest


def _synthetic_returns(n_days: int = 1100, n_assets: int = 4, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    tickers = [f"ASSET_{i}" for i in range(n_assets)]
    means = rng.uniform(0.0002, 0.0008, size=n_assets)
    vols = rng.uniform(0.008, 0.02, size=n_assets)
    data = rng.normal(loc=means, scale=vols, size=(n_days, n_assets))
    return pd.DataFrame(data, index=dates, columns=tickers)


def test_bandit_posterior_moves_toward_the_empirically_better_arm() -> None:
    bandit = RegimeStrategyBandit(arms=("good_arm", "bad_arm"), seed=1)
    rng = np.random.default_rng(0)

    for _ in range(200):
        bandit.update("bull", "good_arm", float(rng.normal(1.0, 0.1)))
        bandit.update("bull", "bad_arm", float(rng.normal(-1.0, 0.1)))

    summary = bandit.posterior_summary()
    assert summary["bull"]["good_arm"]["mean"] > summary["bull"]["bad_arm"]["mean"]

    # After strong evidence, Thompson sampling should pick the good arm on almost every draw.
    picks = [bandit.select_arm("bull") for _ in range(50)]
    assert picks.count("good_arm") > picks.count("bad_arm")


def test_bandit_only_updates_from_realized_rewards_not_future_data() -> None:
    """The bandit's posterior for a regime/arm must have zero observations
    until at least one holding period using that arm has completed."""
    bandit = RegimeStrategyBandit(arms=("static_mvo", "mvo_ledoit_wolf", "full_pipeline"), seed=2)
    assert all(entry["n"] == 0 for regime in bandit.posterior_summary().values() for entry in regime.values())

    bandit.update("bear", "static_mvo", 0.5)
    summary = bandit.posterior_summary()
    assert summary["bear"]["static_mvo"]["n"] == 1
    # untouched entries remain at zero observations
    assert summary["bear"]["mvo_ledoit_wolf"]["n"] == 0
    assert summary["bull"]["static_mvo"]["n"] == 0


def test_run_adaptive_bandit_backtest_produces_valid_result() -> None:
    returns_df = _synthetic_returns(n_days=1100, n_assets=4)
    asset_classes = {ticker: "stock" for ticker in returns_df.columns}

    result, bandit = run_adaptive_bandit_backtest(returns_df, asset_classes, lookback_days=252, transaction_cost_bps=10.0)

    assert result.name == "adaptive_bandit"
    assert len(result.periods) > 0
    assert (result.equity_curve > 0).all()
    for period in result.periods:
        assert pytest.approx(sum(period.weights.values()), rel=1e-6) == 1.0

    # the bandit accumulated evidence for at least one (regime, arm) pair from the replay
    summary = bandit.posterior_summary()
    total_observations = sum(entry["n"] for regime in summary.values() for entry in regime.values())
    assert total_observations == len(result.periods)


def test_run_adaptive_bandit_backtest_raises_on_insufficient_history() -> None:
    returns_df = _synthetic_returns(n_days=50, n_assets=2)
    asset_classes = {ticker: "stock" for ticker in returns_df.columns}
    with pytest.raises(ValueError):
        run_adaptive_bandit_backtest(returns_df, asset_classes, lookback_days=252)
