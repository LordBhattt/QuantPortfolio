# QP Smart Improvement Report

## Evaluation protocol

The evaluation uses daily data from 2018-01-02 through 2026-11-12, with the
first 60% ending 2023-04-28 used for all selection. The final 40% starts
2023-04-29 and is never read by selection. Each strategy uses the same class
constraints and 10 bps turnover cost. SPY is a reference benchmark only; it
does not satisfy the portfolio's five asset-class constraints.

The bond holding `LTGILTDIR.NS` has no Yahoo history. Its five-year evaluation
series uses the documented liquid bond ETF proxy `TLT`; all other demo holdings
use their own complete five-year histories. This proxy limitation does not
change the selection split.

## Train-part choices

The selected configuration is **Shrinkage, lambda=0**, which is equal weight
(the optimizer component receives zero weight). It was selected using the
highest train-period Sharpe, with volatility-model candidates rejected unless
their train-internal 60/40 validation error beat trailing volatility. The
volatility model failed that gate: model MAE 0.4796 versus trailing-vol MAE
0.0503.

## Held-out results (final 40%)

| Candidate | Profit (INR) | Sharpe | Max drawdown | Turnover |
|---|---:|---:|---:|---:|
| Shrinkage, lambda=0 (selected) | 47,141.66 | 0.1452 | -16.51% | 0.0000 |
| Shrinkage, lambda=0.25 | 47,792.38 | 0.1517 | -16.14% | 0.0528 |
| Shrinkage, lambda=0.5 | 48,626.81 | 0.1581 | -16.72% | 0.1043 |
| Shrinkage, lambda=0.75 | 49,494.60 | 0.1629 | -17.28% | 0.1554 |
| No-trade, 2%, monthly | 50,557.59 | 0.1687 | -17.65% | 0.2057 |
| No-trade, 2%, quarterly | 64,202.14 | 0.3482 | -16.71% | 0.2424 |
| No-trade, 5%, monthly | 50,772.94 | 0.1717 | -18.09% | 0.2030 |
| No-trade, 5%, quarterly | 64,202.14 | 0.3482 | -16.71% | 0.2424 |
| No-trade, 10%, monthly | 51,612.80 | 0.1829 | -18.09% | 0.1976 |
| No-trade, 10%, quarterly | 64,584.94 | 0.3510 | -16.71% | 0.2400 |
| Inverse volatility | 38,276.26 | 0.0012 | -16.21% | 0.0111 |
| Risk parity | 37,495.81 | -0.0140 | -15.43% | 0.0152 |
| Hierarchical risk parity | 47,141.66 | 0.1452 | -16.51% | 0.0000 |
| Volatility model (rejected) | 37,388.86 | -0.0160 | -16.57% | 0.0391 |
| Vol target + bear overlay | 50,251.76 | 0.1647 | -17.79% | 0.2067 |
| SPY reference | 90,119.12 | — | — | — |

No candidate was selected from this held-out table. The selected QP Smart
configuration is therefore equal weight and does not beat the best held-out
candidate or SPY. The best held-out risk-adjusted result was no-trade 10% with
quarterly rebalancing, but it was not promoted because that choice would use
held-out information.

## Rolling selected-window averages

Three rolling starts were evaluated with the same 60/40 train/test rule. The
selected configurations were Risk Parity, Risk Parity, and Inverse Volatility.
Their average held-out result was profit **INR 19,566.11**, Sharpe **0.1819**,
max drawdown **-14.43%**, and turnover **0.0126**.

## What did not work

- The volatility model was materially worse than trailing volatility and is
  gated off.
- Risk parity and inverse volatility were not consistently better than equal
  weight across rolling starts.
- The bear overlay reduced held-out return without improving drawdown enough to
  justify selection.
- The honest train-only winner is equal weight; QP Smart is retained as a
  transparent, leakage-safe strategy rather than claiming an improvement that
  the data does not support.
