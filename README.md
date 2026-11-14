# Receipts for Forecasting Papers

An agent that finds newly published forecasting methods, judges whether they apply to a
specific problem with every claim cited, and runs the runnable ones on our own benchmark
to report claimed against measured. We call the result a receipt.

Benchmark: PJM hourly electricity load, a week ahead (168 hours), forecast every Monday
at midnight. The first zones were JC and DOM; the newest test adds AEP and AE.

Dashboard: https://shlyakh.github.io/load-bearing/
Slides for the three-minute talk: https://claude.ai/artifact/APSUpcPFEfifCXQw9cZGXj
(talking points in `notes/talk_3min.md`)

## The question

A pre-registered study of Great Britain's electricity demand (Zenodo record 24161799)
found that a pretrained forecasting model, Chronos-2, and a plain regression roughly tie
once both get the same weather: day ahead, Chronos-2's error was 0.966 of the
regression's (90% interval 0.931 to 1.001). We ask whether that tie transfers to US grid
zones a week ahead. A receipt says "transfers" or "does not transfer". It is a transfer
test and says nothing about whether the GB result is correct.

Every comparison is a ratio of mean weekly errors (below 1, the first-named model is
better) with a 90% interval from resampling whole weeks. The bar is 10%, fixed before
scoring: the whole interval below 0.90 is "worth switching", the whole interval inside
0.90 to 1.10 is a "practical tie", anything that crosses a bar edge is "inconclusive".

## What has been measured, in order

Each step is a protocol version, frozen at a git tag before its scored run and scored
once. Later steps add secondary rows and never change an earlier result. Full numbers:
`results/README.md`. Changes and corrections: `DEVIATIONS.md`.

### 1. protocol-v1: Chronos-2 against the temperature-only regression (DOM, JC)

The primary comparison: Chronos-2 with temperature against our lag regression with
temperature (the "temperature-only regression"), archived forecast weather, 48 scored
weeks per zone.

| Zone | Ratio | 90% interval | Reading |
|---|---|---|---|
| DOM | 0.730 | 0.665 to 0.805 | worth switching |
| JC | 0.817 | 0.686 to 0.960 | inconclusive |

So the GB "rough tie" does not transfer to DOM under this protocol, and is undecided on
JC. All 48 scored weeks start after the date of Chronos-2's pinned weights. Earlier years
of the same public series may be in its training data.

The leaderboard also has seasonal naive, the regression without weather, LightGBM on the
regression's inputs, Chronos-2 without weather and with a 48-hour data gap, TimesFM 2.5
with and without temperature, and Timestral. Timestral has the lowest error on the board
but its weights were published inside the scored year (1 of 48 weeks starts after them),
so it is labelled not out-of-sample.

### 2. protocol-v1.1: against the field's standard benchmark (secondary)

After scoring, a recorded search for the field's standard baselines (`BASELINES.md`)
found Tao's Vanilla Benchmark, the organisers' benchmark in the GEFCom competitions. It
was added in two forms, with and without a linear trend. Vanilla with trend has 23% less
error than the temperature-only regression on DOM and 18% less on JC.

| Forecast weather | DOM | JC |
|---|---|---|
| Chronos-2 with temperature vs. Vanilla with trend | 0.946 (0.885 to 1.011) | 0.997 (0.903 to 1.088) |

Against the standard benchmark Chronos-2's lead is gone on JC (a practical tie) and small
on DOM (inconclusive). The v1 primary outcome stands, because its baseline was fixed in
advance, but it shows that Chronos-2 beats our first regression, not that it beats a
standard load-forecasting regression.

### 3. protocol-v1.2: weather sources, with ERA5 as the truth (secondary)

The v1 series first called "oracle" or reanalysis turned out to be an ECMWF IFS analysis
(9 km), not ERA5. The dashboard now calls it "analysed weather". v1.2 makes ERA5 the
temperature truth and history in every setting and compares four horizon sources: the
GFS/HRRR mix used in v1, ECMWF IFS 0.25°, ECMWF AIFS, and ERA5 itself as perfect weather.

