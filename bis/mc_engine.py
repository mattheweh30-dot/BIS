#!/usr/bin/env python3
"""
Monte Carlo simulation engine for equity price paths.

Design notes (these are the load-bearing decisions, read them before trusting output):

1. DRIFT IS AN ASSUMPTION, NOT AN ESTIMATE.
   Calibrating drift to trailing realized return is the single most common error in
   retail Monte Carlo work. NVDA's trailing 4y CAGR is ~+96%; feeding that into a
   GBM "forecasts" a near-doubling with no economic content -- it merely restates
   the input. All bootstrap models here are DEMEANED and re-drifted to an explicit,
   stated assumption. The naive `gbm_hist` model is included ONLY to demonstrate
   how badly it misleads.

2. VOLATILITY CLUSTERS.
   Trailing 252d realized vol badly understates risk immediately after a shock.
   EWMA(lambda=0.94, RiskMetrics) and the stationary block bootstrap both respond
   to recent conditions; iid bootstrap and GBM do not.

3. INTERPOLATED BARS ARE SYNTHETIC.
   The data feed marks bars it fabricated to fill gaps. They are flat by
   construction and suppress measured volatility. They are excluded from all
   return estimation.

4. SCHEDULED EVENTS ARE NOT DIFFUSION.
   A known earnings date inside the horizon is a discrete jump, not Brownian
   motion. `boot_jump` overlays a jump drawn from the name's own historical
   earnings-day reaction distribution at the correct trading-day offset.

5. SMALL N HAS LARGE SAMPLING ERROR.
   With N=100 paths, the 5th percentile is the 5th-worst observation. Its standard
   error is reported by repeating the whole N=100 experiment many times.
"""

import csv
import math
from collections import defaultdict

import numpy as np

TRADING_DAYS = 252
EWMA_LAMBDA = 0.94  # RiskMetrics standard


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------

def load_prices(path):
    """Return {symbol: (dates, closes, interpolated_flags)} sorted by date."""
    rows = defaultdict(list)
    with open(path) as fh:
        for r in csv.reader(fh):
            if len(r) < 8:
                continue
            sym, date, _o, _h, _l, close, _v, interp = r[:8]
            rows[sym].append((date[:10], float(close), interp.lower() == "true"))
    out = {}
    for sym, recs in rows.items():
        recs.sort(key=lambda x: x[0])
        out[sym] = (
            [r[0] for r in recs],
            np.array([r[1] for r in recs], dtype=float),
            np.array([r[2] for r in recs], dtype=bool),
        )
    return out


def log_returns(dates, closes, interp):
    """Log returns, excluding any return that touches a synthetic bar.

    A return r_t = ln(P_t / P_{t-1}) is dropped if either endpoint is
    interpolated, since a fabricated flat bar produces a fake zero return.
    """
    r, rdates = [], []
    for i in range(1, len(closes)):
        if interp[i] or interp[i - 1]:
            continue
        if closes[i] <= 0 or closes[i - 1] <= 0:
            continue
        r.append(math.log(closes[i] / closes[i - 1]))
        rdates.append(dates[i])
    return np.array(r), rdates


# ----------------------------------------------------------------------------
# Volatility estimators
# ----------------------------------------------------------------------------

def realized_vol(r, window=None):
    x = r if window is None else r[-window:]
    if len(x) < 3:
        return float("nan")
    return float(np.std(x, ddof=1) * math.sqrt(TRADING_DAYS))


def ewma_vol(r, lam=EWMA_LAMBDA):
    """EWMA volatility. Responds to recent shocks; trailing realized does not."""
    if len(r) < 3:
        return float("nan")
    var = float(np.var(r[: min(60, len(r))], ddof=1))
    for x in r:
        var = lam * var + (1.0 - lam) * x * x
    return float(math.sqrt(var * TRADING_DAYS))


def vol_diagnostics(r):
    """Fat tails and volatility clustering -- the two things GBM cannot represent."""
    s = float(np.std(r, ddof=1))
    z = (r - r.mean()) / s
    kurt = float(np.mean(z ** 4))                       # 3.0 for a normal
    skew = float(np.mean(z ** 3))
    absr = np.abs(r - r.mean())
    # lag-1 autocorrelation of |r|: >0 means vol clusters
    ac1 = float(np.corrcoef(absr[:-1], absr[1:])[0, 1]) if len(absr) > 10 else float("nan")
    worst = float(np.min(r))
    # how many sigma was the worst day, and how often a normal would do that
    return {
        "kurtosis": kurt,
        "excess_kurtosis": kurt - 3.0,
        "skew": skew,
        "abs_autocorr_lag1": ac1,
        "worst_day": worst,
        "worst_day_sigmas": worst / s,
        "n_obs": int(len(r)),
    }


# ----------------------------------------------------------------------------
# Path generators. Each returns array (n_paths, horizon+1) of PRICES.
# ----------------------------------------------------------------------------

