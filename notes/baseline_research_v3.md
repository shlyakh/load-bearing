# Baseline research for protocol-v3 (stage 1)

Research pass on 2026-11-15 by one agent. Purpose: survey what the field uses as a
baseline for hourly load forecasting a week ahead, before protocol-v3 names its primary
baseline. The decision rule is already fixed by the owner: a shortlist is tuned with an
equal budget on development data, the lowest validation error becomes primary, and the
report also names the most widely used baseline and the practitioner's choice.

How to read this note:

- Everything is in our own words; sources are given as URLs with short paraphrases
  (CLAUDE.md rule 9). LinkedIn was not searched, fetched or cited (rule 10).
- **(fetched)** means the page or PDF was opened today and the statement was read there.
  **(abstract)** means only the abstract or index page was read. **(search summary)**
  means the statement comes from a search-result summary and the page was not opened.
  **(memory)** means it comes from the agent's memory and was not checked today.
- Nothing in the repository was changed except this file. No model was run.
- "SIGN-OFF" marks every item that needs the owner's decision.

One correction to the brief: the brief says the scored period under protocol-v2 starts
2025-09-29. In `protocol.yaml` (which `protocol-v2.yaml` reads its origins from),
2025-09-29 is the first **gate** origin (6 Mondays, 2025-09-29 to 2025-11-03) and the
52 **scored** origins run from 2025-11-10 to 2026-11-02. The draft in section 5 keeps
development origins strictly before 2025-09-29, so it is safe under either reading.

## 1. Summary: three named answers

### 1a. Strongest candidates

**A tuned gradient-boosted model on recency features, and an additive model (GAM) with
smoothed temperatures, each with a correction for the level of load at the cutoff.** A
recency regression (Vanilla plus lagged and averaged temperatures) is the cheapest
credible challenger to both.

Reasoning:

- Tao's Vanilla Benchmark is a bar to clear, not a strong model. In the BigDEAL
  Challenge 2022 qualifying match it ranked 25th to 30th of roughly 40 finishers per
  track, while a LightGBM entry on temperature and calendar features ranked 3rd to 8th
  and the organisers' recency benchmark 13th on the peak track (fetched, arXiv
  2305.05575). In GEFCom2017's qualifying match a quantile regression with almost no
  weather beat Vanilla in about 90% of zone and task cells (fetched, arXiv 1809.03561).
- The recency extension is worth 18 to 21% at the aggregate level and 12 to 15% on
  average at zone level over Vanilla, with actual temperatures, both a year ahead and
  24 hours ahead (fetched, the working-paper version of Wang, Liu and Hong 2016).
- Additive models won or placed in GEFCom2012 and GEFCom2014, are EDF's main
  operational tool, and were the base of the winning entry in the 2021 post-COVID
  day-ahead competition (fetched: arXiv 2009.06527, 2110.00334; abstract: EconPapers
  listing of Gaillard, Goude and Nedellec 2016).
- PJM's own 2024 test found XGBoost "slightly more accurate" and much faster than a
  neural network, an LSTM and a Transformer, and better than PJM's production forecast
  at RTO level (root mean square error 1,523 against 1,909 MW and 1,267 against 1,835
  MW on the two slides shown), **except in Dominion**, where load growth from data
  centres biased it until a second "bias learner" was added (fetched, PJM's FERC
  technical conference deck, 2024-07-09).
- Our own untuned result points the same way: `lightgbm_competition` is at 0.886 of
  Vanilla with trend on AEP and 0.952 on AE (`results/README.md`, protocol-v2 section).
- At a week ahead with forecast weather, the gain from extra temperature detail should
  shrink with lead time, because lagged-temperature terms are only as good as the
  forecast they are built from. No source measured this at exactly our horizon and
  regime (section 6). That is the reason to let validation data decide.

### 1b. Most widely used baseline

**Seasonal naive (same hour one week earlier) is the most widely used baseline in the
recent papers we judge; Tao's Vanilla Benchmark is the most widely used weather-aware
benchmark in the load forecasting field itself.** Both should be reported.

Reasoning:

- In our 25 judged references, another pretrained model is the most common comparator
  (17) and seasonal naive or persistence the most common trained-free baseline (11).
  Vanilla appears in none (section 2).
- Vanilla was the organisers' benchmark in GEFCom2012 (verified earlier,
  `notes/hong2014_gefcom2012.md`), is described as the GEFCom2014 benchmark and was one
  of two benchmarks in GEFCom2017's qualifying match (fetched, arXiv 1809.03561), and
  was the first of two organiser benchmarks in BigDEAL 2022 (fetched, arXiv
  2305.05575). A 2024 mid-term study picks three Vanilla variants as benchmarks
  "because of their prevalence" (fetched, arXiv 2405.17070; our paraphrase).
- The field's own view of seasonal naive: for aggregate load it is too inaccurate to be
  a meaningful benchmark; it is useful for household-level load and for comparing
  univariate models (fetched, Wang, Liu and Hong working paper, section 4.1, and Hong's
  2018 blog post).

### 1c. Practitioner's choice

**An ensemble of several models, mostly neural networks plus regression and a
similar-day lookup, fed by weather forecasts from several vendors or models, with a
human forecaster choosing or adjusting the result.** No operator document found today
describes a single model. The closest reproducible stand-in is a tuned boosted-tree
model with a bias correction, or the average of a boosted model and a regression.

Reasoning (all fetched from operator documents; see section 3f):

- PJM (2018 deck): eight models (four neural-network variants, two similar-day
  methods, two weighted ensembles); the ensembles do best on average; operators use the
  base neural network, the ensembles and the similar-day lookup on ordinary days and
  other variants in extreme weather or on holidays; seven days ahead for 22 zones.
- PJM (2024 deck): tested XGBoost, a neural network, an LSTM and a Transformer against
  production; XGBoost preferred. The deck does not say what is in production now.
- NYISO: a neural network combined with ordinary-least-squares regressions, one model
  set per zone, hourly out to 168 hours, re-estimated yearly.
- ERCOT (2024): neural-network and linear-regression models run on several weather
  forecasts; the published forecast "M" is an average of four internal and two
  energy-management-system forecasts; 168 hours ahead, updated hourly.
- ISO-NE (2024, 2026): load forecast models of 25 neural networks each (one daily
  energy model feeding 24 hourly models), with about 15 weather and 40 calendar
  features and 9 to 10 years of training history in the adapted version.
- EDF: GAMs, one per half-hour, with Kalman adaptation since 2020.

What this means for the benchmark: the practitioner's forecast uses more weather
variables (humidity, wind, cloud), more stations, more history and human judgement than
any row we can build from temperature alone. A row labelled "practitioner-style" would
be an approximation and must say so.

## 2. What our own references compare against

Redone from `scorecards/*/*.json`, field `claims[].baseline`, on 2026-11-15. There are
31 scorecard files for 25 distinct references (six references were judged by both
providers). A reference is counted once per family if any of its claims, in either
provider's file, names a baseline of that family. Classification is by keyword on the
baseline text (for example "naive", "persistence", "same-time average"; "lightgbm";
"regression"; "neso", "entso", "tso", "pse"); the script was run from the session
scratchpad and is not stored in the repository. All paths below are under
`scorecards/`.