- Against Vanilla with trend, Chronos-2 is level under every source (0.94 to 1.04). On
  DOM the ratio climbs as the weather improves: 0.937 (GFS), 0.967 (IFS), 0.995 (AIFS),
  1.044 (ERA5). A regression that uses temperature well gains more from better weather
  than Chronos-2 does.
- Against the temperature-only regression, Chronos-2's lead holds under every source
  (0.69 to 0.81).
- AIFS gives the lowest load error for every model and cuts the extra error from
  forecast weather by a third to two thirds against GFS. IFS 0.25° was no better than the
  GFS/HRRR mix for load over this year.
- The AIFS archive is incomplete for three April weeks, so AIFS rows cover 45 weeks.

### 4. protocol-v1.3: a competition-grade LightGBM (secondary)

An untuned LightGBM built like a published competition entry (BigDEAL 2022 feature
design: 91 calendar and temperature features, detrended log target, two years of
history, no load input). Its point error is lower than Chronos-2's in all 12 zone and
weather cells (1 to 6% lower with forecast weather, 8 to 19% lower with weather known
after the fact), but only one cell is decided (a practical tie); the rest are
inconclusive. Against the temperature-only regression it is 0.57 to 0.78; against
Vanilla with trend, 0.84 to 1.00.

TabPFN-TS with v2 weights is registered in the same version but **not scored**: its run
takes about 50 hours on CPU.

### 5. protocol-v2: a fresh test on two new zones (the current primary)

Every model had already been seen on DOM and JC, and the first baseline was weaker than
the field's standard. So v2 fixed a new primary comparison in advance and read it on two
zones no model had been run on: Chronos-2 with temperature against Vanilla with trend,
ECMWF AIFS forecast weather, ERA5 history, 45 scored weeks per zone.

| Zone | Ratio | 90% interval | Reading |
|---|---:|---|---|
| AEP | 1.006 | 0.906 to 1.118 | inconclusive |
| AE | 0.890 | 0.796 to 0.999 | inconclusive |

Both intervals cross the 10% bar, so 45 weeks cannot separate a tie from a real
difference on either zone. Chronos-2 has no clear lead, and no tie is confirmed. All 45
scored weeks start after the pinned weights.

Secondary readings, AIFS weather:

- The same pair on the development zones: DOM 1.017 (0.933 to 1.104), JC 1.001 (0.899 to
  1.112), 47 weeks each. Under the other sources: AEP 1.03 (ERA5), 1.04 (GFS), 1.04
  (IFS); AE 0.93, 0.93, 0.90.
- **Calendar inputs.** Every model that takes calendar inputs gets the same harness table
  (hour, day of week, US federal holiday, the Christmas to New Year week). Given the
  calendar, Chronos-2 got worse in all four zones: AEP 1.039, AE 1.107, DOM 1.125, JC
  1.055 of its error without it. Holiday terms left Vanilla with trend within 3% (AEP
  0.970, AE 1.003, DOM 0.993, JC 0.997), a practical tie everywhere.
- The competition-grade LightGBM has the lowest error on AEP (530 MW against 598 MW for
  Vanilla with trend); its ratio, 0.886 (0.809 to 0.966), is inconclusive.
- Chronos-2 with temperature against the v1 temperature-only regression: AEP 0.672, AE
  0.765, beyond the bar in both.

## How the new zones were chosen

The rule was written before any model ran on a new zone (`notes/zone_selection.md`,
code in `tools/zone_selection/`). For each original zone, the new zone is the PJM
sub-area in EIA-930 with the smallest standardised distance on seven load statistics
(size, growth, seasonal peaks, weekly and daily shape) over the two years before the
first scored week. Zones correlating 0.95 or more with the original, or under 1,000 MW,
were excluded.

