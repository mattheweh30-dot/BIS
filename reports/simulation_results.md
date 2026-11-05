# Monte Carlo simulation study — 9 names

**As of close 2026-11-05.** Data: Robinhood authenticated feed, 1,006 daily split-adjusted
bars per name (2022-11-01 → 2026-11-04) plus the 2026-11-05 close appended.
Code: `bis/mc_engine.py`, `bis/run_sims.py`. Raw output: `reports/sim_full_output.txt`,
`reports/sim_results.json`.

**This is a risk-distribution study, not a forecast.** No price targets, no ratings.
A Monte Carlo cannot tell you where a stock is going; it can only tell you the shape
of the distribution implied by the assumptions you feed it. The assumptions are stated
and their influence is measured in Part 5.

---

## 0. Market context — the day this was run

2026-11-05 was a broad risk-off session, not an idiosyncratic one:

| | Close | 1-day |
|---|---|---|
| SPY | 733.25 | **−4.38%** |
| NVDA | 181.59 | **−9.26%** |
| TSSI | 5.93 | **−13.43%** |
| IMXI | 7.28 | **−12.39%** |
| TLRY | 2.82 | −4.73% |
| WTI | 3.115 | −2.96% |
| III | 5.95 | −2.14% |
| GAU | 2.115 | **+1.68%** |

SPY's realized vol going into the day was 12.6% (21-day). A −4.38% session is roughly a
4-sigma move against that. **Any model calibrated to trailing 252-day volatility is
calibrated to a regime that ended today.** This single fact drives most of what follows.

Reported drivers: post-midterm expectations of tighter AI regulation, vendor-financing
concerns, data-center project delays, export-control uncertainty. UAMY, BW, VRRM, TSSI
and IMXI all printed 52-week lows.

---

## 1. Selection

### Large caps (given)
AAPL, GOOG, NVDA.

### Penny stocks — price < $5 (SEC definition), chosen for real revenue and liquidity

| Ticker | Price | Mkt cap | P/E | P/B | Avg vol | Why |
|---|---|---|---|---|---|---|
| WTI | $3.115 | $482M | −9.3 | **−2.6** | 4.9M | Gulf of America E&P. Real production and a dividend; negative book equity is the risk. Commodity-driven. |
| TLRY | $2.82 | $417M | −2.1 | **0.26** | 5.5M | Cannabis/beverage, $3.6B-scale operations, 3,595 staff. Trades at a quarter of book. Serial equity issuer — dilution is the dominant mechanism. |
| GAU | $2.115 | $559M | **7.5** | 1.71 | 2.1M | Asanko gold mine. **Profitable.** Rose +1.68% while SPY fell 4.38% — a genuine diversifier. |

### Micro caps — market cap $50–300M, **each verified against the fundamentals endpoint**

| Ticker | Price | Mkt cap | P/E | P/B | Avg vol | Why |
|---|---|---|---|---|---|---|
| TSSI | $5.93 | **$167M** | 13.5 | 2.39 | 807k | Data-center integration. Profitable. $18.54 → $5.93 (−68%); 52-wk low set today. Pure AI-capex beta. |
| IMXI | $7.28 | **$220M** | 13.4 | 1.48 | 605k | Money remittance, 531 staff. Profitable. $15.95 → $7.28; 52-wk low today. Fallen-angel value. |
| III | $5.95 | **$283M** | 25.4 | 3.07 | 276k | IT sourcing advisory, pays a 2.96% dividend. **52-wk high was two days ago** — the only name here not in a drawdown. |

### Two selection traps worth recording

**Trap 1 — "penny stock" by price catches mega-caps.** A naive `price < $5` screen
returned 326 names, of which **11 had market caps above $5B**: AmBev ($42.8B), Banco
Bradesco ($27.4B), Wipro ($20.2B), Stellantis ($17.6B), Sabesp ($16.2B), Grab ($13.6B).
Low share price and small company size are orthogonal properties. Price-based and
cap-based definitions must both be applied.

**Trap 2 — the screener's market-cap column is unreliable.** It disagreed with the
authoritative fundamentals endpoint on two names that would otherwise have been admitted:

| Ticker | Screener cap | Fundamentals cap | Error |
|---|---|---|---|
| DSP | $278M | **$841M** | 3.0× |
| INR | $235M | **$777M** | 3.3× |

