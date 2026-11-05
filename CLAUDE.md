# BIS — working notes for equity simulation work

These are rules derived from mistakes actually made and caught in this repo, not general
advice. Read before building or extending anything in `bis/`.

**On "train yourself":** nothing in a session changes model weights. This file is the
real mechanism — it is loaded automatically by future Claude Code sessions in this repo.
Durable lessons belong here; everything else evaporates when the container is reclaimed.

---

## Modelling rules

**1. Never put a trailing CAGR in the drift slot.** This is the single highest-impact
error available. NVDA's trailing 4-year CAGR was +96.5%; a GBM calibrated to it assigned
a **7% probability of losing money over a year** on a stock that had just fallen 9.26% in
a day and 25% from its high. The same model put TLRY's median at −62%. It is not
optimistic — it extrapolates momentum in whichever direction the window ran, while
keeping the appearance of rigour. Demean the data and apply an explicit, stated drift.
Then publish the drift sensitivity so the reader can substitute their own.

**2. Calibrate volatility to the current regime, not the sample average.** Compare EWMA
(λ=0.94) against trailing 252-day and look at the ratio. If it is far from 1.0,
unconditional resampling is wrong. IMXI: ratio 2.12, and vol targeting moved its 1-month
p5 from −23% to −39% and its 1-year P(loss) from 55% to 65%. Use
`bootstrap_block_volscaled`. The correction cuts both ways — it *lowered* risk for TSSI
and TLRY, whose trailing vol was stale and high.

**3. Volatility drag dominates everything for high-vol names.** Median grows at
`mu − σ²/2`. At σ=109% (TSSI) the drag is 59%/yr, so a +4% expected return still implies
a −55% median drift and 70% P(loss). Always state this explicitly — otherwise a positive
expected return and a majority-chance of loss look contradictory when they are not.

**4. Scheduled events are jumps, not diffusion.** Check the earnings calendar before
choosing a horizon. But **verify the jump actually matters**: NVDA's historical
earnings-reaction SD was 5.1pp while its current daily SD was 3.2pp, so earnings was only
~1.6× an ordinary day and the overlay barely shifted the distribution. Measure before
assuming an event is the dominant risk.

**5. Report sampling error whenever N is small.** Re-run the whole experiment and report
the SD of each statistic. `P(loss)` from N=100 has SD ≈ 5.0pp — exactly
`sqrt(0.25/100)` — so ±10pp at 95%, enough to flip 45% into 55%. N=100 is adequate only
for the median of a low-vol name at a short horizon. 50,000 paths cost milliseconds;
there is no reason to accept the error.

**6. Simulate the portfolio, not just the marginals.** Independent per-name simulation
understates joint drawdown. On 2026-11-05, SPY fell 4.38% and 8 of 9 names fell together.
Marginal distributions are fine for single-name risk and misleading for portfolio risk.

**7. Know what the model structurally cannot say.** For sub-$5 names the dominant
mechanisms are *dilution* and *default*, and a per-share diffusion model represents
neither. TLRY at 0.26× book issues equity routinely; WTI has negative book equity. For
those two, this omission outweighs anything in the volatility modelling. Say so rather
than letting clean percentiles imply coverage that does not exist.

---

## Data rules (this feed specifically)

**8. Check the `interpolated` flag on every bar.** TSSI returned 1,006 bars of which
**512 were synthetic** — the vendor fabricates them to fill gaps and documents that they
"carry no new information." They are flat, so they suppress measured volatility. Drop any
return touching one. TSSI's real history began November 2024 (~494 bars), covering one
theme's boom and bust — a regime-limited sample, not four years of evidence.

**9. Do not trust the screener's fundamental columns. Re-verify every one.** The scanner
reported DSP at $278M (actual **$841M**, 3.0× off) and INR at $235M (actual **$777M**,
3.3× off). Both would have been wrongly admitted as micro caps. `get_equity_fundamentals`
is authoritative; the scanner's `Market cap` column is not.

**10. `asset_type = STOCK` does not mean operating company.** It admits closed-end funds,
muni-bond funds, SPACs, BDCs and REITs. A penny screen surfaced OXLC (a CLO fund) as its
top hit; a micro-cap screen returned PCQ, OIA, DSM, NHS, FTF, MFM (bond funds), NTWO,
SVCC, BACC (SPACs, identifiable by HV ≈ 0.02–0.10 against trust value), RWAY (BDC) and
SEVN (REIT). Filter by hand.