- **AEP** (American Electric Power, Indiana to Virginia) matches DOM: similar size,
  growing load, winter peak about equal to summer peak. Distance 1.56; next AP at 3.06.
- **AE** (Atlantic City Electric, southern New Jersey) matches JC: strongly
  summer-peaking. Distance 2.12. It borders JC and their daily load correlates at 0.93;
  it was kept because it is the only other usable zone with JC's summer-peaking shape.

Disclosed: the rule and its thresholds were written with the load statistics of all 20
zones in view. No model had been run on any new zone.

## Weather points, not weather stations

Every model in a weather setting gets the identical temperature series. That series is
an average over a few **weather points**. A weather point is a grid cell of a weather
model (0.25° for ERA5), queried at a latitude and longitude. No station readings are
used. "Station" is kept for PJM's own airport stations.

- AEP and AE (v2): the ERA5 grid cells that hold PJM's stations for the zone, averaged
  with PJM's published weights. AEP has five cells (Columbus 0.234, Fort Wayne 0.227,
  Charleston WV 0.226, Roanoke 0.162, Akron-Canton 0.151). AE has one cell, inland of
  Atlantic City. Details in `notes/zone_geography.md`.
- DOM and JC keep their three v1 points each and an unweighted mean.

## The agent

Three Claude Code skills in `.claude/skills/`, built on Claude's own web search and fetch:

- `/scan` finds forecasting claims published in the last 120 days (web search plus the
  arXiv, Hugging Face and Zenodo listings read by `tools/feeds.py`) and writes them to
  `candidates/`.
- `/judge` scores one candidate against the problem spec (`spec.yaml`), citing a source
  for every claim, and writes a scorecard (`scorecards/`, checked by
  `tools/validate_scorecard.py`). It reasons only from the evidence ledger
  (`evidence/`, written by `tools/ledger.py`).
- `/run-candidate` runs an accepted candidate on the frozen benchmark and writes its
  receipt (`tools/receipt.py`).

`tools/pipeline.py` runs scan, judge and run-candidate in one command, each step a
recorded headless run (`tools/run_skill.py`, records in `runs/`). Headless runs do not
start model runs: if a model row is missing, the step stops and says what a person has
to run. Outputs are kept per search provider (`claude` now, `youcom` later) so the two
can be compared on the same inputs. `.claude/skills/providers.md` maps the skills to
each provider's tools.

LinkedIn is not a source: it is never searched, fetched or cited.

## Dashboard

https://shlyakh.github.io/load-bearing/ , deployed from `dashboard/` by GitHub Actions on a
push to `main`. It is a static page (`dashboard/index.html`) that reads `dashboard/data.js`,
built from `results/` by `dashboard/build_data.py`. Tabs: The problem, Methods, Receipt,
New zones, Leaderboard, Weather, New claims, How it works. `dashboard/story.html` tells
the same results as one scrolling page.

## Reproduce

From the repository root. Raw data is git-ignored; `fetch.py` downloads it and writes
SHA-256 hashes to `fetch_manifest.json`, and scoring refuses to run if a raw file does
not match. A fresh `download` rewrites the manifest, so compare it with the committed
`fetch_manifest.json` (`git diff`) to see whether the source data has changed since the
scored runs.

```
uv run --project core python fetch.py download            # v1 load and weather
uv run --project core python fetch.py process
uv run --project core python fetch.py download-v12        # v1.2 weather sources
uv run --project core python fetch.py process-v12
uv run --project core python fetch.py download-v2         # AEP and AE load and weather
uv run --project core python fetch.py process-v2
uv run --project core python fetch.py verify              # raw files match the manifest
uv run --project core pytest tests -q
uv run --project core python -m harness.v2 score scored   # rescore v2 from stored forecasts
uv run --project core python tools/pipeline.py claude     # judge and run the latest scan
uv run --project core python dashboard/build_data.py
```