Both would have been wrongly classified as micro caps. Every market cap in this study
was re-verified. The screener also does not exclude closed-end funds, muni-bond funds,
SPACs, BDCs or REITs from `asset_type = STOCK`; PCQ, OIA, DSM, NHS, FTF, MFM, RWAY, SEVN,
NTWO, SVCC and BACC were removed by hand.

---

## 2. Calibration diagnostics

| Sym | Spot | vol 21d | vol 63d | vol 252d | **EWMA** | Excess kurt | \|r\| autocorr | Worst day | σ |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | 344.33 | 25% | 22% | 25% | 27% | 8.4 | 0.23 | −9% | −5.8 |
| GOOG | 281.73 | 50% | 34% | 33% | **50%** | 5.2 | 0.04 | −12% | −6.7 |
| NVDA | 181.59 | 45% | 40% | 38% | **51%** | 5.9 | 0.10 | −17% | −6.1 |
| WTI | 3.12 | 72% | 58% | 82% | 72% | 2.9 | 0.10 | −18% | −5.0 |
| TLRY | 2.82 | 61% | 53% | 78% | 64% | 12.4 | 0.15 | −21% | −4.3 |
| GAU | 2.12 | 77% | 62% | 68% | 71% | 3.2 | 0.05 | −15% | −4.1 |
| TSSI | 5.93 | 86% | 80% | 109% | 92% | 12.5 | 0.02 | −43% | −7.6 |
| IMXI | 7.28 | 85% | 76% | **42%** | **89%** | **76.6** | 0.13 | −20% | −7.6 |
| III | 5.95 | 30% | 28% | 40% | 32% | 4.4 | 0.07 | −9% | −4.1 |

Three things in this table make a Gaussian model untenable:

- **Excess kurtosis is positive everywhere** (normal = 0). IMXI's **76.6** is extreme —
  its return distribution is almost entirely a quiet core plus a few enormous jumps.
- **Worst days are 4–8 sigma.** Under a normal distribution a −7.6σ day has probability
  ~1 in 10¹³. Two names here did it inside four years.
- **|r| autocorrelation is positive** for 9/9 names: volatility clusters. AAPL's 0.23
  means a large move today genuinely predicts a large move tomorrow — an effect GBM
  assumes away entirely.

**Data-quality note:** TSSI had **512 of 1,006 bars flagged `interpolated`** — the feed
fabricated them to fill gaps, and the vendor documents that they "carry no new
information." All of them precede November 2024; TSSI simply did not trade daily before
then. Interpolated bars are flat by construction and suppress measured volatility, so
every return touching one is excluded. TSSI's usable history is ~494 real bars covering
exactly one boom-and-bust of a single theme — a regime-limited sample, not four years of
evidence.

---

## 3. Earnings-day base rates

Reports are after-close ("pm"), so day 0 is the next session. All reaction returns are
realized from actual closes.

| | n | Median | Mean | SD | Range | Up |
|---|---|---|---|---|---|---|
| NVDA | 6 | **−1.3%** | +0.1% | 5.1pp | −5.5% to +8.7% | **2/6** |
| AAPL | 7 | −1.9% | −1.7% | 3.4pp | −7.4% to +3.2% | 2/7 |
| GOOG | 7 | +0.9% | −0.7% | 7.1pp | **−12.3% to +10.0%** | 4/7 |

All three are **thin base rates** (n < 8). Treat them as weak evidence.

**The most useful finding in this study: NVDA beat consensus EPS in all six quarters —
by +28%, +6.1%, +6.6%, +8.0%, +6.3%, +6.2% — and the stock still fell on four of the
six reactions, with a median of −1.3%.** Beating the estimate is not the same as the
stock going up, because the estimate is not what is priced. Anyone reasoning "NVDA
always beats, so it will rise on 17 November" is using a premise that its own history
contradicts.

**Corollary that surprised me: NVDA's earnings day is no longer its scariest day.** The
historical earnings-reaction SD is 5.1pp. At today's EWMA vol of 51%, an ordinary session
has an SD of 3.2pp — so earnings is only ~1.6× a normal day. The largest earnings move in
the sample was +8.7%; NVDA's worst ordinary day was −17%, and it fell 9.26% today on no
company news at all. This is why the scheduled-jump overlay barely moves the distribution
(below): ambient volatility now swamps the event.

### GOOG event study — 2026-10-28 report (measured per stock-event-precedents methodology)