| Family | References | Files |
|---|---:|---|
| Another pretrained model, or the same model without covariates | 17 | `youcom/calendar-encoding-covariate-tsfm.json`, `claude/chronos2-covariate-grid-load.json`, `youcom/chronos2-covariates-building-energy.json`, `youcom/foretec-energybench.json`, `claude/` and `youcom/gb-demand-weather-zero-shot-backtest.json`, `youcom/german-stlf-live-challenge.json`, `youcom/item-02.json`, `youcom/peak-aware-stlf-aggregation-levels.json`, `youcom/peft-tsfm-electrical-load.json`, `youcom/pl-forecast-bench.json`, `youcom/t0-forecasting-with-context.json`, `youcom/tabpfn-ts-chronos2-heat-load.json`, `youcom/timesfm-3.json`, `youcom/timesfm3-leakage-aware-evaluation.json`, `youcom/timesfm3-university-building-day-ahead.json`, `claude/` and `youcom/timestral.json`, `youcom/tsfm-load-covariate-uncertainty.json` |
| Seasonal naive, persistence or a same-time average | 11 | `youcom/chronos2-covariates-building-energy.json`, `youcom/foretec-energybench.json`, `youcom/german-stlf-live-challenge.json`, `youcom/load-benchmark-across-grid-levels.json`, `youcom/ltcc-weekly-ahead-load-ensemble.json`, `youcom/peak-aware-stlf-aggregation-levels.json`, `youcom/peft-tsfm-electrical-load.json`, `youcom/t0-forecasting-with-context.json`, `youcom/timesfm3-leakage-aware-evaluation.json`, `youcom/timesfm3-university-building-day-ahead.json`, `claude/timestral.json` |
| Operator or TSO forecast | 6 | `youcom/foretec-energybench.json`, `claude/` and `youcom/gb-demand-weather-zero-shot-backtest.json`, `youcom/gb-demand-zero-shot-backtest.json`, `youcom/german-stlf-live-challenge.json`, `youcom/item-02.json`, `youcom/pl-forecast-bench.json` |
| LightGBM | 5 | `youcom/foretec-energybench.json`, `youcom/german-stlf-live-challenge.json`, `youcom/load-benchmark-across-grid-levels.json`, `youcom/ltcc-weekly-ahead-load-ensemble.json`, `youcom/peak-aware-stlf-aggregation-levels.json` |
| XGBoost | 4 | `youcom/ltcc-weekly-ahead-load-ensemble.json`, `youcom/peak-aware-stlf-aggregation-levels.json`, `youcom/peft-tsfm-electrical-load.json`, `youcom/timesfm3-university-building-day-ahead.json` |
| Gradient boosting, library not named | 1 | `youcom/pl-forecast-bench.json` |
| Linear, ridge or lag regression | 4 | `claude/` and `youcom/gb-demand-weather-zero-shot-backtest.json`, `youcom/gb-demand-zero-shot-backtest.json`, `claude/` and `youcom/item-02.json`, `youcom/pl-forecast-bench.json` |
| LSTM, GRU, TCN or CNN | 3 | `claude/` and `youcom/chronos2-covariate-grid-load.json`, `youcom/load-benchmark-across-grid-levels.json`, `youcom/ltcc-weekly-ahead-load-ensemble.json` |
| Transformer trained on the data | 3 | `claude/` and `youcom/chronos2-covariate-grid-load.json`, `youcom/load-benchmark-across-grid-levels.json`, `youcom/ltcc-weekly-ahead-load-ensemble.json` |
| Other trained deep models (TimesNet; TFT from an AutoGluon suite; N-HITS) | 3 | `claude/` and `youcom/tsfm-load-covariate-uncertainty.json`, `youcom/tabpfn-ts-chronos2-heat-load.json`, `youcom/load-benchmark-across-grid-levels.json` |
| ARIMA family or a classical ensemble (SARIMA; MSTL, ETS, ARIMA, Theta) | 2 | `youcom/ltcc-weekly-ahead-load-ensemble.json`, `youcom/timesfm3-leakage-aware-evaluation.json` |
| GAM | 1 | `youcom/weather-forecast-aggregation-gam-load.json` |
| Tao's Vanilla Benchmark | 0 | none |

Agreement with the earlier tally: every count matches, with two notes. The earlier
"XGBoost 4" matches if the unnamed gradient boosting in `pl-forecast-bench` is left out.
The earlier "Transformer 3" matches the strict reading; TimesNet, TFT and N-HITS are
listed on their own row here.

Other observations from the same files:

- Three references have no baseline of any of these families: their comparators are the
  same model under another condition (`claude/` and
  `youcom/pjm-cold-spell-calibration-benchmark.json`,
  `youcom/covariate-copies-tsfm-temperature.json`,
  `youcom/us-day-ahead-load-forecasts-eia930-audit.json`).
  `youcom/choosing-load-methods-horizon-four-grids.json` records no baseline.
- Horizon: most claims are day-ahead (24 hours, or 96 quarter-hours). Only
  `covariate-copies-tsfm-temperature`, `tabpfn-ts-chronos2-heat-load`,
  `timesfm3-leakage-aware-evaluation` (168 hours) and `ltcc-weekly-ahead-load-ensemble`
  (7 days at daily steps) reach a week. Evidence at exactly our horizon is thin.
- Where a boosted model was tuned (`german-stlf-live-challenge`: LightGBM retuned daily
  with Optuna; `timesfm3-university-building-day-ahead`: XGBoost tuned on 90 validation
  days), the scorecards record it as a strong comparator; where it was fixed
  (`peak-aware-stlf-aggregation-levels`: one fit per season on a 90-day block) a 7-day
  same-time average beat it at some aggregation levels.
- Where an operator forecast exists it is usually the best row (NESO 700 MW against
  1,014 MW for the regression in `gb-demand-weather-zero-shot-backtest`; PSE 414 MW
  against 551 MW for Chronos-2 with weather in `pl-forecast-bench`).

## 3. What competitions, literature and operators use

Column "Weather": **ex-post** = actual temperatures in the forecast period; **ex-ante**
= forecast temperatures or none supplied.

### 3a. Competitions

| Source | Method(s) | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| GEFCom2012, load track (Hong, Pinson, Fan 2014) | Benchmark: Vanilla with trend, 4.5 years, best single station. Leading entries: regression with cleansing and holiday terms, boosting with Gaussian processes, additive models, random forests, neural networks | 8 backcast weeks plus 1 forecast week | ex-post for the backcast weeks; none supplied for the forecast week | Benchmark finished behind every selected entry; most winners used holiday effects and station selection | https://doi.org/10.1016/j.ijforecast.2013.07.001 (read 2026-11-13, `notes/hong2014_gefcom2012.md`; not re-read today) |
| Same competition, as described by Wang, Liu and Hong | Vanilla | same | same | Vanilla ranked in the top 25% of over 100 teams | working paper below (fetched) |
| GEFCom2014, load track | Winners: quantile additive models with temperature scenarios (Gaillard, Goude, Nedellec, 1st); forecast combination with residual simulation (Xie and Hong, top 3); semi-parametric regression with simulated temperatures (Dordonnat et al.); kernel density with quantile regression (Haben and Giasemidis) | about a month ahead, probabilistic (memory for the horizon) | ex-ante | Temperature-based models dominated; one winning team modelled regression residuals with ARIMA | https://econpapers.repec.org/RePEc:eee:intfor:v:32:y:2016:i:3:p:1038-1050 (search summary of abstracts); https://blog.drhongtao.com/2018/12/temperature-based-models-vs-time-series-models.html (fetched) |
| GEFCom2014 follow-up (Ziel and Liu 2016) | Lasso-estimated bivariate load and temperature autoregression | same | ex-ante | Beat two regression-based benchmarks drawn from the top eight entries | https://arxiv.org/abs/1603.01376 (abstract) |
| GEFCom2017 qualifying match (Ziel 2019) | Benchmarks: Vanilla (as in GEFCom2014) and a second "Rain" benchmark. Ziel: quantile regression on calendar structure, temperature used only for the trend | about 1 to 2 months ahead, ISO New England, 10 zones, probabilistic | ex-ante, real time | Ziel's entry (2nd open track, 4th defined-data track) beat Vanilla in about 90% of zone and task cells, by 1.4 to 11.2% on the total | https://ar5iv.labs.arxiv.org/html/1809.03561 (fetched) |
| GEFCom2017 overall (Hong, Xie, Black 2019) | Winners' papers: gradient boosting, quantile forests and neural networks in ensembles (Smyl and Hua); quantile regression with heavy preprocessing (Kanda and Quintana Veguillas, final match); reconciled boosted models (Roach) | as above; final match on 161 delivery points | ex-ante | First edition with real-time ex-ante forecasts and open data | https://blog.drhongtao.com/2019/04/gefcom2017-hierarchical-probabilistic-load-forecasting.html (abstract); methods from search summaries of EconPapers abstracts |
| BigDEAL Challenge 2022, qualifying match | Benchmarks: Vanilla, then the Recency Benchmark. LightGBM entry (Rubattu, Maroni, Corani): temperature lags 1 to 48 h, rolling statistics over 3 h to a month, calendar with holiday distance, log target, linear detrending, Optuna tuning on expanding yearly folds | one year ahead, hourly, a US utility, 2002-2006 to forecast 2007 | ex-post | Vanilla ranked 27th (hourly), 25th (peak size), 30th (peak timing); recency benchmark 13th on peak size; the LightGBM entry 8th, 3rd, 3rd. Their error fell from 4.81 to 3.33 when temperature lags were added and 6.18 to 4.81 from detrending alone. 14 of 78 teams beat the recency benchmark in some track | https://ar5iv.labs.arxiv.org/html/2305.05575 (fetched); https://blog.drhongtao.com/2022/11/bigdeal-challenge-2022-qualifying-match.html (fetched) |
| BigDEAL Challenge 2022, final match | Same benchmarks; winners Amperon (1st on size) and KIT-IAI (1st on timing and shape) | day-ahead daily peak, six rounds | ex-ante (1-day-ahead temperature forecasts) | Overall rank, benchmarks included in the ranking: Vanilla 14th, recency benchmark 10th, the LightGBM entry 6th (13 teams were eligible). Winners' methods not published on the page | https://blog.drhongtao.com/2022/12/bigdeal-challenge-2022-final-leaderboard.html (fetched; leaderboard is an image); ranks from arXiv 2305.05575 (fetched) |
| IEEE DataPort post-COVID day-ahead competition, 2021 (Farrokhabadi et al. 2022) | Winner 1 (de Vilmarest and Goude): autoregressive, linear, GAM and neural-network models adapted by Kalman filters, then aggregated. Winner 2 (Ziel): online combination of time-series models, GAMs and lasso regressions with a holiday adjustment | 16 to 40 hours ahead, hourly, 30 daily rounds | ex-ante (weather forecasts, statistically corrected by the winners) | Offline linear regression and GAM had errors of about 22.8 and 22.7 MW; after Kalman adaptation 11.2 and 12.4 MW; the aggregate 10.9 MW. Adaptation mattered more than the model family | https://ar5iv.labs.arxiv.org/html/2110.00334 (fetched); https://arxiv.org/abs/2107.06268 (abstract); competition paper https://doi.org/10.1109/OAJPE.2022.3161101 (search summary) |
| Anything from 2023 to 2026 | none found | | | One search for BigDEAL 2023 to 2025 returned nothing after 2022. Kaggle's Enefit competition (2024) is known only from an earlier search summary (`notes/model_families.md`) | not verified |

