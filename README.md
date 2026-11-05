# BIS

Monte Carlo risk-distribution engine for equities, built on an authenticated daily
price feed.

- `bis/mc_engine.py` — path generators (GBM, iid bootstrap, stationary block bootstrap,
  variance-targeted block bootstrap, scheduled-jump overlay), volatility estimators
  (realized, EWMA), distribution diagnostics, and event-study measurement
  (excess and beta-adjusted abnormal returns).
- `bis/run_sims.py` — the study: calibration diagnostics, earnings base rates,
  simulations at 21 and 252 trading days, N=100 sampling-error quantification, and
  drift sensitivity. Deterministic (seed 20261105).
- `reports/simulation_results.md` — findings and limitations.
- `CLAUDE.md` — modelling and data rules derived from errors caught here. Read it first.

Run: `python3 bis/run_sims.py`

This produces risk distributions, not forecasts. Not investment advice.
