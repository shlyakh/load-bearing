# Handoff: where things stand (Fri Nov 13, 2026, evening)

Read this first when starting a new session, then `CLAUDE.md` (rules), `DECISIONS.md`
and `results/README.md` (all numbers). This file is a snapshot; when it disagrees with
the repository, the repository wins.

## State

- Everything is committed and pushed to `main`. Tags: `protocol-v1`, `protocol-v1.1`,
  `protocol-v1.2`, `protocol-v1.3`.
- `.github/workflows/pages.yml` deploys the dashboard automatically on a push to `main`
  that touches `dashboard/`.
- After a reboot, local Langfuse needs restarting: run `tools/start_langfuse.sh`
  (starts Docker Desktop if needed, then the containers in `/Users/yuri/work/langfuse`,
  and waits until http://localhost:3000 answers).

## Where the dashboard lives

- GitHub Pages: https://shlyakh.github.io/load-bearing/ . Deployed by the workflow on every
  push to `main` that touches `dashboard/`; the `gh-pages` branch is no longer used.
- Development artifact: https://claude.ai/artifact/UyjuJT9VXa4bcjnSrFgmjr
- Tabs: The problem, Methods, Receipt, New zones, Leaderboard, Weather, New claims, How
  it works. The tour and its video predate the New zones tab and the new maps.
  Tour of 9 steps, video in `dashboard/tour.webm`.

## What the results say (48 scored weeks, PJM zones DOM and JC, week ahead)

1. **Primary (protocol-v1, frozen):** Chronos-2 with temperature against our lag
   regression with temperature, forecast weather: DOM 0.730 (0.665 to 0.805), worth
   switching; JC 0.817 (0.686 to 0.960), inconclusive.
2. **Against the field's standard (protocol-v1.1, secondary):** Chronos-2 against Tao's
   Vanilla Benchmark with trend: DOM 0.946 (0.885 to 1.011), JC 0.997 (0.903 to 1.088).
   The lead largely disappears. The trend term is now verified from the competition
   paper (`notes/hong2014_gefcom2012.md`).
3. **Weather sources (protocol-v1.2, secondary):** with ERA5 as the temperature truth
   and four sources (GFS/HRRR mix, ECMWF IFS, ECMWF AIFS, ERA5 as perfect weather),
   Chronos-2 and Vanilla with trend are level under every source (0.94 to 1.04), and on
   DOM the ratio climbs as weather improves. AIFS gives the lowest load error for every
   model; IFS was no better than GFS for load this year. AIFS rows cover 45 weeks.
4. **Correction made:** the series first called "oracle / reanalysis" is ECMWF IFS
   analysis, not ERA5. `REFERENCE.md`, `DEVIATIONS.md` and the dashboard say so; the
   frozen protocol files keep the old wording.
5. **New model rows (protocol-v1.3, secondary):** see the section at the end of this
   file.
6. **protocol-v2 (frozen, tagged and scored once on 2026-11-14):** the new primary, on
   zones no model had been run on, Chronos-2 with temperature against Vanilla with trend,
   AIFS weather, 45 weeks: AEP 1.006 (0.906 to 1.118) and AE 0.890 (0.796 to 0.999), both
   inconclusive. The calendar made Chronos-2 worse in all four zones (1.04 to 1.13);
   holiday terms left Vanilla within 3%. Section "protocol-v2" of `results/README.md`.
   The dashboard shows them on the "New zones" tab.

## State on Nov 14, late morning

Done today: protocol-v2 frozen, tagged and scored; dashboard "New zones" tab, county zone
maps, US map with operator names; tour with a New zones step, re-recorded; Receipt tab
points to the fresh test; `README.md` and `dashboard/story.html` brought up to date.

Waiting on Yuri:

1. **You.com key.** The provider is wired and tested offline only. Add `YDC_API_KEY` to
   `.env`, then follow `notes/youcom_provider.md` (smoke test, judge, pipeline, compare).
2. **Voice for the video.** `tools/make_video.py` builds `video/out/receipts_demo.mp4` from
   `video/narration.json` with the macOS system voice (a draft: Apple's licence limits it
   to personal, non-commercial use). A Treg or other hosted voice needs a key and one
   new function in that script.
3. **README prior-work line.** It says everything up to today predates the hackathon;
   this morning's v2 and dashboard work is dated Nov 14. Correct it once the event's
   start time is known.

## State on Nov 14, about noon (hackathon, You.com live)

- **You.com runs live.** Key in `.env`. Smoke test, one scan (40 candidates) and nine
  judges done; all nine scorecards validate. On the five claims judged under both
  providers the verdicts agree, five of five (`results/provider_comparison.csv`).
  Receipts written for two claims from existing leaderboard rows, both "partially".
- **What the live runs showed, costs and feedback:** `notes/youcom_usage_and_feedback.md`.
  Most important: only one `site:` per query restricts a search; `(site:a OR site:b)`
  silently searches the open web. `.claude/skills/providers.md` is corrected.
- **Sources widened** from `notes/source_seed_list.md`: two domain groups and three
  load queries in `spec.yaml`; `tools/feeds.py` also lists two journals (Crossref),
  PyPI releases and GitHub releases (`tests/test_feeds.py`). The GitHub listing failed
  once during the scan with an HTTP error, probably the unauthenticated limit of 60
  requests an hour (not confirmed); the run kept the earlier rows.
- **Dashboard:** New claims has a provider comparison table and a switch between the
  Claude and You.com scans.
- **Spend:** $71.24 of model cost on today's headless runs after the noon scans, cap $75 (Yuri). You.com credit
  left: 917 cents when checked late morning.
- **Scan comparison (noon):** the Claude scan was rerun on the current `spec.yaml`
  (44 candidates, 29 shared with the You.com scan; table in
  `notes/youcom_usage_and_feedback.md`). A You.com rerun with one `site:` per query
  stopped at the Claude usage limit (resets 16:20) and wrote nothing. Spend is then
  $71.24 of the $75 cap: no further model runs without Yuri's word.
- **Not done:** the Kafritsas Substack post was not judged (the Substack robots
  question is open); research tasks are still counted as calls in the comparison (48
  calls were 6 tasks); You.com charges are not in the run records.
- **After the hackathon:** scheduling per `notes/agent_runtime_and_scheduling.md`
  (verify its check list first; design with the prospective panel, decision 35); a
  written study of LinkedIn routes for Yuri to decide (rule 10 and decision 21 unchanged,
  no LinkedIn access before that).
- Item 1 under "Waiting on Yuri" above is done.

## Open decisions (Yuri)

1. **protocol-v2.** Proposal: ERA5 truth, AIFS forecast weather, Vanilla with trend as
   the named primary baseline, Chronos-2 with temperature as challenger. Because we have
   already seen this comparison on DOM and JC, the recommended primary is on **new PJM
   zones** chosen by a stated rule before any model runs on them, with DOM and JC as
   development results and a **prospective weekly panel** (forecast before the week
   happens, read at fixed checkpoints such as 13, 26, 52 weeks) alongside. Not decided.
   A draft is in `protocol-v2-draft.yaml`. Decided on Nov 13: calendar is a known-future
   covariate beside humidity, solar and wind, as secondary rows (decisions 30, 31); the
   prospective panel starts with v2 (decision 32); primary zones AEP and AE (decision 33,
   `notes/zone_selection.md`); humidity, solar and wind wait for v2.x (decision 34). Still
   open: nothing for Yuri; to build before the tag: weighted zone mean, data pulls for AEP
   and AE, the calendar rows, gate runs. The panel runs on GitHub Actions (decision 35;
   `notes/prospective_panel_plan.md`, a plan, not built); weather points are ERA5 grid
   cells with PJM's weights (decisions 36, 37). Nothing has been run under it.
2. **TabPFN attribution.** Its licence asks for "Built with PriorLabs-TabPFN" where
   results are published. Needed on the dashboard if that row is shown.
3. **Blogs and newsletters for the scan.** A verified list is in
   `notes/blog_newsletter_sources.md`. Substack and Medium discourage AI crawlers in
   `robots.txt`; GitHub's Atom feeds are discouraged too (its API is the alternative).
   Yuri said he may explore feeds during the hackathon.
4. **Framework to explore.** Research recommends Nixtla first (MSTL, NHITS with future
   temperature), Darts second (`notes/framework_choice.md`). Needs its own environment.
5. **More weather models.** Google WeatherNext 2 needs a data request form with a wait
   of 5 to 7 business days (Yuri's step). GraphCast and FourCastNet forecasts are in a
   public NOAA bucket and could be tried now (`notes/weathernext_nvidia.md`).

## Saturday (hackathon)

- You.com provider for `/scan`, `/judge`, `/run-candidate`, and the comparison with the
  Claude-based runs already stored under `candidates/claude`, `scorecards/claude`,
  `evidence/claude`. No You.com code exists yet, by rule.
- Suggested pitch: the first baseline made the model look 27% better; the search for
  the field's standards closed most of that gap; better weather closes the rest.

## Leftovers

- `dashboard/story.html` is out of date (no Vanilla, weather or wording fixes).
- Figure improvements not yet done: per-week paired difference chart, lead-time curves
  for more pairs, SVG export (`notes/figure_presentation.md`).
- A station-observation check would show whether ERA5 as truth flatters AIFS.
- Yuri's steps: blind labels in `eval/label_sheet.md`; Langfuse Claude Code plugin;
  true Wi-Fi-off check of the dashboard; read the README prior-work disclosure.
- `README.md` status section predates protocol-v1.1 to v1.3.

## How work was split today

Build tasks were delegated to Opus 5.5 agents and research to the session model, to
save the session's usage limit. Each agent was told its file boundaries and to commit
only its own paths.

## Research notes written today

`notes/blog_newsletter_sources.md`, `notes/model_families.md`,
`notes/weather_skill_sensitivity.md`, `notes/figure_presentation.md`,
`notes/framework_choice.md`, `notes/weathernext_nvidia.md`, `notes/method_facts.md`,
`notes/hong2014_gefcom2012.md`.

## New model rows (protocol-v1.3, secondary)

Tagged `protocol-v1.3`; registers two rows under six weather settings (the v1 pair and
the four v1.2 sources). Results in `results/models_v13/` and the section
"Competition-grade LightGBM (protocol-v1.3, secondary)" of `results/README.md`.

- **`lightgbm_competition`: scored once.** Untuned LightGBM built like the BigDEAL 2022
  entry (91 calendar and temperature features, detrended log target, two years of
  history, no load input). Lower error than Chronos-2 with temperature in all 12
  zone-and-setting cells (1 to 6% with forecast weather, 8 to 19% with actual weather),
  but only one cell clears the 10% bar (a practical tie); the rest are inconclusive.
  Against the frozen lag regression: 0.57 to 0.78, beyond the bar everywhere. Against
  Vanilla with trend: 0.84 to 1.00. Forecast weather, v1 setting: DOM 715 MW (Chronos-2
  734, Vanilla with trend 776), JC 204 MW (218, 219).
- **`tabpfn_ts_v2_temperature`: registered, NOT scored.** About 50 hours on CPU for all
  six settings (624 windows at about 5 minutes). The run saves each finished cutoff and
  resumes after an interruption. Commands:

  ```
  git switch --detach protocol-v1.3
  uv run --project models_ff python models_ff/tabpfn_ts_v2.py scored   # rerun the same line to resume
  git switch main
  uv run --project core python -m harness.v13 score scored
  ```

  Then commit `results/models_v13/forecasts/tabpfn_ts_v2_temperature.parquet` and the
  rescored files. CPU-only is part of the registered definition; using the Mac GPU would
  need a new protocol version.
- The dashboard does not show the v1.3 rows yet.
- Open: whether a tuned LightGBM is worth a later protocol version.