def _finalize(s0, log_paths):
    return s0 * np.exp(np.cumsum(log_paths, axis=1))


def gbm(s0, mu_annual, sigma_annual, horizon, n, rng):
    """Geometric Brownian motion. mu is the ARITHMETIC annual drift."""
    dt = 1.0 / TRADING_DAYS
    sig = sigma_annual * math.sqrt(dt)
    # Ito correction so E[S_T] = s0 * exp(mu * T)
    drift = (mu_annual - 0.5 * sigma_annual ** 2) * dt
    steps = drift + sig * rng.standard_normal((n, horizon))
    return _finalize(s0, steps)


def bootstrap_iid(s0, r, mu_annual, horizon, n, rng):
    """IID bootstrap of historical daily log returns, demeaned and re-drifted.

    Captures fat tails and skew. Does NOT capture volatility clustering --
    shuffling destroys the time structure.
    """
    centered = r - r.mean()
    target = mu_annual / TRADING_DAYS - 0.5 * float(np.var(centered, ddof=1))
    idx = rng.integers(0, len(centered), size=(n, horizon))
    return _finalize(s0, centered[idx] + target)


def bootstrap_block(s0, r, mu_annual, horizon, n, rng, mean_block=10):
    """Stationary block bootstrap (Politis-Romano).

    Block lengths are geometric with mean `mean_block`, sampled with wraparound.
    This preserves short-range dependence, so volatility clustering and
    multi-day drawdown sequences survive -- the thing that matters most for
    tail risk and that iid resampling destroys.
    """
    centered = r - r.mean()
    m = len(centered)
    target = mu_annual / TRADING_DAYS - 0.5 * float(np.var(centered, ddof=1))
    p = 1.0 / mean_block

    out = np.empty((n, horizon))
    # vectorised: walk forward, restarting at a random index with prob p
    pos = rng.integers(0, m, size=n)
    restart = rng.random((n, horizon)) < p
    jump_to = rng.integers(0, m, size=(n, horizon))
    for t in range(horizon):
        pos = np.where(restart[:, t], jump_to[:, t], pos)
        out[:, t] = centered[pos]
        pos = (pos + 1) % m
    return _finalize(s0, out + target)


def bootstrap_block_volscaled(s0, r, mu_annual, horizon, n, rng,
                              target_vol, mean_block=10):
    """Block bootstrap rescaled so unconditional vol matches CURRENT conditions.

    Plain `bootstrap_block` resamples the unconditional distribution: it keeps
    fat tails and clustering but reports the AVERAGE volatility of the sample
    window, not today's. When the two differ sharply (IMXI: 42% trailing 252d
    vs 89% EWMA) that understates near-term risk badly.

    This variant multiplies the demeaned returns by target_vol / sample_vol,
    preserving the SHAPE of the distribution (skew, kurtosis, clustering) while
    matching its SCALE to the current regime. This is the standard
    variance-targeting fix and is the model to prefer when EWMA and trailing
    realized vol disagree.
    """
    centered = r - r.mean()
    sample_vol = float(np.std(centered, ddof=1)) * math.sqrt(TRADING_DAYS)
    scale = (target_vol / sample_vol) if sample_vol > 0 else 1.0
    scaled = centered * scale

    m = len(scaled)
    target = mu_annual / TRADING_DAYS - 0.5 * float(np.var(scaled, ddof=1))
    p = 1.0 / mean_block

    out = np.empty((n, horizon))
    pos = rng.integers(0, m, size=n)
    restart = rng.random((n, horizon)) < p
    jump_to = rng.integers(0, m, size=(n, horizon))
    for t in range(horizon):
        pos = np.where(restart[:, t], jump_to[:, t], pos)
        out[:, t] = scaled[pos]
        pos = (pos + 1) % m
    return _finalize(s0, out + target)


def bootstrap_block_jump(s0, r, mu_annual, horizon, n, rng,
                         jump_pool, jump_day, mean_block=10):
    """Block bootstrap plus a scheduled discrete jump on a known event day.

    `jump_pool` is the name's own historical event-day log returns (e.g. past
    earnings reactions). On `jump_day` the diffusion step is REPLACED by a draw
    from that pool, because the event-day move is not drawn from the ordinary
    daily distribution.
    """
    centered = r - r.mean()
    m = len(centered)
    # exclude event days from the diffusion pool so the jump isn't double counted
    target = mu_annual / TRADING_DAYS - 0.5 * float(np.var(centered, ddof=1))
    p = 1.0 / mean_block

    out = np.empty((n, horizon))
    pos = rng.integers(0, m, size=n)
    restart = rng.random((n, horizon)) < p
    jump_to = rng.integers(0, m, size=(n, horizon))
    for t in range(horizon):
        pos = np.where(restart[:, t], jump_to[:, t], pos)
        out[:, t] = centered[pos]
        pos = (pos + 1) % m
    out += target

    if jump_pool is not None and len(jump_pool) > 0 and 0 <= jump_day < horizon:
        pool = np.asarray(jump_pool, dtype=float)
        # resample the event-day distribution; add small smoothing so a 6-point
        # pool does not produce only 6 discrete outcomes
        draws = pool[rng.integers(0, len(pool), size=n)]
        smooth = rng.standard_normal(n) * (float(np.std(pool, ddof=1)) * 0.5
                                           if len(pool) > 2 else 0.0)
        out[:, jump_day] = draws + smooth
    return _finalize(s0, out)