### 3b. Vanilla and its extensions

| Source | Method | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| Wang, Liu and Hong, working paper HSC/15/08 (journal version: Int. J. Forecasting 32(3), 2016) | Vanilla with trend, plus the same cubic temperature terms repeated for `h` lagged hourly temperatures (0 to 72) and `d` daily moving averages (0 to 7): 584 candidate pairs, all enumerated; the pair with the lowest error on one validation year is kept | one year ahead, and 24 hours ahead with a rolling 730-day window | ex-post in both | Training 2 years (2004-2005), validation 2006, test 2007. Chosen for the aggregate series: 2 daily averages and 12 hourly lags (the text later prints "d = 2; h = 4"; the two statements disagree). Test error 4.27% against 5.22% for Vanilla (18% lower); 12% lower on average over zones with a pair chosen per zone; 21% (aggregate) and 15% (zones) at 24 hours ahead. In hindsight the best pair on the test year was different (no daily averages, 16 lags). One pair for all hours did better than a pair per hour. No lagged load in any model | https://ideas.repec.org/p/wuu/wpaper/hsc1508.html (fetched); PDF at https://prac.im.pwr.edu.pl/~hugo/RePEc/wuu/wpaper/HSC_15_08.pdf (fetched and read) |
| Same paper, section 2.2 | Vanilla | | | States that Vanilla is the base model in a commercial product (SAS Energy Forecasting) and that past load is left out because some jurisdictions do not allow it in long-term forecasts | same (fetched) |
| Same paper, section 4.1 | Daily and weekly seasonal naive | 24 hours ahead | n/a | Both far behind all four regression models; the authors call naive models not meaningful for aggregate load | same (fetched) |
| Hong, Wang and White 2015 | Station selection: rank stations by the in-sample fit of Vanilla, average the top `k`, choose `k` on validation data | used with Vanilla | ex-post | Dropping a fixed number of stations improves accuracy; the four GEFCom2012 load winners used some form of it | https://econpapers.repec.org/RePEc:eee:intfor:v:31:y:2015:i:2:p:286-295 (search summary of the abstract and of later papers) |
| Holiday treatment | No source read today gives Hong's rule. Zimmermann and Ziel treat fixed-date and weekday holidays as separate smooth effects and add vacation periods; Ziel's post-COVID entry credits a holiday adjustment for part of its win | | | Our own result: holiday-by-hour terms changed Vanilla by under 3.5% (`protocol-v2.yaml`, `results/README.md`). The common practice of coding a holiday as a weekend day is (memory) | arXiv 2405.17070 (fetched); arXiv 2107.06268 (abstract) |
| Training length | Vanilla: 4.5 years in GEFCom2012; 2 years in the recency paper and in Ziel and Liu; 4 years in Zimmermann and Ziel; 5 years in a SAS holiday paper; PJM's 2024 test used 7 years; ISO-NE 9 to 10 years | | | No source read today tests training length for Vanilla directly. It is a tuning parameter in section 4 | recency paper, arXiv 2405.17070, PJM and ISO-NE decks (fetched); SAS paper (search summary) |

### 3c. Additive models (GAM)

| Source | Method | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| Obst, de Vilmarest and Goude 2020 (EDF) | One GAM per half-hour (48 models). Terms: day type by clock-change indicator; yesterday's load with a coefficient per day type; last week's load; smooth of time; smooth of time of year; smooth interaction of time and temperature; smooths of exponentially smoothed temperature (factors 0.95 and 0.99); smooth of smoothed daily minimum and maximum; ARIMA on the residuals | day-ahead (inferred from the lags) | ex-post (observed temperatures, chosen for reproducibility) | Trained 2012 to Aug 2019. Error before lockdown 1.39% for the GAM and 1.26% with Kalman adaptation; in the first lockdown month 4.83% and 2.73%. The paper calls the GAM EDF's main operational tool | https://ar5iv.labs.arxiv.org/html/2009.06527 (fetched) |
| de Vilmarest and Goude 2021 | GAM with day type, smoothed temperature, cyclic time of year, splines on day and week load lags, linear trend; beside linear, autoregressive and neural models | 16 to 40 hours | ex-ante | see 3a | https://ar5iv.labs.arxiv.org/html/2110.00334 (fetched) |
| Zimmermann and Ziel 2024 (rev. 2025) | Two-stage P-spline GAM: smoothed temperatures, level and seasonal "states" from an exponential-smoothing model carried forward, separate holiday smooths, autoregressive post-processing of residuals. Benchmarks: weekly and annual seasonal random walks, STL, three Vanilla variants (no temperature, temperature, recency), an autoregressive weekly-difference model, a feed-forward network | 1 to 52 weeks ahead, averaged over the whole horizon; 24 European countries; 4 years of training, rolled daily | ex-ante of a special kind: future temperature is itself forecast from seasonality, not from a weather model | Summed error over countries: GAM 16.8, network 17.6, annual random walk 20.5, STL 22.7, autoregressive model 30.1, Vanilla with recency 37.9, Vanilla 38.5, weekly random walk 40.7 (GW). The authors note the same weakness of Vanilla in GEFCom2014 and 2017. Fit takes seconds. **Not our setting**: a year-long horizon with a linear trend extrapolated and no weather forecast | https://arxiv.org/abs/2405.17070 (abstract page and PDF, fetched and read) |
| Pierrot and Goude 2011; Goude, Nedellec and Kong 2014; Wood, Goude and Shaw 2015 | EDF's original GAM; one model applied to 2,260 substations; fitting methods for very large data with autocorrelated residuals | short and middle term | not read | Term lists not read today: the open copy redirected and the others are index pages | https://researchportal.bath.ac.uk/en/publications/short-term-electricity-load-forecasting-with-generalized-additive/ and https://ideas.repec.org/a/bla/jorssc/v64y2015i1p139-155.html (search summaries only) |
| Our reference `weather-forecast-aggregation-gam-load` | GAM with Kalman adaptation ("Viking") on several weather providers | 24 hours | ex-ante | The only one of our 25 references built on a GAM | `scorecards/youcom/weather-forecast-aggregation-gam-load.json` |

