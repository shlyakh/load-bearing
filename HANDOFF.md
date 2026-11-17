# Handoff: where things stand

## RESUME HERE: the rebaseline, paused Sun Nov 15, 2026 (evening)

Yuri switched to another project for a day or more. The first weekly run is no longer
tied to Monday Nov 16: it happens on the first day Yuri is back, and the weekly timer
is set from that day (Yuri, Nov 15). The sections below this one are the Nov 13 snapshot.

**Where everything is.** Branch `rebaseline`, 14 commits on top of `main` (this handoff included), working tree
clean, pushed to `origin/rebaseline` on Nov 16 as a backup. It is **not merged**, so
no workflow can run yet. Plan: `notes/rebaseline_plan.md`. Decisions:
`DECISIONS.md` 38 to 52. Setup steps: `notes/weekly_run_setup.md`.

**Built and tested** (116 tests pass; one real judge run confirmed the run ids):

| Piece | Where |
|---|---|
| Subscription login survives in headless runs; run id on ledger rows and scorecards | `tools/run_skill.py`, `tools/ledger.py`, `schemas/scorecard.schema.json` |
| Registry of 93 known works under stable keys; weekly queue with a cap | `tools/keys.py`, `tools/registry.py`, `registry/` |
| Weekly orchestrator (both providers, stops cleanly at a usage limit) | `tools/weekly.py` |
| Guard: an agent pull request may change only output paths | `tools/guard_paths.py`, `.github/workflows/guard.yml` |
| Weekly workflow, started by hand, no timer yet | `.github/workflows/weekly.yml` |
| Review sheets, backlog filled, Yuri's columns blank | `reviews/*.csv`, `tools/reviews.py` |
| "How was this verdict reached" | `tools/trace.py` |
| Dashboard Review tab and registry table | `dashboard/build_reviews.py`, `dashboard/reviews.js`, `dashboard/index.html` |
| Baseline survey, shortlist of six, tuning protocol draft (nothing tuned) | `notes/baseline_research_v3.md` |
| Notes for the later public/private split | `notes/split_plan.md` |

**Next steps, in order.**

1. Yuri: merge `rebaseline` into `main` (a workflow can only be started by
   hand once its file is on the default branch; the merge also redeploys the dashboard
   with the Review tab).
2. Yuri: the one-time setup in `notes/weekly_run_setup.md`: private archive repo,
   deploy key, `claude setup-token`, four secrets, the `ARCHIVE_REPO` variable, allow
   Actions to open pull requests.
3. Start "Weekly scan and judge" with `queue_only` ticked (free), then with `cap` = 3.
   Check the pull request, the private archive and the public artifacts as listed in
   the setup note. This is the first time the workflows run and the first test of the
   skills under the narrower CI shell.
4. If clean: run with `cap` = 60, then add the `schedule` block (written as a comment
   at the top of `weekly.yml`) for the weekday Yuri picks.
5. Yuri: sign off the baseline survey (section 5 of `notes/baseline_research_v3.md`).
   The main choices: tune on IFS forecasts for all 52 development weeks (AIFS covers
   only 32); list the 52 development Mondays 2024-09-30 to 2025-09-22 in `protocol-v3`
   (hard rule 12); one configuration for both zones; reuse the scored AEP/AE weeks or
   tie the primary to the prospective panel.
6. After sign-off, stage 2: contenders in `harness/baselines.py`, `harness/tune.py`
   that refuses scored origins and zones outside DOM and JC, gate, tag `protocol-v3`,
   score once, `spec-v2`, then `run-candidate` goes back on.
7. Yuri: start reviewing. Fill `label_yuri` in `eval/items.yaml` from
   `eval/label_sheet.md` first (the judge sheet is not blind), then `reviews/judge.csv`.

**Open questions for Yuri.**

- The first run queues the 36 hackathon candidates that were never judged; with both
  providers that is up to 72 judge runs. Exclude them, or let them be judged?
- `CLAUDE.md` still describes protocol-v1 in its benchmark line, rule 11 and the
  baseline name; it needs Yuri's edit once v3 lands.

**Not built yet.**

- `tools/langfuse_upload.py` (decision 48): needs Yuri's Langfuse Cloud project and
  keys. The archive job in `weekly.yml` has no Langfuse step yet.