| Measure | Value |
|---|---|
| Reaction session | 2026-10-29 |
| Raw | −12.3% |
| SPY same day | −0.4% |
| **Excess vs SPY** | **−12.0%** |
| Beta (250 sessions pre-event) | 1.36 |
| **Abnormal (beta-adjusted)** | **−11.8%** |

The market was flat, so essentially the entire move was idiosyncratic. Cause: EPS $2.12
vs $3.02 expected, free cash flow **negative $9.07B** against +$2.7B expected, an $8.7B
equity-investment paper loss, and 2026 capex guided to $195–205B rising "significantly"
in 2027. Worst session since the 2004 IPO; October −19%, worst month on record.

**GOOG's P/E of 15.0 is an artifact, not cheapness.** Trailing EPS prints were $5.11 and
$9.11 against ~$2.9 estimates in the prior two quarters — mark-to-market gains on equity
holdings, not operations. Q3 reversed it to $2.12. The denominator of that P/E contains
large non-operating swings in both directions.

---

## 4. Simulation results

Five models, two horizons, N = 100 (as requested) and N = 50,000. Drift assumption
**+4.0% annual for every name**, stated not estimated. All bootstraps are demeaned and
re-drifted to that assumption.

Models: `gbm_hist` (naive, trailing drift + trailing vol — included to demonstrate
failure), `gbm_ewma`, `boot_iid`, `boot_block` (stationary block bootstrap, mean block
10d), `boot_block_voltgt` (block bootstrap variance-targeted to EWMA — **the preferred
model**), plus `boot_block_earnings` for NVDA.

### 1 month (21 trading days), preferred model, N = 50,000

| Sym | p5 | p50 | P(loss) | ES 5% |
|---|---|---|---|---|
| AAPL | −12% | +0% | 48% | −15% |
| GOOG | −21% | −1% | 52% | −26% |
| NVDA | −20% | −1% | 54% | −24% |
| WTI | −27% | −3% | 56% | −33% |
| TLRY | −23% | −3% | 58% | −28% |
| GAU | −27% | −2% | 55% | −32% |
| TSSI | **−40%** | −2% | 53% | **−48%** |
| IMXI | **−39%** | −1% | 53% | **−49%** |
| III | −13% | +0% | 52% | −16% |

### 1 year (252 trading days), block bootstrap, N = 50,000

| Sym | p5 | p25 | p50 | p75 | p95 | P(loss) | Mean max DD |
|---|---|---|---|---|---|---|---|
| AAPL | −33% | −15% | +1% | +19% | +50% | 49% | −25% |
| GOOG | −40% | −19% | −1% | +22% | +62% | 51% | −30% |
| NVDA | −54% | −31% | −8% | +24% | +92% | 57% | −41% |
| WTI | −67% | −43% | −16% | +23% | +119% | 62% | −52% |
| TLRY | −81% | −60% | −32% | +18% | +181% | 68% | −64% |
| GAU | −66% | −42% | −15% | +25% | +125% | 61% | −51% |
| TSSI | −93% | −78% | **−49%** | +20% | **+306%** | 70% | −78% |
| IMXI | −59% | −32% | −6% | +30% | +110% | 55% | −40% |
| III | −46% | −25% | −4% | +23% | +76% | 54% | −34% |

### Volatility drag is the dominant fact for small caps

Every 252-day median above is **negative despite a +4% expected-return assumption.**
This is not a bug. The median of a lognormal grows at `mu − σ²/2`. At TSSI's 109%
volatility, `σ²/2 = 59%` — so even a +4% expected arithmetic return leaves a median
drift of **−55% per year**:

| Sym | σ | σ²/2 drag | Median drift at mu=+4% |
|---|---|---|---|
| AAPL | 25% | 3% | +1% |
| NVDA | 38% | 7% | −3% |
| TLRY | 78% | 30% | −26% |
| TSSI | 109% | **59%** | **−55%** |

**At 109% volatility you need a +59%/yr expected return just for the median outcome to
break even.** This is why high-volatility small caps can have positive expected value
and still lose money most of the time — TSSI's P(loss) is 70% with a *positive* drift
assumption. Volatility is not merely a measure of uncertainty here; it is a direct,
compounding cost.

---

## 5. The naive-drift trap, quantified

`gbm_hist` calibrates drift to trailing realized return — the standard retail approach.
At 252 days (N = 50,000):

