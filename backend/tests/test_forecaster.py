from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from backend.quant.forecaster import ReturnForecaster


def _build_price_frame() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    dates = [start + timedelta(days=index) for index in range(140)]
    closes = [100 + index * 0.5 for index in range(140)]
    frame = pd.DataFrame(
        {
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [1_000_000 + index * 1000 for index in range(140)],
        },
        index=pd.to_datetime(dates),
    )
    return frame


def test_return_forecaster_loads_momentum_model_and_predicts() -> None:
    forecaster = ReturnForecaster().load()

    assert forecaster.model_kind == "momentum"
    assert getattr(forecaster.model, "n_features_in_", None) == 6

    prediction = forecaster.predict(_build_price_frame())

    assert isinstance(prediction, float)
    assert prediction == prediction