Model rows run in their own environments (`models/` for Chronos-2, `models_ff/` for
FoundationForecast and TabPFN), so a model dependency cannot break the baselines. Each
protocol file names its commands; `harness/v2.py` lists the v2 ones.

## Prior work disclosure

This project is entered in the Ground Truth hackathon (New York, Nov 14, 2026). The
build time starts at 10:00 Eastern on Nov 14. Everything committed before then is prior
work and not hackathon work. The git tag `pre-hackathon` marks that state:

- data and weather pulls, the frozen protocols v1 to v2, the evaluation harness
- baselines, foundation-model rows and every scored result above (protocol-v2 was frozen
  and scored on the morning of Nov 14, before the start)
- zone selection and weather points for AEP and AE
- problem spec, scorecard schema, 11-item evaluation set
- the three agent skills and `tools/pipeline.py`, running on Claude's own web search and
  public listings
- the dashboard and story pages, the tour and the narration text
- the wiring for the You.com search provider (`tools/run_skill.py`,
  `notes/youcom_provider.md`), written that morning and tested only against a local mock:
  no You.com call had been made and no API key existed

Hackathon-day work, after the tag: every live You.com run of the skills, whatever has to
change to make them work on the real service, the comparison of the two providers on the
same inputs, and whatever the day's scan finds and runs.

## Not done yet

- **Prospective panel.** Planned with v2, not built: forecasts committed each Monday
  before the week's load exists, scored when it is published, read after 13, 26 and 52
  weeks (`notes/prospective_panel_plan.md`).
- **TabPFN-TS scored run** (registered in v1.3, about 50 hours on CPU). Its licence asks
  for "Built with PriorLabs-TabPFN" wherever its results are published.
- **Dashboard tour video** (`dashboard/tour.webm`) predates the New zones tab.
- Yuri's blind labels for the evaluation set and the judge agreement table.
- A check against station observations, to see whether ERA5 as truth flatters AIFS.
- Humidity, solar and wind as inputs (a later v2.x addendum).
- A fair test of models whose weights were published inside the scored year.

## Caveats

- One year of weekly origins per zone gives wide intervals; "inconclusive" is common.
- The information set is idealised: load is visible up to the cutoff, which favours
  models that use the most recent hours. A 48-hour-gap row measures this for Chronos-2.
- ERA5 is a model product, not observations, and AIFS was trained on ERA5.
- AE rests on a single grid cell. AE and JC are correlated (0.93).
- EIA-930 load is operator-reported, not settlement quality.

## Documents

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Rules for anyone (or any agent) working in this repo |
| `HANDOFF.md` | Where things stand, for the next session |
| `DECISIONS.md` | Fixed design choices and open questions |
| `DEVIATIONS.md` | Dated changes and corrections to the frozen protocols |
| `protocol.yaml`, `protocol-v1.1.yaml` to `protocol-v2.yaml` | The frozen backtest definitions |
| `results/README.md` | Every scored number, by protocol version |
| `BASELINES.md` | The search for the field's standard baselines |
| `TONIGHT.md`, `FRIDAY.md`, `HACKATHON.md` | Task briefs for Thursday, Friday and Saturday |
| `REFERENCE.md` | Endpoints, formulas, schemas, unverified items |
| `spec.yaml` | The problem the judge scores against, and the scan's configuration |
| `eval/items.yaml` | 11 candidates for testing the judge (`eval/label_sheet.md` for blind labelling) |
| `notes/zone_selection.md`, `notes/zone_geography.md` | How AEP and AE and their weather points were chosen |
| `notes/` | Other reading notes: the GB study, FoundationForecast, feeds, weather, telemetry |

## Acknowledgements

The backtest discipline follows Andy Moran's GB demand studies
(`AndyMoran/gb-foundation-model-tests`). The skills approach follows
`dgilford/ai-science-toolkit`. Foundation models are run through
`TimeCopilot/foundationforecast`.