**11. Low share price and small company size are orthogonal.** A `price < $5` screen
returned **11 names above $5B market cap** — AmBev $42.8B, Banco Bradesco $27.4B, Wipro
$20.2B, Stellantis $17.6B. Apply both a price and a cap filter, and say which definition
is in use.

**12. Absurd HV readings mark untradeable names, not opportunities.** ZONE showed HV
26.41 and ENHA 7.88 (i.e. 788%). These are illiquidity and manipulation artifacts. Also
cross-check reported volume against average volume — SVCC showed volume 2,122 against an
average of 309,920, i.e. a stale print.

**13. Check the bid/ask before calling a small cap liquid.** III's after-hours spread was
4.81/7.05 (~38%). Execution cost can exceed a month of modelled median return, which no
price simulation captures.

**14. Large tool payloads spill to a file — use `jq`, don't read them into context.**
Historicals for 4–6 symbols exceed the token limit. The result message gives the path.
Note the bar array key is **`bars`**, not `historicals`.

**15. A suspiciously cheap multiple usually has a non-operating cause — find it before
using it.** GOOG showed a P/E of 15.0 at a $3.45T cap. Cause: trailing EPS prints of
$5.11 and $9.11 against ~$2.9 estimates were equity-investment marks, reversing to $2.12
on an $8.7B paper loss. The denominator was inflated by non-operating swings. Not cheap —
mismeasured.

---

## Analysis rules

**16. Measure event reactions against a benchmark, with beta.** Raw moves conflate market
and idiosyncratic components. GOOG on 2026-10-29: raw −12.3%, SPY −0.4%, beta 1.36,
abnormal **−11.8%**. Estimate beta on the ~250 sessions *before* the event so a high-beta
name falling with the market is not misread as a reaction.

**17. For after-close ("pm") reports, day 0 is the next session.** Getting this wrong
shifts every reaction by one day and silently corrupts the base rate.

**18. "Beats consensus" does not mean "stock rises."** NVDA beat EPS in 6/6 quarters
(+28%, +6.1%, +6.6%, +8.0%, +6.3%, +6.2%) and the stock *fell on 4 of 6 reactions*,
median −1.3%. The estimate is not what is priced. Check the reaction base rate, never
infer it from the surprise record.

**19. Establish whether the day is idiosyncratic or market-wide before interpreting
anything.** A −9.26% NVDA print reads very differently against SPY −0.4% than against
SPY −4.38%. Pull the index first.

**20. Flag thin base rates in the text, not just a footnote.** The earnings API returns
8 quarters, so n is typically 6–7. That is weak evidence and must be labelled as such
wherever a number derived from it appears.

---

## Process rules

**21. Match the skill's mode to the deliverable.** `equity-research` and
`stock-event-precedents` default to full branded-PDF workflows with subagents.
`stock-event-precedents` has an explicit **quick mode** for non-report questions — use
its *methodology* (day-0 identification, excess and beta-adjusted returns, the
d0–1/d0–5/d0–21/d0–63 windows) against the authenticated feed rather than running the
whole report pipeline when the ask was a simulation. Its own instructions say to.

**22. State the uncomfortable constraint first.** "100 simulations" was statistically
inadequate for the tail statistics requested, and the two named skills do not perform
simulation. Both needed saying before any numbers, not after.

**23. Audit your own engine before shipping it.** The unconditional block bootstrap
passed every test and was still wrong for IMXI by 17 points at the 5th percentile,
because it answered a subtly different question than the one asked. Working code is not
correct code.

---

## Repo layout

```
bis/mc_engine.py    models, estimators, event measurement
bis/run_sims.py     the suite; writes reports/sim_results.json
bis/prices_all.csv  sym,date,o,h,l,c,volume,interpolated
reports/            simulation_results.md, sim_full_output.txt, sim_results.json
```

Reproduce: `python3 bis/run_sims.py` (deterministic, seed 20261105).

**Nothing in this repo is investment advice, and no output of it should be presented as
a forecast.** The simulations restate their assumptions; they contain no view on AI
capex, commodity prices or regulation, which is what will actually determine outcomes.
