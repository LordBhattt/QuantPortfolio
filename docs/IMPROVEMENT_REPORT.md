# QP Smart Improvement Report

Selection uses four expanding windows ending before the cutoff. The score is mean
train Sharpe minus 0.25 times its cross-window standard deviation. The final 40%
is never read by selection. All candidates use the same class constraints and 10 bps cost.

Data: 2018-01-02 to 2026-11-12 (3237 rows).
Train cutoff: 2023-04-28. Selected configuration: **Inverse Volatility**.
SPY is a reference benchmark only and is not constrained across five asset classes.
The LTGILTDIR.NS bond history uses the documented TLT proxy.

## Held-out final 40%

| Candidate | Profit (INR) | Sharpe | Max drawdown | Turnover |
|---|---:|---:|---:|---:|
| Shrinkage, lambda=0 | 47,141.66 | 0.1452 | -16.51% | 0.0000 |
| Shrinkage, lambda=0.25 | 47,792.38 | 0.1517 | -16.14% | 0.0528 |
| Shrinkage, lambda=0.5 | 48,626.81 | 0.1581 | -16.72% | 0.1043 |
| Shrinkage, lambda=0.75 | 49,494.59 | 0.1629 | -17.28% | 0.1554 |
| Shrinkage | 50,251.75 | 0.1647 | -17.79% | 0.2067 |
| No-trade, band=2% | 50,683.04 | 0.1706 | -17.49% | 0.2028 |
| No-trade, band=2%, quarterly | 65,048.82 | 0.3587 | -16.59% | 0.2377 |
| No-trade, band=5% | 45,977.00 | 0.1077 | -18.15% | 0.1976 |
| No-trade, band=5%, quarterly | 68,068.86 | 0.4099 | -15.53% | 0.2304 |
| No-trade, band=10% | 48,726.78 | 0.1463 | -17.38% | 0.1711 |
| No-trade, band=10%, quarterly | 69,295.07 | 0.4114 | -14.91% | 0.2257 |
| Inverse Volatility | 38,276.24 | 0.0012 | -16.21% | 0.0111 |
| Risk Parity | 37,495.82 | -0.0140 | -15.43% | 0.0152 |
| Hierarchical Risk Parity | 41,186.99 | 0.0559 | -15.19% | 0.0557 |
| Volatility Model | 37,388.85 | -0.0160 | -16.57% | 0.0391 |
| Vol Target + Bear Overlay, target=12%, bear-cut=30% | 50,046.95 | 0.1621 | -17.79% | 0.2072 |
| SPY reference | 90,119.12 | 0.5483 | -18.76% | 0.0000 |

## Rolling out-of-sample windows

| Start | Selected config | Profit (INR) | Sharpe | Max drawdown | Turnover |
|---|---|---:|---:|---:|---:|
| 2018-01-02 | Shrinkage | 77,259.42 | 1.4785 | -20.75% | 0.0633 |
| 2018-05-08 | Hierarchical Risk Parity | 51,489.20 | 1.7311 | -5.98% | 0.0874 |
| 2018-09-11 | Risk Parity | 24,141.82 | 0.6249 | -6.43% | 0.0110 |
| 2019-01-15 | Risk Parity | -5,751.83 | -1.0683 | -17.51% | 0.0124 |
| 2019-05-21 | Risk Parity | -6,615.77 | -1.1119 | -18.42% | 0.0136 |

Rolling average: profit INR 28,104.57, Sharpe 0.3309, max drawdown -13.82%, turnover 0.0375.

## Model and strategy findings

Volatility model MAE was 0.1052 versus 0.0502 for trailing volatility, so it remains disabled.
Block-bootstrap annualized return-difference CI versus equal weight: [-0.0027, 0.0009], significant=False.
QP Smart is promoted only from train-window evidence. No held-out result is used to change settings.
No bootstrap Sharpe difference is claimed until the comparison is implemented over the same daily curves.
