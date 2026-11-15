# Splitting the project (decision 51): notes, nothing done yet

After `protocol-v3` is scored the project becomes two repositories.

## Public: the week-ahead benchmark (this repo)

Stays: `fetch.py`, `harness/`, `protocol*.yaml`, `models/`, `models_ff/`, `results/`,
`fetch_manifest.json`, the agent (skills, `tools/`, `spec.yaml`, `schemas/`,
`candidates/`, `evidence/`, `scorecards/`), `registry/`, `reviews/` (verdicts), the
dashboard, the tests.

## Private: long-term load forecasting, 1 to 6 months, PJM first

Starts with: run transcripts (`transcripts/<year>/<run_id>.jsonl.gz`), private review
notes (`notes/<registry key>.md`), and a daily capture of PJM's 7-day forecast
(Data Miner `load_frcstd_7_day` is current-only, so it has to be collected from now on;
check PJM's redistribution terms before anything is published). Later: the long-horizon
protocols, data and results. It installs the public harness as a package; it does not
copy it.

## Before the split

- Add a licence to the public repo (there is none; GitHub reports none).
- Make `harness/` installable: `core/pyproject.toml` has `package = false` and
  `harness/` sits outside `core/`.
- Third-party terms to carry over: TabPFN asks for the attribution "Built with
  PriorLabs-TabPFN"; TimesFM 3.0 weights are non-commercial; TabPFN 2.5 and later
  forbid production use (`notes/model_families.md`).

## What is tied to 168 hours and to PJM today

| Where | What |
|---|---|
| `protocol*.yaml`, `spec.yaml` | zones, `horizon_hours: 168`, explicit Monday origin lists |
| `harness/baselines.py` | `LAG = 168h`, 168 day-of-week by hour dummies, New York calendar default |
| `harness/data.py` | `horizon_index(..., hours=168)`, zone tuples, New York timezone default |
| `harness/score.py`, `harness/v2.py`, `harness/export_inputs.py` | horizon must be 168 long |
| `models/chronos2.py` | `prediction_length=168`, zone tuples |
| `fetch.py` | 7 lead days, the EIA PJM sub-BA endpoint, zone lists |

## What a 1 to 6 month project needs that does not exist

- Targets: monthly energy and monthly peak per zone, not hourly load.
- Weather: no forecast reaches that far (the lead-matched forecast regime ends at 7
  days), so climate normals, resampled historical years or scenarios; the regime
  definitions and hard rule 2 need a new form.
- Longer history and structural drivers (economic series, data-centre growth; PJM's
  own test found Dominion's growth biased a boosted model, `notes/baseline_research_v3.md`).
- Baselines of its own: PJM's long-term load forecast report is the operator reference.
- Far fewer independent windows: a few per year, so the statistics change.