| Sym | Trailing 4y CAGR | Naive p50 | Naive P(loss) | Honest p50 | Honest P(loss) |
|---|---|---|---|---|---|
| NVDA | **+96.5%** | **+78%** | **7%** | −8% | 57% |
| GOOG | +33.6% | +25% | 25% | −1% | 51% |
| AAPL | +23.5% | +19% | 24% | +1% | 49% |
| TLRY | negative | **−62%** | **89%** | −32% | 68% |
| TSSI | negative | −61% | 81% | −49% | 70% |

The naive model assigns NVDA a **7% chance of losing money over a year** — on a stock
that fell 9.26% today and 25% from its high. It is not optimistic by nature: it
*extrapolates momentum in whichever direction the window happened to run*, which is why
it is equally wrong on TLRY in the opposite direction. A trailing CAGR is a description
of the past, and placing it in the drift slot converts a risk model into a
momentum-extrapolation machine while preserving the appearance of rigour.

### Drift sensitivity (252d, N = 50,000) — p5 / p50 / p95

| Sym | mu = −10% | mu = 0% | mu = +4% | mu = +10% |
|---|---|---|---|---|
| AAPL | −42/−13/+30 | −36/−3/+43 | −33/+1/+50 | −29/+7/+59 |
| NVDA | −60/−20/+68 | −56/−11/+85 | −54/−8/+92 | −52/−2/+102 |
| TSSI | −94/−56/+250 | −94/−51/+284 | −93/−49/+307 | −93/−46/+337 |

A 20-point swing in the drift assumption moves AAPL's median by 20 points and TSSI's by
only 10 — because at TSSI's volatility, variance drag dwarfs any plausible drift. **At
short horizons and for high-vol names, volatility is nearly everything and drift barely
registers. At long horizons for low-vol names, drift dominates.** Spend calibration
effort accordingly.

---

## 6. Is N = 100 enough? No — measured, not asserted

The entire N = 100 experiment was re-run 2,000 times. The "90% band" is where the
answer from 100 paths actually lands.

| Sym | Horizon | Stat | N=100 mean | SD | 90% band of the N=100 answer | N=50k |
|---|---|---|---|---|---|---|
| AAPL | 21d | p50 | +0.3% | 0.9pp | [−1.1%, +1.9%] | +0.3% |
| AAPL | 21d | p5 | −11.1% | 1.4pp | [−13.6%, −8.8%] | −11.3% |
| NVDA | 252d | p50 | −7.8% | 5.1pp | [−15.8%, +1.0%] | −7.6% |
| NVDA | 252d | p5 | −53.3% | 3.9pp | [−59.8%, −46.8%] | −54.1% |
| TSSI | 252d | p50 | −48.3% | **8.0pp** | **[−60.1%, −34.4%]** | −49.5% |
| TSSI | 21d | p5 | −48.1% | **4.8pp** | [−55.5%, −39.9%] | −49.4% |
| TLRY | 252d | p50 | −31.6% | 6.9pp | [−42.5%, −19.8%] | −32.3% |

**P(loss) has SD ≈ 5.0pp for every name at every horizon.** That is not coincidence: it
is `sqrt(0.25/100)` exactly. So a P(loss) read off 100 paths carries roughly **±10pp at
95% confidence** — enough to turn 45% into 55% and reverse the conclusion.

**Verdict.** N = 100 is unbiased but imprecise. It is adequate for the *median of a
low-volatility name at short horizon* (AAPL 21-day median: ±1pp). It is not adequate for
any tail statistic, any long horizon, or any high-volatility name — TSSI's 1-year median
from 100 paths lands anywhere in a **26-point range**. The cost of 50,000 paths is
milliseconds. There is no reason to accept this error.

---

## 7. Why volatility targeting mattered

`boot_block` resamples the unconditional distribution — it preserves fat tails and
clustering, but reports the *average* volatility of the sample window rather than
today's. Where those differ, the error is large. Correction = scale demeaned returns by
`EWMA / sample vol`, preserving distribution shape while matching scale (21d p5):

| Sym | vol ratio (EWMA / 252d) | Unconditional p5 | Vol-targeted p5 | Shift |
|---|---|---|---|---|
| IMXI | **2.12** | −23% | **−39%** | **−16.7pp** |
| TSSI | 0.85 | −49% | −40% | +9.3pp |
| TLRY | 0.83 | −32% | −23% | +8.0pp |
| GOOG | 1.50 | −14% | −21% | −7.8pp |
| AAPL | 1.10 | −11% | −12% | −0.4pp |