- Registry-aware `/scan` and `/judge` (call `registry.py check` and `related`, record
  `improves_on`): planned for the second weekly run. Today de-duplication happens in
  code after the scan.
- The heartbeat service is not chosen (`HEARTBEAT_URL` is optional in the workflow).
- A licence, and `harness/` as an installable package (both before the split).

**Known limits.**

- Three older scorecards have no run record (`claude/item-02`, `claude/timestral`,
  `claude/tsfm-load-covariate-uncertainty`), so `trace.py` cannot replay them.
- `statsforecast` needs pandas below 3 and cannot go into `core/`; use statsmodels'
  MSTL if that contender stays on the shortlist.
- Not confirmed: the consumer terms on unattended use of a subscription token; whether
  GitHub starts `guard.yml` on a pull request opened by the workflow's own token (the
  guard also runs twice inside the weekly run); whether Codex resolves the linked
  skills in `.agents/skills` (Codex was not run).
- The survey's 32 search queries are in section 7 of the note; only the 29 pages are
  in the evidence ledger.
- The dashboard's tab row now wraps onto a second line.
- At the cap, a week is roughly $300 to $400 of API-equivalent usage against the
  subscription limits; most weeks after the first should be far smaller.

# Snapshot of Fri Nov 13, 2026, evening

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
- **Spend:** see the scan comparison line below. You.com credit
  left: 917 cents when checked late morning.
- **Scan comparison (early afternoon):** both providers scanned on the current
  `spec.yaml`; the You.com scan used one `site:` per query. Claude 44 candidates,
  You.com 53, 37 in common (table in `notes/youcom_usage_and_feedback.md`; snapshots
  in `comparisons/`). Spend after it: $86.34 of model cost; cap raised to $150 (Yuri).
- **Combined candidate list** (Yuri, Nov 14): `tools/merge_candidates.py` merges the
  latest scan of each provider into `candidates/merged/scan_<date>.jsonl` (60 claims
  today: 37 found by both, 16 only by You.com, 7 only by Claude). Judge from it with
  `tools/pipeline.py <provider> --candidates-from merged`. Run the merge after scans.
- **Judged from the combined list (afternoon):** 19 claims judged with You.com, 8 with
  receipts: 5 "partially", 3 "untestable" (the first GB study on Timestral, and the two
  TimesFM 3.0 claims: most scored weeks precede the weights).
- **TimesFM 3.0 with temperature added** (Yuri, Nov 14) as a flagged secondary row,
  `timesfm3_temperature`: gate first, scored once, 8 of 48 weeks after the weights,
  non-commercial weights (`DEVIATIONS.md`). Forecast weather against the temperature-only
  regression: DOM 0.70 (0.65 to 0.77), JC 0.76 (0.65 to 0.88). Spend $123.75; cap $250.
- **State at 14:10:** 25 claims judged with You.com, 11 with receipts (6 "partially", 5
  "untestable"); 6 judged with both providers, same label on all 6. Spend $147.09, cap
  $250. protocol-v2.1 (four Chronos-2 calendar-encoding rows) frozen, tagged and scored
  once: no encoding makes the calendar help (`results/README.md`, last section; panel on
  the dashboard's New zones tab). The two seed-list domain groups were removed from
  `spec.yaml`. Dashboard has a You.com tab; the tour has 11 steps including it.
  Narrated video: `tools/make_video.py --backend openai` writes
  `video/out/receipts_demo.mp4` (git-ignored); OpenAI key in `.env`.
- **Video chosen (Yuri, Nov 14, 15:05):** `video/out/receipts_demo.mp4`, 164 seconds,
  13 steps, OpenAI voice, recorded 15:02 (copy: `receipts_demo_final_164s.mp4`; both
  git-ignored, on the laptop only). `video/narration.json` holds exactly its text. The
  dashboard tour follows the same 13 steps. Dashboard also has You.com and Open Crawl
  tabs. Failed agent runs now exit nonzero and stop the pipeline
  (`tests/test_pipeline_failures.py`).
- **Repository renamed** to `load-bearing` (Yuri, Nov 14). Dashboard:
  https://shlyakh.github.io/load-bearing/ ; the old Pages address returns 404. The
  local folder is still `receipts`.
- **Dashboard "How it works"** is now a flow diagram: setup once, the weekly stages,
  the three agents with both providers, and scoring. `notes/demo_script.md` is the
  three-minute walkthrough.
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
