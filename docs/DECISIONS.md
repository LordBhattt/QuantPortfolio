# Engineering Decisions

## Local-first runtime

The default database is SQLite and the cache falls back to in-memory storage
when Redis is unavailable. Docker Compose overrides those defaults with local
Postgres and Redis services. This keeps a fresh checkout usable without
external infrastructure while preserving a production-like local stack.

## Market data and proxies

`backend/scripts/download_data.py` is the reproducible price and macro-data
entry point. It writes parquet files and a quality report. `LTGILTDIR.NS` has
no reliable Yahoo history, so `TLT` is used as a clearly labelled bond proxy.
The proxy is not presented as the Indian security's own history.

## QP Smart selection

Candidate settings are scored on four expanding windows ending before the
selection cutoff. The score is mean Sharpe minus 0.25 times the cross-window
standard deviation. The final 40 percent is never read by selection. Models
that fail their train-internal validation gate remain disabled.

## ML defaults

Return and volatility models are optional evidence, not assumptions. A model
is enabled only when its out-of-sample metrics beat the relevant baseline and
pass the documented IC and t-stat gates. Otherwise the UI reports that ML was
not used.