IMXI's tail was understated by 17 points because its trailing-252-day vol (42%) is less
than half its current vol (89%). The correction cuts both ways — TSSI and TLRY look
*less* risky once stale high-vol history is scaled down. Any name whose EWMA/252d ratio
is far from 1.0 should not be simulated from unconditional history.

At one year the divergence is larger still (N = 50,000, p5 / p50 / P(loss)):

| Sym | vol ratio | Unconditional block | **Vol-targeted** |
|---|---|---|---|
| IMXI | **2.12** | −59% / −6% / 55% | **−85% / −29% / 65%** |
| GOOG | 1.50 | −40% / −1% / 51% | **−59% / −8% / 57%** |
| NVDA | 1.32 | −55% / −8% / 58% | −57% / −9% / 58% |
| AAPL | 1.10 | −33% / +1% / 49% | −34% / +0% / 49% |
| GAU | 1.04 | −66% / −16% / 62% | −71% / −20% / 64% |
| WTI | 0.88 | −66% / −16% / 62% | −71% / −21% / 64% |
| TSSI | 0.85 | −94% / −49% / 71% | −86% / −32% / 65% |
| TLRY | 0.83 | −81% / −32% / 68% | −66% / −17% / 63% |
| III | 0.81 | −46% / −4% / 54% | −40% / −1% / 52% |

**IMXI is the cautionary case: P(loss) moves from 55% to 65% and the median from −6% to
−29% purely by calibrating to current rather than average volatility.** Same data, same
drift, same code path — only the variance target changed. Where the two models disagree
this much, the honest report is the range, and the vol-targeted figure is the one to
weight when the regime has visibly shifted, as it did today.

---

## 8. Honest limitations

1. **Drift is assumed, not known.** +4% is a placeholder. Part 5 shows exactly how much
   that choice matters so it can be substituted.
2. **No implied volatility.** Options markets price forward vol directly and would beat
   EWMA. Not pulled here.
3. **Dilution is unmodelled, and it is the main penny-stock mechanism.** TLRY trades at
   0.26× book and issues equity routinely; WTI has negative book equity. A per-share
   price model cannot represent share-count growth. **For TLRY and WTI specifically,
   this is a bigger omission than anything in the volatility modelling.**
4. **Bankruptcy/delisting is unmodelled.** Diffusion approaches zero but never defaults.
   For sub-$5 names with negative equity the true left tail includes a point mass at
   −100% that no model here produces.
5. **Thin earnings samples** (n = 6–7).
6. **TSSI's history is one regime**, ~494 real bars of a single theme's rise and fall.
7. **Correlation is ignored.** Each name is simulated independently. Today's session —
   SPY −4.38% with 8 of 9 names down together — shows that is false. A portfolio built
   from these marginals would understate joint drawdown badly. Only GAU diversified.
8. **III's liquidity is thin.** Its after-hours bid/ask was 4.81/7.05, a ~38% spread.
   Execution cost could exceed a month of modelled median return.
9. **Simulation is not prediction.** These distributions restate assumptions. They
   contain no view on AI capex, antimony prices, cannabis regulation or remittance
   volumes — the things that will actually determine outcomes.

---

*Historical and statistical analysis. Not investment advice. No ratings or price targets
are given or implied.*

Sources for event context:
[CNBC on Alphabet's worst day since IPO](https://www.cnbc.com/2026/10/29/alphabet-google-microsoft-msft-shares-today-earnings.html) ·
[Fortune on Alphabet cloud revenue and negative FCF](https://fortune.com/2026/10/28/alphabet-google-stock-drops-cloud-revenue-doubles-free-cash-flow-negative/) ·
[Yahoo Finance on Alphabet's October decline](https://finance.yahoo.com/markets/article/alphabets-october-wipeout-hits-758-billion-its-worst-month-ever-211521791.html) ·
[Motley Fool, 5 Nov AI chip selloff](https://www.fool.com/coverage/stock-market-today/2026/11/05/stock-market-today-nov-5-nvidia-slides-on-ai-chip-selloff-as-election-uncertainty-weighs/) ·
[Invezz on Nvidia AI spending and financing fears](https://invezz.com/sg/news/2026/11/05/nvidia-stock-plunges-8percent-as-ai-spending-fears-and-financing-risks-mount/) ·
[24/7 Wall St. on chip-sector regulation fears](https://247wallst.com/investing/2026/11/05/amd-tumbles-13-nvidia-slides-7-as-ai-regulation-fears-hit-chip-stocks-intel-sinks-8/)