Typical term structure across these sources: a day-type factor (often by hour), a smooth
of current temperature, one or two smooths of exponentially smoothed temperature, a
cyclic smooth of time of year, a trend or slowly varying level, load lags of a day and a
week where the horizon allows, and an autoregressive model on the residuals. A model
per hour (or half-hour) is the EDF convention.

### 3d. Classical time-series methods with several seasonal cycles

| Source | Method | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| Hong's 2018 post on temperature-based against time-series models | Exponential smoothing and ARIMA against regression with temperature | several | both | Ex-post point forecasting favours temperature models; ex-ante probabilistic competitions (2014, 2017) were also dominated by them; for ex-ante point forecasting the post finds no solid evidence either way. Taylor's 2012 result (smoothing better up to about five hours, the weather-based method beyond) is cited with the warning that the weather-based comparator was poorly described | https://blog.drhongtao.com/2018/12/temperature-based-models-vs-time-series-models.html (fetched) |
| Taylor 2010 | Double- and triple-seasonal Holt-Winters, double-seasonal ARMA, a univariate neural network | up to a day ahead, half-hourly, British and French data | none | Triple-seasonal versions beat double-seasonal ones; combining two helps | https://ora.ox.ac.uk/objects/uuid:ee05c2f4-99d5-4b23-945a-9527f5defafa (abstract) |
| Bandara, Hyndman and Bergmeir 2021 | MSTL decomposition | n/a | none | Competitive decompositions at lower cost than alternatives; tested on simulated and perturbed series, not as a load forecaster | https://arxiv.org/abs/2107.13462 (abstract) |
| Nixtla tutorial on PJM hourly load | MSTL (cycles 24 and 168, AutoARIMA trend) against seasonal naive, Prophet, NeuralProphet | 24 hours, one test day | none | MSTL about a third below seasonal naive; Prophet and NeuralProphet above it. One day, a vendor tutorial: weak evidence | https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/electricityloadforecasting.html (fetched) |
| Zimmermann and Ziel 2024 | STL, autoregressive weekly-difference model | 1 to 52 weeks | n/a | Both behind the GAM and the network, ahead of Vanilla, in that special setting (3c) | arXiv 2405.17070 (fetched) |
| Our reference `timesfm3-leakage-aware-evaluation` | Average of three MSTL variants | 24 and 168 hours | none | The only one of our references with a multi-seasonal classical comparator at 168 hours | `scorecards/youcom/timesfm3-leakage-aware-evaluation.json` |
| TBATS; (S)ARIMAX | not searched beyond the above | | | TBATS takes no regressors and is slow on long hourly series; regression with ARIMA errors is the standard way to add weather to ARIMA (both memory; the first is also in `notes/model_families.md`) | not verified today |

No source found today compares double- or triple-seasonal smoothing, TBATS or MSTL with
a regression, GAM or boosted model at a week ahead with forecast weather.

### 3e. Gradient boosting

| Source | Method | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| Rubattu, Maroni and Corani 2023 (BigDEAL 2022) | LightGBM; features in 3a; selection by permutation importance on correlated feature clusters; Optuna; DART booster with 30,000 iterations for the final gain (3.24 to 2.83) | a year ahead (qualifying), day-ahead (final) | ex-post, then ex-ante | Far ahead of Vanilla, close to or ahead of the recency benchmark. Search space not reported. Most useful lags in the final: 1 to 5 and 10 to 12 hours; windows of 3 hours and a day | https://ar5iv.labs.arxiv.org/html/2305.05575 (fetched) |
| PJM, FERC technical conference, 2024-07-09 | XGBoost with year, month, weekday, hour, holiday; temperature, dew point, wind, cloud; temperature differences over three hours either side; load and temperature at the current hour, the same hour yesterday and the same hour on the last same weekday. Second XGBoost learner for bias (error on forecast and hour) | intraday and day-ahead (the 10:00 and 18:00 forecasts for day 0 and day 1) | ex-ante presumably (not stated) | Trained on 7 years, tested monthly from April 2023 to May 2024. Better than production for the RTO and all large zones except Dominion; the bias learner fixed Dominion and left other zones unchanged | https://www.pjm.com/-/media/DotCom/library/reports-notices/testimony/2024/20240709-presentation-ferc-technical-conference-hourly-load-forecasting-machine-learning-algorithms.pdf (fetched and read) |
| Smyl and Hua 2019 (GEFCom2017) | Boosting, quantile forests, neural networks, ensembles | about a month | ex-ante | A winning qualifying entry | EconPapers listing (search summary) |
| Our references | LightGBM or XGBoost as comparator in 9 of 25 | mostly day-ahead | mixed | Tuned versions are strong comparators (section 2) | `scorecards/` |
| Direct comparison of LightGBM with Vanilla | one targeted search | | | No paper found that tests a tuned boosted model against Vanilla as its headline; the BigDEAL leaderboard is the best evidence | search only |

### 3f. Operators

| Operator | Models | Horizon | Inputs | Notes | URL and status |
|---|---|---|---|---|---|
| PJM, 2018-03-09 | Eight: neural network; "Index" network on a temperature-humidity index or wind chill; "Weather Optimized" and "Backfill" variants for sudden weather change; two similar-day methods; two weighted ensembles | seven days including today, 22 zones plus aggregates; posted twice an hour; dispatchers concentrate on intraday and day-ahead | season, weekday, hour, holidays; temperature, cloud, wind, humidity from three weather vendors; historical load and similar days | Ensembles best on average; similar-day lookup on holidays; operators may adjust at any time | https://pjm.com/-/media/committees-groups/task-forces/sodrstf/20180309/20180309-item-04-load-forecasting.ashx (fetched and read) |
| PJM, 2024-07-09 | XGBoost, neural network, LSTM, Transformer under test against production | seven days hourly (short-term); six hours at five minutes (very short-term) | see 3e | Production model in 2024 to 2026 is not described; PJM's fact sheet could not be fetched | URL in 3e (fetched) |
| NYISO (FERC Order 890-A posting, undated) | Neural network combined with ordinary-least-squares regressions, per zone, summed to the state | current day plus six days, up to 168 hours | dry bulb, wind, cloud, dew point, wet bulb from one vendor; station weights in the Day-Ahead Scheduling Manual | Re-estimated before June each year; no economic inputs | https://www.nyiso.com/documents/20142/1395789/FERC890aDALFDesc.pdf/a87e4c73-2d59-0d83-d3c0-b31e6c3f7e00 (fetched and read) |
| ERCOT, board education deck, 2024-06 | Internally developed neural-network and linear-regression models, specified by season; two models inside the energy management system; a vendor forecast being added. Forecasts E, E1, E2, E3 are the same model on different weather forecasts; "M" averages the four internal and two system forecasts | 168 hours, updated hourly, by weather zone | temperature, wind, cloud, solar irradiance; 49 stations; weekday and holidays; four global weather models and three vendor forecasts | | https://www.ercot.com/files/docs/2024/06/11/7%20Board%20Education%20%E2%80%93%20Load%20Forecasting.pdf (fetched and read) |
| ISO-NE, 2024-10-29 and 2026-03 | Each load forecast model is 25 neural networks: a daily energy model feeding 24 hourly models; three such models in the 2026 prototype. The version adapted for long-term work has about 15 weather features, 40 calendar features and 9 to 10 years of history | intraday, day-ahead and out to 7 days (21 days mentioned) | dry bulb, dew point, wet bulb, wind, cloud; 23 stations; several vendors | The 2026 deck says the load models were not the object of that exercise and could be improved | https://iea-wind.org/wp-content/uploads/2025/01/6_IEA_Rutgers_Task51_29Oct2024_vrojo.pdf and https://www.esig.energy/attachment/serve/pfx_prototype_isone_march2026 (both fetched and read) |
| NESO (GB), Energy Forecasting Strategy, 2026-03 | Legacy systems being replaced by a cloud "Platform for Energy Forecasting"; machine-learning methods named for wind and solar; demand model type not stated | day-ahead national demand is the regulated metric; products out to 52 weeks | moving from fixed weather locations to gridded and ensemble weather | No model family for demand could be confirmed | https://www.neso.energy/document/373066/download (fetched and read) |
| EDF (France) | GAMs with Kalman adaptation | day-ahead | see 3c | The GAM is the main tool, by the authors' own statement | arXiv 2009.06527 (fetched) |
| Itron (vendor), 2018-12-05 | Names like-day, multivariate regression and neural networks as the industry's standard techniques | short-term | | Product page only | https://de.itron.com/w/a-practitioners-guide-to-short-term-load-forecast-modeling (fetched) |
| CAISO, MISO | not found | | | Two searches returned no operator document on model families. A 2026 conference paper on MISO combining several vendors' forecasts is a search summary only | not verified |