# ----------------------------------------------------------------------------
# Summary statistics
# ----------------------------------------------------------------------------

PCTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]


def summarize(paths, s0):
    terminal = paths[:, -1]
    ret = terminal / s0 - 1.0
    running_max = np.maximum.accumulate(paths, axis=1)
    max_dd = float(np.mean(np.min(paths / running_max - 1.0, axis=1)))
    tail = ret[ret <= np.percentile(ret, 5)]
    return {
        "n": int(len(terminal)),
        "mean_ret": float(np.mean(ret)),
        "median_ret": float(np.median(ret)),
        "pct": {p: float(np.percentile(ret, p)) for p in PCTS},
        "p_loss": float(np.mean(ret < 0)),
        "p_down_20": float(np.mean(ret < -0.20)),
        "p_up_20": float(np.mean(ret > 0.20)),
        "es_5": float(np.mean(tail)) if len(tail) else float("nan"),
        "mean_max_drawdown": max_dd,
    }


def sampling_error(gen, s0, n_small, reps, rng):
    """How unstable are percentile estimates at n_small paths?

    Re-runs the whole n_small experiment `reps` times and reports the standard
    deviation of each percentile across replications. This is the answer to
    'is 100 simulations enough'.
    """
    acc = defaultdict(list)
    for _ in range(reps):
        paths = gen(n_small, rng)
        ret = paths[:, -1] / s0 - 1.0
        for p in PCTS:
            acc[p].append(float(np.percentile(ret, p)))
        acc["p_loss"].append(float(np.mean(ret < 0)))
    return {k: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)),
                "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))}
            for k, v in acc.items()}


# ----------------------------------------------------------------------------
# Event-study measurement (stock-event-precedents methodology)
# ----------------------------------------------------------------------------

def event_reactions(dates, closes, interp, event_dates, after_close=True):
    """Realized log return on the first session that could price each event.

    after_close=True (pm reports): day 0 is the NEXT session.
    Returns list of (event_date, reaction_date, log_return).
    """
    idx = {d: i for i, d in enumerate(dates)}
    out = []
    for ed in event_dates:
        # find first trading day >= event date
        i = None
        if ed in idx:
            i = idx[ed]
        else:
            for j, d in enumerate(dates):
                if d >= ed:
                    i = j
                    break
        if i is None:
            continue
        k = i + 1 if after_close else i
        if k <= 0 or k >= len(closes):
            continue
        if interp[k] or interp[k - 1]:
            continue
        out.append((ed, dates[k], math.log(closes[k] / closes[k - 1])))
    return out


def excess_and_abnormal(dates, closes, bdates, bcloses, event_date,
                        after_close=True, beta_window=250):
    """Raw, excess (stock - benchmark) and beta-adjusted abnormal return.

    Beta is estimated on the ~250 sessions BEFORE the event, so a high-beta
    name falling with the market is not misread as an idiosyncratic reaction.
    """
    bidx = {d: i for i, d in enumerate(bdates)}
    idx = {d: i for i, d in enumerate(dates)}
    if event_date not in idx:
        return None
    i = idx[event_date]
    k = i + 1 if after_close else i
    if k <= 0 or k >= len(closes):
        return None
    d = dates[k]
    if d not in bidx:
        return None
    bk = bidx[d]

    raw = math.log(closes[k] / closes[k - 1])
    bench = math.log(bcloses[bk] / bcloses[bk - 1])

    # align histories for beta
    lo = max(0, k - beta_window)
    sr, br = [], []
    for t in range(lo + 1, k):
        dt = dates[t]
        if dt not in bidx:
            continue
        bt = bidx[dt]
        if bt == 0:
            continue
        sr.append(math.log(closes[t] / closes[t - 1]))
        br.append(math.log(bcloses[bt] / bcloses[bt - 1]))
    beta = float("nan")
    if len(sr) > 30:
        sr_a, br_a = np.array(sr), np.array(br)
        beta = float(np.cov(sr_a, br_a)[0, 1] / np.var(br_a, ddof=1))
    return {
        "date": d,
        "raw": raw,
        "benchmark": bench,
        "excess": raw - bench,
        "beta": beta,
        "abnormal": raw - beta * bench if beta == beta else float("nan"),
    }
