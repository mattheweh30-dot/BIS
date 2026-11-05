#!/usr/bin/env python3
"""Run the simulation suite for the six requested names plus the three large caps.

Usage: python3 bis/run_sims.py
Writes: reports/sim_results.json  and prints a readable report.
"""

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mc_engine import (  # noqa: E402
    PCTS, TRADING_DAYS, bootstrap_block, bootstrap_block_jump, bootstrap_iid,
    bootstrap_block_volscaled, ewma_vol, event_reactions, excess_and_abnormal,
    gbm, load_prices,
    log_returns, realized_vol, sampling_error, summarize, vol_diagnostics,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- assumptions
RISK_FREE = 0.040          # stated assumption, not an estimate
DRIFT_SENSITIVITY = [-0.10, 0.0, 0.040, 0.10]
N_SMALL = 100              # as requested
N_LARGE = 50_000           # to expose N=100 sampling error
SE_REPS = 2000             # replications of the N=100 experiment
HORIZONS = {"21d": 21, "252d": TRADING_DAYS}
SEED = 20261105

# Today's regular-session closes (2026-11-05), from the live quote endpoint.
TODAY = "2026-11-05"
SPOT = {
    "AAPL": 344.33, "GOOG": 281.73, "NVDA": 181.59, "SPY": 733.2499,
    "WTI": 3.115, "TLRY": 2.82, "GAU": 2.115,
    "TSSI": 5.93, "IMXI": 7.28, "III": 5.95,
}

# Verified earnings report dates (all after-close "pm"), from the earnings endpoint.
EARNINGS = {
    "NVDA": ["2025-05-28", "2025-08-27", "2025-11-19",
             "2026-02-25", "2026-05-20", "2026-08-26"],
    "AAPL": ["2025-05-01", "2025-07-31", "2025-10-30", "2026-01-29",
             "2026-04-30", "2026-07-30", "2026-11-02"],
    "GOOG": ["2025-04-24", "2025-07-23", "2025-10-29", "2026-02-04",
             "2026-04-29", "2026-07-22", "2026-10-28"],
}

# Next scheduled report inside a horizon, as a 1-based trading-day step from today.
# NVDA reports 2026-11-17 after close -> first session that can price it is 2026-11-18.
# Trading days from 2026-11-05: 11/06=1, 11/09=2, 11/10=3, 11/11=4, 11/12=5,
# 11/13=6, 11/16=7, 11/17=8, 11/18=9.  (Veterans Day: equity markets open.)
NEXT_EARNINGS_STEP = {"NVDA": 9}

GROUPS = {
    "large cap": ["AAPL", "GOOG", "NVDA"],
    "penny (price < $5)": ["WTI", "TLRY", "GAU"],
    "micro cap ($50-300M)": ["TSSI", "IMXI", "III"],
}
ALL = [s for g in GROUPS.values() for s in g]


def pct(x, nd=1):
    return "n/a" if x != x else f"{x * 100:+.{nd}f}%"


def main():
    data = load_prices(os.path.join(HERE, "prices_all.csv"))
    rng = np.random.default_rng(SEED)
    out = {"as_of": TODAY, "assumptions": {
        "risk_free_drift": RISK_FREE, "n_small": N_SMALL, "n_large": N_LARGE,
        "se_replications": SE_REPS, "seed": SEED,
        "note": "bootstrap models are demeaned and re-drifted; trailing realized "
                "return is NOT used as a forecast"}, "symbols": {}}

    bdates, bcloses, binterp = data["SPY"]

    # -------------------------------------------------- Part 1: calibration
    print("=" * 100)
    print(f"PART 1 - CALIBRATION DIAGNOSTICS  (as of {TODAY} close)")
    print("=" * 100)
    print(f"{'sym':<6}{'spot':>9}{'today':>9}{'vol21':>8}{'vol63':>8}{'vol252':>8}"
          f"{'EWMA':>8}{'exKurt':>8}{'|r|ac1':>8}{'worst':>8}{'σ':>7}{'nobs':>6}")
    print("-" * 100)

    series = {}
    for sym in ALL:
        dates, closes, interp = data[sym]
        r, _ = log_returns(dates, closes, interp)
        # append today's realized move so EWMA registers the crash
        today_r = math.log(SPOT[sym] / closes[-1])
        r = np.append(r, today_r)
        series[sym] = r
        d = vol_diagnostics(r)
        rec = {
            "spot": SPOT[sym], "today_return": math.exp(today_r) - 1,
            "vol_21": realized_vol(r, 21), "vol_63": realized_vol(r, 63),
            "vol_252": realized_vol(r, 252), "vol_ewma": ewma_vol(r),
            "n_real_bars": int(len(r)),
            "n_interpolated_excluded": int(interp.sum()),
            "diagnostics": d,
        }
        out["symbols"][sym] = rec
        print(f"{sym:<6}{SPOT[sym]:>9.2f}{pct(rec['today_return']):>9}"
              f"{rec['vol_21'] * 100:>7.0f}%{rec['vol_63'] * 100:>7.0f}%"
              f"{rec['vol_252'] * 100:>7.0f}%{rec['vol_ewma'] * 100:>7.0f}%"
              f"{d['excess_kurtosis']:>8.1f}{d['abs_autocorr_lag1']:>8.2f}"
              f"{pct(math.exp(d['worst_day']) - 1, 0):>8}"
              f"{d['worst_day_sigmas']:>7.1f}{d['n_obs']:>6}")

    print("\nReading this table:")
    print("  exKurt > 0 means fatter tails than a normal (GBM assumes 0).")
    print("  |r|ac1 > 0 means volatility clusters: big days follow big days.")
    print("  EWMA vs vol252 is the gap between current and average conditions.")
    print(f"  TSSI excludes {int(data['TSSI'][2].sum())} synthetic bars "
          f"(no real trading before Nov 2024).")

    # ------------------------------------------- Part 2: earnings base rates
    print("\n" + "=" * 100)
    print("PART 2 - EARNINGS-DAY REACTION BASE RATES (after-close reports, day 0 = next session)")
    print("=" * 100)
    jump_pools = {}
    for sym, evs in EARNINGS.items():
        dates, closes, interp = data[sym]
        reactions = event_reactions(dates, closes, interp, evs, after_close=True)
        pool = [lr for _, _, lr in reactions]
        jump_pools[sym] = pool
        simple = [math.exp(x) - 1 for x in pool]
        print(f"\n{sym}  n={len(pool)} "
              f"{'(THIN BASE RATE)' if len(pool) < 8 else ''}")
        for (ed, rd, lr) in reactions:
            print(f"   reported {ed} -> reaction {rd}: {pct(math.exp(lr) - 1)}")
        if simple:
            a = np.array(simple)
            print(f"   median {pct(float(np.median(a)))}  mean {pct(float(a.mean()))}  "
                  f"stdev {abs(float(a.std(ddof=1))) * 100:.1f}pp  "
                  f"range {pct(float(a.min()))} to {pct(float(a.max()))}  "
                  f"up {int((a > 0).sum())}/{len(a)}")
            out["symbols"][sym]["earnings_reactions"] = {
                "n": len(simple), "median": float(np.median(a)),
                "mean": float(a.mean()), "sd": float(a.std(ddof=1)),
                "min": float(a.min()), "max": float(a.max()),
                "detail": [{"reported": e, "reaction_date": d,
                            "return": math.exp(l) - 1} for e, d, l in reactions],
            }

    # GOOG event study, measured properly against SPY
    print("\n" + "-" * 100)
    print("Event study: GOOG Q3 2026 report (2026-10-28 pm), measured vs SPY")
    gd, gc, gi = data["GOOG"]
    ev = excess_and_abnormal(gd, gc, bdates, bcloses, "2026-10-28", after_close=True)
    if ev:
        print(f"   reaction session {ev['date']}")
        print(f"   raw      {pct(math.exp(ev['raw']) - 1)}")
        print(f"   SPY      {pct(math.exp(ev['benchmark']) - 1)}")
        print(f"   excess   {pct(math.exp(ev['excess']) - 1)}")
        print(f"   beta     {ev['beta']:.2f} (250 sessions pre-event)")
        print(f"   abnormal {pct(math.exp(ev['abnormal']) - 1)}  <- idiosyncratic component")
        out["goog_event_study"] = {k: (float(v) if isinstance(v, float) else v)
                                   for k, v in ev.items()}

    # ------------------------------------------------- Part 3: simulations
    print("\n" + "=" * 100)
    print(f"PART 3 - SIMULATIONS  (N={N_SMALL} as requested, vs N={N_LARGE:,})")
    print(f"Drift assumption: {RISK_FREE:.1%} annual for every name. "
          f"Bootstraps demeaned and re-drifted.")
    print("=" * 100)

    for hname, H in HORIZONS.items():
        print(f"\n\n{'#' * 100}\nHORIZON: {hname} ({H} trading days)\n{'#' * 100}")
        for gname, syms in GROUPS.items():
            print(f"\n--- {gname} ---")
            for sym in syms:
                r = series[sym]
                s0 = SPOT[sym]
                ewma = ewma_vol(r)
                hist_vol = realized_vol(r, 252)
                hist_mu = float(r.mean()) * TRADING_DAYS

                jd = NEXT_EARNINGS_STEP.get(sym)
                jump_day = (jd - 1) if (jd is not None and jd <= H) else None

                models = {
                    "gbm_hist_NAIVE": lambda n, g, s=s0, m=hist_mu, v=hist_vol, h=H:
                        gbm(s, m, v, h, n, g),
                    "gbm_ewma": lambda n, g, s=s0, v=ewma, h=H:
                        gbm(s, RISK_FREE, v, h, n, g),
                    "boot_iid": lambda n, g, s=s0, rr=r, h=H:
                        bootstrap_iid(s, rr, RISK_FREE, h, n, g),
                    "boot_block": lambda n, g, s=s0, rr=r, h=H:
                        bootstrap_block(s, rr, RISK_FREE, h, n, g),
                    "boot_block_voltgt": lambda n, g, s=s0, rr=r, h=H, tv=ewma:
                        bootstrap_block_volscaled(s, rr, RISK_FREE, h, n, g, tv),
                }
                if jump_day is not None:
                    models["boot_block_earnings"] = (
                        lambda n, g, s=s0, rr=r, h=H, jp=jump_pools.get(sym), jday=jump_day:
                        bootstrap_block_jump(s, rr, RISK_FREE, h, n, g, jp, jday))

                print(f"\n  {sym}  spot ${s0:,.2f}   EWMA vol {ewma:.0%}   "
                      f"252d vol {hist_vol:.0%}"
                      + (f"   [earnings jump at step {jd}]" if jump_day is not None else ""))
                print(f"    {'model':<22}{'N':>7}{'p5':>9}{'p25':>9}{'p50':>9}"
                      f"{'p75':>9}{'p95':>9}{'P(loss)':>9}{'ES5%':>9}{'maxDD':>8}")

                rec = out["symbols"][sym].setdefault("sims", {}).setdefault(hname, {})
                for mname, gen in models.items():
                    for N in (N_SMALL, N_LARGE):
                        paths = gen(N, rng)
                        s = summarize(paths, s0)
                        rec.setdefault(mname, {})[f"n{N}"] = s
                        print(f"    {mname:<22}{N:>7,}"
                              f"{pct(s['pct'][5], 0):>9}{pct(s['pct'][25], 0):>9}"
                              f"{pct(s['pct'][50], 0):>9}{pct(s['pct'][75], 0):>9}"
                              f"{pct(s['pct'][95], 0):>9}"
                              f"{s['p_loss'] * 100:>8.0f}%{pct(s['es_5'], 0):>9}"
                              f"{pct(s['mean_max_drawdown'], 0):>8}")

    # ------------------------------- Part 4: is N=100 enough? (sampling error)
    print("\n" + "=" * 100)
    print(f"PART 4 - SAMPLING ERROR OF N={N_SMALL}: the whole N={N_SMALL} experiment "
          f"re-run {SE_REPS:,} times")
    print("=" * 100)
    print("If the sd column is large relative to the estimate, N=100 cannot support "
          "the number.\n")
    print(f"{'sym':<7}{'horizon':<9}{'stat':<9}{'N=100 mean':>12}{'sd':>9}"
          f"{'90% band of the N=100 answer':>34}{'N=50k truth':>13}")
    print("-" * 100)
    for sym in ALL:
        r, s0 = series[sym], SPOT[sym]
        for hname, H in HORIZONS.items():
            gen = lambda n, g, s=s0, rr=r, h=H: bootstrap_block(s, rr, RISK_FREE, h, n, g)
            se = sampling_error(gen, s0, N_SMALL, SE_REPS, rng)
            truth = summarize(gen(N_LARGE, rng), s0)
            for stat in (5, 50):
                e = se[stat]
                print(f"{sym:<7}{hname:<9}{'p' + str(stat):<9}"
                      f"{pct(e['mean']):>12}{e['sd'] * 100:>8.1f}pp"
                      f"{'[' + pct(e['p05']) + ' , ' + pct(e['p95']) + ']':>34}"
                      f"{pct(truth['pct'][stat]):>13}")
            e = se["p_loss"]
            print(f"{sym:<7}{hname:<9}{'P(loss)':<9}{e['mean'] * 100:>11.0f}%"
                  f"{e['sd'] * 100:>8.1f}pp"
                  f"{'[' + f'{e[chr(112) + chr(48) + chr(53)] * 100:.0f}%' + ' , ' + f'{e[chr(112) + chr(57) + chr(53)] * 100:.0f}%' + ']':>34}"
                  f"{truth['p_loss'] * 100:>12.0f}%")
            out["symbols"][sym].setdefault("sampling_error", {})[hname] = se

    # ----------------------------------------- Part 5: drift sensitivity
    print("\n" + "=" * 100)
    print("PART 5 - DRIFT SENSITIVITY (252d, block bootstrap, N=50,000)")
    print("Shows which assumption actually drives the answer at each horizon.")
    print("=" * 100)
    print(f"{'sym':<7}" + "".join(f"{f'mu={m:+.0%}':>26}" for m in DRIFT_SENSITIVITY))
    print(f"{'':<7}" + "".join(f"{'p5 / p50 / p95':>26}" for _ in DRIFT_SENSITIVITY))
    print("-" * 110)
    for sym in ALL:
        r, s0 = series[sym], SPOT[sym]
        cells = []
        for m in DRIFT_SENSITIVITY:
            s = summarize(bootstrap_block(s0, r, m, TRADING_DAYS, N_LARGE, rng), s0)
            cells.append(f"{pct(s['pct'][5], 0)}/{pct(s['pct'][50], 0)}/{pct(s['pct'][95], 0)}")
            out["symbols"][sym].setdefault("drift_sensitivity", {})[f"{m:+.3f}"] = {
                "p5": s["pct"][5], "p50": s["pct"][50], "p95": s["pct"][95]}
        print(f"{sym:<7}" + "".join(f"{c:>26}" for c in cells))

    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    dest = os.path.join(ROOT, "reports", "sim_results.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2, default=float)
    print(f"\n\nWrote {dest}")


if __name__ == "__main__":
    main()