PJM archive of week-ahead forecasts: already known to be unavailable (brief); nothing
found today changes that.

### 3g. Baselines in recent evaluations of pretrained models

| Source | Baselines used | Horizon | Weather | Finding | URL and status |
|---|---|---|---|---|---|
| Our 25 references | section 2 | mostly day-ahead | mixed | No Vanilla, one GAM, few tuned regressions | `scorecards/` |
| Bouainouche et al., NeurIPS 2025 workshop, "Linear regression as a litmus test" | argues seasonal naive and DLinear set too low a bar | general benchmarks | none | A carefully tuned linear regression beat many deep models and Chronos Base; calls for stronger baselines | https://neurips.cc/virtual/2025/loc/san-diego/130437 (abstract) |
| Meyer et al., arXiv 2410.09487 | Transformers trained from scratch; a seasonal average | household load, short term | none | Pretrained models comparable to trained Transformers | search summary |
| Simeone, arXiv 2602.10848 | Prophet, SARIMA, seasonal naive | ERCOT hourly | none | Calibration comparison | search summary |
| arXiv 2602.05390 | an LSTM | electricity demand with exogenous data | yes | The simple trained baseline often beat the pretrained models in a stable climate | search summary |
| arXiv 2602.21415 | LSTM beside Mamba and Transformer models; no regression, boosting or operator forecast | 24 to 168 hours, six US grids | yes | Rankings reverse when weather is added | https://arxiv.org/abs/2602.21415 (abstract) |
| Cloud-workload study arXiv 2502.12944; TempusBench arXiv 2604.11529 | seasonal naive, online linear model | general | none | Simple baselines matched or beat zero-shot models on some data | search summaries |

Criticism that baselines are weak exists for general benchmarks (the litmus-test paper).
No paper was found that makes this criticism specifically about electricity load, and
none that compares a pretrained model with Vanilla, a recency regression or a GAM on
load with weather, apart from our reference `weather-forecast-aggregation-gam-load`
(which does not include a pretrained model). This repeats the finding in
`notes/classical_baselines.md` with a logged search behind it.

## 4. Proposed shortlist for tuning

Six contenders. Common rules for all: fitted only on data before the cutoff; horizon
temperature from the active regime; one configuration shared by both development zones
(SIGN-OFF, see 5); refit at every origin. Installed and checked today in `core/.venv`
(rule 7): statsmodels 0.15.0 with `GLMGam`, `BSplines`, `CyclicCubicSplines`, `MSTL`
and `ExponentialSmoothing` importable; lightgbm 4.7.0; scikit-learn 1.9.1 with
`SplineTransformer`. Not installed: pygam, statsforecast, optuna, xgboost.

### C1. Vanilla with trend, tuned (the incumbent)

- **Definition:** `vanilla_benchmark_trend` as in `harness/baselines.py`.
- **Tune:** training window {365, 730, 1095, 1461, 1826 days, all since 2019}; trend
  {linear over the window, none}; observation weights {equal, exponential with half-life
  180 or 365 days}; target {MW, log}; holiday terms {none, holiday by hour as in
  `vanilla_benchmark_trend_holiday`, holiday coded as Sunday}; temperature polynomial
  degree {2, 3}. 432 combinations; draw 50.
- **Effort:** 2 hours (parameterise existing code).
- **Why included:** organisers' benchmark in GEFCom2012, 2014, 2017 and BigDEAL 2022;
  the current primary baseline. Tuning it answers the owner's first suspicion directly.
- **Note:** "holiday as Sunday" is from memory, not a source read today. SIGN-OFF to
  include it.

### C2. Recency regression (Vanilla plus lagged and averaged temperatures)

- **Definition:** C1 plus the cubic temperature block (main effect, by month, by hour)
  repeated for `h` lagged hourly temperatures and `d` daily moving averages, as in the
  working paper's equation 4. No lagged load.
- **Tune:** `d` in 0..7; `h` in {0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 36, 48, 72}; training
  window {730, 1095, 1461 days}; trend and holiday choices as C1. The source enumerated
  all 584 pairs on one validation year; our budget samples 50.
- **Effort:** half a day. Largest design is roughly 80 temperature series by 111
  columns on up to 35,000 rows; ordinary least squares in seconds (estimate, not
  timed). Collinearity may need a pseudo-inverse or a small ridge term; say which.
- **Why included:** Wang, Liu and Hong (12 to 21% over Vanilla, ex-post); the
  organisers' second benchmark in BigDEAL 2022.
- **Caveat:** in the forecast regime every lag inside the horizon is a forecast value;
  the gain measured ex-post may not carry over.

### C3. Additive model (GAM)

- **Definition:** per hour of day (24 fits) or pooled with hour interactions: day-type
  factor; smooth of temperature; smooths of exponentially smoothed temperature; cyclic
  smooth of day of year; linear trend; holiday factor; optionally a smooth of the load
  168 hours earlier.
- **Tune:** per-hour or pooled; smoothing factors for temperature from {0.90, 0.95,
  0.98, 0.99} (one or two series); basis size {6, 10, 15}; penalty weight log-uniform
  1e-2 to 1e3; training window {730, 1095, 1461, 1826 days}; lag-168 term on or off;
  trend on or off.
- **Effort:** 1 to 1.5 days. Three routes, to be chosen after a small test (SIGN-OFF if
  a dependency is added): (a) statsmodels `GLMGam`, installed, but whether it handles
  factor-by-smooth terms at this size is unverified; (b) explicit spline bases with
  scikit-learn's `SplineTransformer` and a ridge penalty, fully under our control;
  (c) `pygam` via `uv add`, maintenance status unverified.
- **Why included:** EDF's operational model; winners of GEFCom2014 load and of the
  post-COVID competition; best model in Zimmermann and Ziel.

### C4. LightGBM on recency features, tuned

- **Definition:** `lightgbm_competition` (temperature lags, rolling statistics, 13
  calendar features, log target with linear detrending), exogenous inputs only.
- **Tune:** `num_leaves` 7 to 127 (log); `learning_rate` 0.01 to 0.1 (log); trees 300
  to 3,000 or early stopping on the last 8 weeks of the training window;
  `min_child_samples` 10 to 200; `feature_fraction` 0.3 to 1.0; `bagging_fraction` 0.5
  to 1.0; `lambda_l2` 0 to 10; objective {L2, L1}; training window {730, 1095, 1826
  days}; detrending {linear, none}; temperature lag set {1 to 6, 1 to 24, 1 to 48}.
  Random search with the protocol seed; no Optuna needed.
- **Effort:** half a day; about 3.6 s per window today, so 50 configurations on 26
  origins and 2 zones is roughly 2.6 hours (estimate from the v2 gate timing).
- **Why included:** BigDEAL 2022 entry; PJM's 2024 test; our untuned row already beats
  Vanilla with trend on AEP.
- **Caveat:** PJM found boosting biased on Dominion (our DOM) because of load growth.
  The detrending switch is the relevant parameter.

### C5. Regression with a correction from the load at the cutoff

- **Definition:** the selected C2 (or C1) regression plus a forecast of its own recent
  residuals: fit an autoregression to the residuals of the last `w` weeks and add its
  168-hour forecast, which decays towards zero. This is the only contender besides C3's
  optional lag term that uses load up to the cutoff, the information the pretrained
  models see.
