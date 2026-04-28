"""PyTorch LSTM definition used by the return forecaster."""

import torch
import torch.nn as nn


class LSTMForecaster(nn.Module):
    def __init__(
        self,
        input_size: int = 5,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
        forecast_horizon: int = 30,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_size, forecast_horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        values, _ = self.lstm(x)
        return self.output(self.dropout(values[:, -1, :]))
