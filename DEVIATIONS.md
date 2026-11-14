# Deviations from protocol-v1

Dated changes to the frozen protocol. `protocol.yaml` is never edited; each change is a
new version file.

- **2026-11-13, protocol-v1.1** (`protocol-v1.1.yaml`): added two secondary rows,
  Tao's Vanilla Benchmark as written in Ziel and Liu (2016) and the same with a linear
  trend, after a search for the field's standard baselines showed the
  original baseline set came from a single recent study. The primary comparison, its
  baseline, bar, verdict rule and sentences are unchanged. The new rows were run on the
  gate origins first and on the scored origins once, after the tag `protocol-v1.1`.
- **2026-11-13, label correction (no protocol change):** the v1 regime `oracle`, described
  in `protocol.yaml` as "Archive (reanalysis) temperature" and in `REFERENCE.md` as ERA5,
  is ECMWF IFS 9 km operational analysis from Open-Meteo's archive (identical at every
  hour to `models=ecmwf_ifs` at all six stations; 1.1 to 1.7 °C RMSE from ERA5 per
  station). The v1 `forecast` regime is HRRR on lead day 1 and GFS on days 2 to 7. The
  frozen wording is a known misnomer; `protocol.yaml`, the v1 and v1.1 inputs and all
  their results are unchanged. `REFERENCE.md` is corrected.
- **2026-11-13, protocol-v1.2** (`protocol-v1.2.yaml`): added four secondary weather
  regimes with ERA5 as the declared temperature truth and as history in every one of
  them: `oracle_era5`, `forecast_gfs` (v1 forecast horizon), `forecast_ifs` (ECMWF IFS
  0.25°) and `forecast_aifs` (ECMWF AIFS Single), lead-matched as in v1. Rows: the lag
  regression with temperature, Vanilla with trend and Chronos-2 with temperature. The
  window-drop rule for these regimes is scoped per regime (AIFS lacks three scored
  weeks). The primary comparison, its sentences and every v1 and v1.1 row are unchanged.
  Gate runs first; the scored origins are run once, after the tag `protocol-v1.2`.
- **2026-11-13, source verified (no protocol change):** the linear trend in
  `vanilla_benchmark_trend` (protocol-v1.1), recorded at registration as found in search
  summaries only, is confirmed by the competition paper (Hong, Pinson and Fan 2014,
  section 2.3). No definition, row or result changes. See `notes/hong2014_gefcom2012.md`.
- **2026-11-13, protocol-v1.3** (`protocol-v1.3.yaml`): added two secondary model rows:
  a competition-grade LightGBM after the BigDEAL 2022 feature design (temperature and
  calendar only, detrended log target, 730-day window, fixed untuned hyperparameters) and
  TabPFN-TS with pinned TabPFN v2 weights and temperature (local CPU only). Both run in all
  six regimes (v1 and v1.2) and are scored on the windows the existing scoring kept; their
  output goes to `results/models_v13/`, which no earlier scorer reads. Registered
  comparisons: each new row vs the temperature regression and vs Vanilla with trend, and
  Chronos-2 with temperature vs each new row. The primary comparison, its sentences and
  every v1, v1.1 and v1.2 row and file are unchanged. LightGBM is scored once after the
  tag; the TabPFN scored run (about 50 h on CPU) is deferred and will be run once at the
  same tag with no change to its definition.
- **2026-11-13, protocol-v2 drafted and gated, NOT tagged or scored**
  (`protocol-v2.yaml`, written from `protocol-v2-draft.yaml`, which is unchanged): a new
  primary comparison, Chronos-2 with temperature against Vanilla with trend, ECMWF AIFS
  forecast weather with ERA5 history, on the new zones AEP and AE (PJM-weighted ERA5 grid
  cells); DOM and JC become development zones; secondary rows include two calendar rows
  (`vanilla_benchmark_trend_holiday`, `chronos2_temperature_calendar`) fed by the harness
  calendar table. Every row was run on the gate origins only; output in
  `results/gate/v2/`. The file is marked not frozen pending the owner's review; the tag
  `protocol-v2` does not exist and no v2 row has been run on a scored origin. Every
  earlier protocol file and result is unchanged.
- **2026-11-14, protocol-v2 frozen and tagged:** the owner reviewed the gate results and
  approved the freeze. Changed before the tag, wording only and without reference to any
  scored result: the outcome sentences name the baseline as Tao's Vanilla Benchmark with
  trend (not "the temperature-only regression"), and the panel's data-gap rule is marked
  confirmed. Accepted as written: the default holiday treatment of
  `vanilla_benchmark_trend_holiday` (the cited paper's full text was not read), and DOM
  and JC keeping more windows under the v2 drop rule than under v1.2 (development zones;
  not like-for-like with v1.2). The scored origins are run once, after the tag.
- **2026-11-14, protocol-v2 scored once:** every v2 row was run on the 52 scored origins
  from a clean tree at the tag `protocol-v2`, in one pass with no rerun. Output in
  `results/v2/`. Kept windows: AEP and AE 45 with AIFS weather and 48 in the other three
  regimes; DOM and JC 47 with AIFS, 50 with GFS and IFS, 49 with ERA5. No definition was
  changed and nothing crashed.
- **2026-11-14, TimesFM 3.0 with temperature added as a flagged secondary row**
  (`timesfm3_temperature`, Yuri's decision after two judged claims needed it). Not a new
  protocol version: protocol-v1 defines pretrained models as a class, and the row is added
  the way `timestral_temperature` was. Weights `google/timesfm-3.0-pytorch` at commit
  43046b8, weights file dated 2026-08-24, non-commercial licence. Settings fixed before
  any scored run: temperature as a known-future covariate, 2,048 hours of context, the
  library's defaults (symmetric averaging, forecasts made positive). Gate origins first
  (complete and plausible, existing gate rows unchanged), then the scored origins once.
  Most scored weeks precede the weights, so the row is flagged as not out-of-sample and
  cannot change the primary outcome.