- **Tune:** maximum order {24, 48, 168, 336}, chosen by AIC below it; residual window
  {4, 8, 13, 26 weeks}; a simpler variant (mean residual of the last 24 or 168 hours
  with geometric decay {0.98, 0.99, 0.995} per hour); base regression's `d`, `h` from a
  short list.
- **Effort:** half a day on top of C2 (statsmodels `AutoReg`).
- **Why included:** ARIMA on GAM residuals at EDF; autoregressive post-processing in
  Zimmermann and Ziel; intraday residual correction in the post-COVID winner; a
  GEFCom2014 winner modelled regression residuals with ARIMA (Hong's 2018 post). Our
  own results show most of Chronos-2's lead over a regression is on day 1
  (`results/README.md`).
- **SIGN-OFF:** whether a contender may build on another contender's tuned
  configuration, or must spend its own 50 draws on the joint space.

### C6. Univariate multi-seasonal model (MSTL or double-seasonal Holt-Winters)

- **Definition:** MSTL decomposition with cycles of 24 and 168 hours, trend forecast by
  ETS or ARIMA, seasonal components repeated; no weather.
- **Tune:** history length {4, 8, 13, 26, 52, 104 weeks}; trend forecaster {ETS damped,
  ARIMA, last value}; seasonal windows; robust on or off; log on or off.
- **Effort:** 2 to 4 hours with statsmodels `MSTL` (installed); statsforecast would be
  faster but is a new dependency.
- **Why included:** the classical time-series family (Taylor; Nixtla tutorial; the
  comparator in `timesfm3-leakage-aware-evaluation`). Expected to lose to every
  temperature model at a week ahead; if it does, that is the documented reason for
  excluding the family, and it remains the right bar for univariate pretrained rows.

Considered and left out of the contenders (SIGN-OFF if any should be added):

- An average of the tuned contenders. Operators and competition winners combine models,
  and it would probably win. It is left out because it is not a single "baseline"; it
  could be reported as a secondary "practitioner-style" row.
- Neural networks trained on the data (operators' main family): outside "traditional
  method", slow on CPU, many more tuning choices.
- Station selection (Hong, Wang, White): changes the weather input for every model, so
  it belongs to the weather definition (hard rule 3), not to one contender.
- Kalman-adapted GAM: strongest in the 2021 competition, but a larger build; C5 covers
  the same idea in a simple form.
- Humidity, wind and cloud inputs: used by every operator; deferred by decision 34.

## 5. Tuning protocol draft

Every numbered item needs the owner's sign-off unless marked "fixed by the brief".

1. **Budget (fixed by the brief):** at most 50 configurations per contender, drawn by
   random search from the spaces in section 4 with seed 20261112 (the protocol's
   bootstrap seed). Configuration 0 of each contender is its published or current
   default, so the default is always among the candidates. SIGN-OFF: seed and the
   "default is configuration 0" rule.
2. **Zones (fixed by the brief):** DOM and JC only. AEP and AE are not touched.
3. **One configuration for both zones.** The winner must be applied unchanged to AEP
   and AE, where no tuning is allowed, so a configuration tuned per zone could not be
   transferred. SIGN-OFF. (The recency paper tunes per zone; this is a deliberate
   departure.)
4. **Development origins:** the 52 Mondays of `protocol.yaml` `origins.ordering_gate`,
   2024-09-30 to 2025-09-22, all strictly before the first gate origin (2025-09-29) and
   before every scored origin. Written out in protocol-v3, never inferred from data
   (hard rule 1). SIGN-OFF, with two disclosures: these origins were used once under
   protocol-v1 for an ordering check of the lag regression (`results/ordering_gate/`),
   not for any contender here; and hard rule 12 says that before a tag, code runs only
   on the gate origins listed in the protocol, so protocol-v3's draft must list these
   development origins explicitly as allowed before the tag.
5. **Alternate origins (fixed by the brief):** in date order, odd-numbered origins
   (26, starting 2024-09-30) are the tuning set; even-numbered origins (26, starting
   2024-10-07) are the selection set. Within each contender the configuration with the
   lowest tuning-set score is frozen; contenders are then compared once on the
   selection set. SIGN-OFF on which parity is which. Caveat: adjacent weeks share
   weather regimes and almost all training data, so the two sets are not independent;
   alternation controls for season, not for dependence.
6. **Gate origins** (2025-09-29 to 2025-11-03) keep their role: code checks only, no
   tuning and no selection.
7. **Metric:** mean over windows of the window MAE in MW (the protocol's
   `window_error`), per zone; each zone's value divided by `vanilla_benchmark_trend`'s
   mean window MAE on the same windows; the score is the geometric mean of the two
   zone ratios. This keeps DOM (large) from deciding alone. SIGN-OFF. Alternatives: sum
   of MW errors (DOM dominates) or MASE.
8. **Dropped windows:** the protocol-v2 drop rule, applied identically to every
   contender; a window missing for one contender is dropped for all. SIGN-OFF.
9. **Tie rule:** if the best contender's selection-set score is not separated from the
   next one (the 90% whole-week paired bootstrap interval of their ratio, 2,000 draws,
   includes 1), take the earlier of the two in this order: C1, C2, C3, C4, C5, C6, that
   is, the simpler and more widely used model. SIGN-OFF on the order and on using the
   interval rather than a fixed margin such as 2%.
10. **Weather regime for tuning. This is the main caveat.** The primary regime of
    protocol-v2 is `forecast_aifs`, and `protocol-v1.2.yaml` records no AIFS archive
    before 2025-02-17. So AIFS covers only the 32 development origins from 2025-02-17
    to 2025-09-22: no autumn and almost no winter. Options:
    - (a) tune and select on `forecast_ifs` (Previous Runs archive from 2024-02-01),
      all 52 origins, and report the AIFS subset as a check. Recommended: a forecast
      regime penalises models that lean on precise temperature detail, as the scored
      comparison will, and all seasons are covered.
    - (b) tune and select on `oracle_era5`. Simplest, but it rewards exactly the
      recency terms whose value under forecast weather is in doubt.
    - (c) tune on AIFS for the 32 available origins only. Matches the primary regime
      but leaves winter untested.
    SIGN-OFF. Whichever is chosen, results for the other regimes are reported
    separately and labelled secondary (hard rule 4). To verify before use: that the IFS
    and GFS processed files for DOM and JC are complete for all 52 development origins
    (the coverage statement in `protocol-v1.2.yaml` names gate and scored origins
    only).
11. **History available:** load and ERA5 start 2019-01-01, so the earliest development
    origin has about 5.7 years behind it; the longest window in the search spaces fits.
12. **Pretrained models are not tuned.** They keep their protocol-v2 settings. The
    asymmetry (50 configurations for a baseline, none for Chronos-2) is intended, since
    the question is whether the model beats a baseline a practitioner would tune, but
    it should be stated in protocol-v3. SIGN-OFF.
13. **What gets recorded:** every configuration drawn, its tuning-set score per zone,
    the frozen configuration per contender, the selection-set table with intervals,
    runtime, git commit, and the seed. Nothing from the scored origins is computed
    until protocol-v3 is tagged.
14. **After selection:** the winner and its frozen configuration are written into
    protocol-v3 as the primary baseline; the report names, beside it, seasonal naive
    and Vanilla with trend (most widely used) and the practitioner-style row if one is
    built. Gate, tag, then score once (hard rule 12).
15. **Which weeks protocol-v3 scores.** The 52 scored origins have already been scored
    for Chronos-2 and several baselines on AEP and AE. A new baseline chosen on
    development data and scored on those weeks is blind for the baseline, but the
    pretrained model's numbers on them are already known. SIGN-OFF: reuse the 52
    origins, or tie protocol-v3's primary to the prospective panel.

## 6. Open questions and what could not be verified

Not verified today (each is marked where it is used above):

- The journal version of Wang, Liu and Hong (2016) was not read; the working paper was.
  The working paper states the chosen pair once as 2 daily averages and 12 lags and
  once as "d = 2; h = 4".
- Hong, Wang and White (2015), Hong and Fan (2016), Pierrot and Goude (2011), Goude,
  Nedellec and Kong (2014), Wood, Goude and Shaw (2015), Taylor (2012), the GEFCom2014
  and GEFCom2017 overview papers and Hong's 2010 dissertation: abstracts or search
  summaries only. The definition of the GEFCom2014 and 2017 Vanilla benchmark (which
  temperature scenarios it was fed) was not read.
- Hong's holiday treatment for Vanilla; any rule for the number of training years.
- BigDEAL 2022 final leaderboard is an image; ranks were taken from the participant
  paper (arXiv 2305.05575). The winners' methods (Amperon, KIT-IAI) are unpublished on
  the pages read.
- No load forecasting competition after 2022 was found; the search was a single query.
- PJM: what is in production in 2026; the fact sheet URL returned no PDF. In the 2024
  deck the two RTO slides ("economic benefit", "reliability benefit") are assumed to be
  the 10:00 and 18:00 forecasts; the deck does not label them so. Whether its test used
  archived weather forecasts is not stated.
- NYISO's posting is undated. NESO's demand model family is not stated in its
  strategy. ERCOT: how "M" relates to the forecast operators finally use. CAISO and
  MISO: nothing found.
- The Zimmermann and Ziel table was read from a text extraction of the PDF; column
  alignment was checked on the "Sum" row only.
- Items marked (memory) in section 3: GEFCom2014's horizon; holiday coded as a weekend
  day; TBATS and ARIMA-with-regressors remarks.
- Entries marked (search summary) in 3g were not opened.

Open questions for the owner:

1. No source compares these families at 168 hours with forecast weather. The sources
   are day-ahead or month-to-year ahead, and most are ex-post. The tuning run will be
   the first evidence at our setting; is the regime choice in 5.10 acceptable?
2. Shared or per-zone configurations (5.3)?
3. May a contender use load up to the cutoff (C5, the lag term in C3)? The pretrained
   models do; Vanilla, by design, does not. If not, C5 drops out and C3 loses a switch.
4. Is a combined row (average of contenders) a secondary "practitioner-style" row, a
   contender, or out of scope?
5. Station choice and weighting stay as in protocol-v2 for all contenders?
6. Training windows longer than 730 days change what "Vanilla" means relative to the
   rows already scored; acceptable inside C1?
7. Which weeks does protocol-v3 score (5.15)?
8. PJM's finding on Dominion suggests DOM will favour models with an explicit trend or
   bias correction. With only two development zones, one of them unusual, the selected
   baseline may be DOM-specific. Is the geometric mean over two zones enough, or should
   the selection also be shown per zone?

## 7. Query log

Retrieval date for every row: 2026-11-15. "Date" is the publication date where the
page gave one.

### Searches (web search tool, standard mode)

| # | Query | What it contributed |
|---|---|---|
| S1 | GEFCom2014 probabilistic load forecasting benchmark winners methods Hong Pinson Fan Zareipour Troccoli Hyndman | Winning load entries and their methods from abstracts; overview paper not returned |
| S2 | GEFCom2017 hierarchical probabilistic load forecasting overview benchmark vanilla winning methods | Overview citation, winner list, winners' paper titles |
| S3 | BigDEAL Challenge 2022 load forecasting results benchmark recency winners methods | Structure, benchmark names, links to leaderboards and arXiv 2305.05575 |
| S4 | Wang Liu Hong 2016 "recency effect" electric load forecasting big data lagged temperature moving average number of lags | Citation; link to the working paper |
| S5 | PJM load forecasting short-term model neural network 2025 seven day forecast methodology weather stations | PJM 2018 deck |
| S6 | time series foundation models electricity load forecasting benchmark baselines weak criticism 2025 Chronos TimesFM short-term load | arXiv 2410.09487, 2602.10848; no load-specific criticism |
| S7 | Hong Wang White 2015 "weather station selection for electric load forecasting" method summary | Abstract-level description of station selection |
| S8 | Pierrot Goude 2011 short-term electricity load forecasting with generalized additive models EDF model terms | Citation only; led to arXiv 2009.06527 |
| S9 | Obst de Vilmarest Goude adaptive methods short-term electricity load forecasting coronavirus lockdown Kalman GAM | arXiv 2009.06527 |
| S10 | Taylor triple seasonal exponential smoothing short-term load forecasting comparison weather-based method lead time day ahead | Taylor 2010 and 2012 abstracts-level findings |
| S11 | BigDEAL Challenge 2023 OR 2024 OR 2025 load forecasting competition Tao Hong results leaderboard | Nothing after 2022 |
| S12 | ERCOT short-term load forecast models description neural network regression seven-day hourly forecast methodology | Only a 2013 long-term review; not used |
| S13 | ISO New England short-term load forecast methodology models neural network regression seven day hourly forecast | Two ISO-NE decks (2024, 2026) |
| S14 | NYISO day-ahead load forecast model description neural network regression weather stations load forecasting manual | NYISO Order 890-A posting |
| S15 | CAISO OR MISO short-term load forecasting methodology "neural network" models seven day hourly forecast documentation Itron MetrixIDR | No operator document |
| S16 | PJM load forecasting 2024 2025 short-term forecast model improvements machine learning gradient boosting operations "load forecast" insidelines | PJM FERC 2024 deck; fact sheet link |
| S17 | Hong Xie Black "Global Energy Forecasting Competition 2017" benchmark "vanilla" teams outperformed benchmark top methods summary quantile regression gradient boosting | Nothing beyond S2 |
| S18 | day-ahead electricity demand forecasting competition post-COVID paradigm IEEE DataPort Farrokhabadi winners methods benchmark | Competition paper citation; two winners' papers |
| S19 | Goude Nedellec Kong 2014 local short and middle term electricity load forecasting with semi-parametric additive models formula terms temperature smoothed lag load | Citation only |
| S20 | LightGBM vs "Tao's Vanilla Benchmark" load forecasting comparison gradient boosting outperforms multiple linear regression hourly load temperature | No direct comparison found |
| S21 | de Vilmarest Goude "State-Space Models Win the IEEE DataPort Competition on Post-covid Day-ahead Electricity Load Forecasting" arXiv | arXiv 2110.00334 |
| S22 | Hong dissertation 2010 "short term electric load forecasting" holiday effect treat holidays as weekend days weekend effect recency model selection years of history | Nothing on the holiday rule; surfaced arXiv 2405.17070 |
| S23 | Hong Fan 2016 "Probabilistic electric load forecasting: A tutorial review" multiple linear regression benchmark naive not useful techniques comparison | Citation only |
| S24 | foundation models load forecasting compared against "generalized additive model" OR "multiple linear regression" strong statistical baseline Chronos electricity demand weather 2025 2026 | arXiv 2602.05390 and others; none with a GAM or regression baseline |
| S25 | National Grid ESO NESO demand forecasting models day ahead week ahead methodology regression machine learning "demand forecast" documentation | NESO strategy document and data-portal products |
| S26 | MSTL Bandara Hyndman Bergmeir multiple seasonal decomposition hourly electricity demand forecast accuracy vs TBATS Prophet | MSTL paper, Nixtla tutorial |
| S27 | "foundation model" time series forecasting evaluation pitfalls weak baselines critique "seasonal naive" tuned gradient boosting energy load "strong baselines" 2025 | Litmus-test paper; arXiv 2502.12944, 2604.11529 |
| S28 | Wood Goude Shaw 2015 "Generalized additive models for large data sets" UK grid load model terms bam | Citation; application is French grid load |
| S29 | ERCOT "mid-term load forecast" MTLF models seven day hourly weather zones multiple models selected forecast | ERCOT 2024 board deck |
| S30 | CAISO day-ahead load forecast "neural network" Itron automated load forecasting system ALFS models | Itron guide; nothing on CAISO's models |
| S31 | GEFCom2017 final match winners "quantile regression" Kanda Veguillas data preprocessing benchmark vanilla qualifying match Ziel lasso | arXiv 1809.03561; final-match winner's abstract |
| S32 | Tao Hong blog how many years of history load forecasting training length "two years" OR "three years" regression models | Nothing decisive; SAS holiday paper uses five years |

### Pages relied on

| URL | Title | Date | What it contributed |
|---|---|---|---|
| https://prac.im.pwr.edu.pl/~hugo/RePEc/wuu/wpaper/HSC_15_08.pdf | Wang, Liu, Hong: Electric load forecasting with recency effect: a big data approach (working paper HSC/15/08) | 2015 | Vanilla equation with trend; recency equation; 584 pairs; training, validation and test years; error reductions; naive models' weakness; per-hour options |
| https://ideas.repec.org/p/wuu/wpaper/hsc1508.html | Index page for the same paper | 2015 | Abstract figures (18 to 21%, 12 to 15%); PDF link (the listed host returned 404; the `prac.im.pwr.edu.pl` host worked) |
| https://blog.drhongtao.com/2015/02/load-forecasting-recency-effect-big-data.html | Hong's post announcing the paper | 2015-02 | Abstract only |
| https://ar5iv.labs.arxiv.org/html/2305.05575 | Rubattu, Maroni, Corani: Electricity load and peak forecasting: feature engineering, probabilistic LightGBM and temporal hierarchies | 2023-05 | BigDEAL 2022 ranks of Vanilla, the recency benchmark and the entry; features; error by pipeline step; tuning method |
| https://blog.drhongtao.com/2022/11/bigdeal-challenge-2022-qualifying-match.html | BigDEAL Challenge 2022 qualifying match | 2022-11-14 | Task, data, tracks, 14 of 78 teams qualified |
| https://blog.drhongtao.com/2022/12/bigdeal-challenge-2022-final-leaderboard.html | BigDEAL Challenge 2022 final leaderboard | 2022-12-19 | Final-match format, top teams, ranking rule |
| https://blog.drhongtao.com/2018/12/temperature-based-models-vs-time-series-models.html | Temperature-based models vs. time series models | 2018-12 | Where each family wins by horizon and by ex-post or ex-ante; view on naive benchmarks |
| https://blog.drhongtao.com/2019/04/gefcom2017-hierarchical-probabilistic-load-forecasting.html | GEFCom2017 overview paper announcement | 2019-04 | Abstract: first real-time ex-ante edition; DOI 10.1016/j.ijforecast.2019.02.006 |
| https://blog.drhongtao.com/2016/01/gefcom2014-probabilistic-electric-load-forecasting.html | Xie and Hong's GEFCom2014 entry | 2016-01 | Components of one top-3 entry |
| https://en.wikipedia.org/wiki/Global_Energy_Forecasting_Competition | Global Energy Forecasting Competition | n/a | Editions and winner names only |
| https://ar5iv.labs.arxiv.org/html/1809.03561 | Ziel: Quantile regression for the qualifying match of GEFCom2017 | 2018-09 | Task, benchmarks, results against Vanilla, inputs |
| https://arxiv.org/abs/1603.01376 | Ziel and Liu: Lasso estimation for GEFCom2014 probabilistic load forecasting | 2016-03 | Abstract: beats two regression benchmarks |
| https://ar5iv.labs.arxiv.org/html/2110.00334 | de Vilmarest and Goude: State-space models win the IEEE DataPort competition | 2021-10 | Task, base models and their terms, errors before and after adaptation |
| https://arxiv.org/abs/2107.06268 | Ziel: Smoothed Bernstein online aggregation for day-ahead electricity demand forecasting | 2021-07 | Abstract: model pool and combination |
| https://ar5iv.labs.arxiv.org/html/2009.06527 | Obst, de Vilmarest, Goude: Adaptive methods for short-term electricity load forecasting during COVID-19 lockdown in France | 2020-09 | EDF GAM term structure, training period, errors |
| https://arxiv.org/abs/2405.17070 and https://arxiv.org/pdf/2405.17070 | Zimmermann and Ziel: Efficient mid-term forecasting of hourly electricity load using generalized additive models | 2024-05, revised 2025-02 | GAM design, benchmark list, results table, remarks on Vanilla |
| https://pjm.com/-/media/committees-groups/task-forces/sodrstf/20180309/20180309-item-04-load-forecasting.ashx | PJM: Load Forecasting Overview (Anastasio) | 2018-03-09 | Eight models, inputs, timing, which forecast operators use |
| https://www.pjm.com/-/media/DotCom/library/reports-notices/testimony/2024/20240709-presentation-ferc-technical-conference-hourly-load-forecasting-machine-learning-algorithms.pdf | PJM: Hourly electricity load forecasting using machine learning algorithms (Wu, Walter, Giacomoni) | 2024-07-09 | Models tested, features, training and test periods, results, Dominion bias |
| https://www.nyiso.com/documents/20142/1395789/FERC890aDALFDesc.pdf/a87e4c73-2d59-0d83-d3c0-b31e6c3f7e00 | NYISO: day-ahead load forecast description (Order 890-A) | undated | Model families, horizon, weather inputs |
| https://www.ercot.com/files/docs/2024/06/11/7%20Board%20Education%20%E2%80%93%20Load%20Forecasting.pdf | ERCOT: Board education, load forecasting | 2024-06 | Model families, weather sources, the averaged forecast |
| https://iea-wind.org/wp-content/uploads/2025/01/6_IEA_Rutgers_Task51_29Oct2024_vrojo.pdf | ISO-NE: Weather applications in the long-term load forecast (Rojo) | 2024-10-29 | Structure of the short-term models, features, history length, stations |
| https://www.esig.energy/attachment/serve/pfx_prototype_isone_march2026 | ISO-NE: Prototype methodology for a 7-day probabilistic load forecast | 2026-03 | Load models are sets of 25 neural networks; stated limits |
| https://www.neso.energy/document/373066/download | NESO: Energy Forecasting Strategy | 2026-03 | Legacy tools being replaced; demand model family not stated |
| https://de.itron.com/w/a-practitioners-guide-to-short-term-load-forecast-modeling | Itron: A practitioner's guide to short-term load forecast modeling (Monforte) | 2018-12-05 | Like-day, regression and neural networks named as standard |
| https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/electricityloadforecasting.html | Nixtla: Electricity load forecast tutorial | n/a | MSTL against seasonal naive and Prophet on one PJM test day |
| https://arxiv.org/abs/2107.13462 | Bandara, Hyndman, Bergmeir: MSTL | 2021-07-28 | Abstract |
| https://ora.ox.ac.uk/objects/uuid:ee05c2f4-99d5-4b23-945a-9527f5defafa | Taylor: Triple seasonal methods for short-term electricity demand forecasting | 2010 | Abstract |
| https://neurips.cc/virtual/2025/loc/san-diego/130437 | Bouainouche et al.: Linear regression as a litmus test for time series forecasting benchmarks | 2025-12 | Abstract: common baselines are a low bar |
| https://arxiv.org/abs/2602.21415 | Benchmarking state space models, Transformers and recurrent networks for US grid forecasting | 2026-02 | Abstract: baselines are deep models only |

Pages opened that gave nothing usable: PJM fact sheet (`www2.pjm.com`, not a PDF);
PJM deck at `datasnapshot.pjm.com` (failed; the `www.pjm.com` copy worked);
`people.bath.ac.uk` copy of the Goude, Nedellec and Kong preprint (redirected);
`ar5iv` and `arxiv.org/html` versions of arXiv 2405.17070 (conversion error, 404; the
PDF worked); ERCOT's 2013 load forecasting review (long-term only);
`arxiv.org/abs/2110.09947` (an unrelated paper, opened by mistake).

Repository files read: `CLAUDE.md`, `BASELINES.md`, `notes/classical_baselines.md`,
`notes/standard_methods.md`, `notes/hong2014_gefcom2012.md`, parts of
`notes/model_families.md`, `REFERENCE.md` lines 55 to 100, parts of
`results/README.md`, `harness/baselines.py` (outline and the competition row),
`protocol.yaml` (origins, gates, metrics), `protocol-v1.2.yaml` (weather coverage),
`protocol-v2.yaml`, `protocol-v2.1.yaml` (header), `DEVIATIONS.md` (tail),
`core/pyproject.toml`, and all 31 files under `scorecards/`. `notes/moran.md` and
`notes/weather_skill_sensitivity.md` were opened for their outlines only.
