# Rebaseline plan (post-hackathon)

## Context

The hackathon left a working pipeline (scan, judge, run-candidate) that has only been
run by hand. It has no human review, no link from a verdict back to the run that made
it, no memory of what earlier scans found, and a baseline that was already replaced
once and is still untuned. Before weekly runs start, the project needs a settled
baseline, a place for Yuri's reviews, traceable runs, a registry of known work, and a
scheduled run that ends in a pull request. Later it splits into a public week-ahead
benchmark and a private long-term (1-6 month) forecasting project.

What the exploration found:

- `protocol-v2` (frozen Nov 14; scored zones AEP, AE; development zones DOM, JC) already
  made `vanilla_benchmark_trend` (Tao Hong's GEFCom Vanilla regression) the primary
  baseline. Every baseline row is untuned. Never run: Vanilla with recency terms, a GAM,
  a tuned LightGBM, MSTL or exponential smoothing. On AEP the untuned
  `lightgbm_competition` already beats Vanilla by 11%.
- None of the 25 judged references compares against Vanilla. They use another
  foundation model (17), seasonal naive (11), the operator's forecast (6), LightGBM (5),
  linear or lag regression (4), XGBoost (4).
- PJM publishes no archive of week-ahead zonal forecasts (`load_frcstd_7_day` is
  current-only; `load_frcstd_hist` and EIA-930 are about day-ahead). PJM's own forecast
  cannot be scored on past weeks; it can only be captured from now on.
- `eval/items.yaml` `label_yuri` is empty for all 11 items. No scorecard, evidence row
  or receipt carries a run id. The same paper got up to three different `candidate_id`s.
  The scan window is a rolling 120 days with no cross-week de-duplication.
- `tools/pipeline.py` and `tools/run_skill.py` already run the skills headless, but
  `run_skill.py` line 108 strips every `CLAUDE*` variable from the child, including the
  subscription token, so it cannot authenticate on a GitHub runner as written.
- The repo is public (free Actions minutes; artifacts and logs are world-readable),
  has no licence, and `spec.yaml` still names `lag_regression_temperature` as
  `baseline_to_beat`.

## Decisions (Yuri, Nov 15)

| # | Decision |
|---|---|
| 1 | Scheduled run does scan + judge only. `run-candidate` stays manual until the baseline is settled. |
| 2 | A stronger baseline becomes primary under a new `protocol-v3`; v1 and v2 results stay as history. |
| 3 | Primary = lowest validation error among a tuned shortlist. The report also names the most widely used baseline and what a utility would run; each is a secondary row if it differs. |
| 4 | Tuning and the choice of winner use only DOM, JC and data before the first scored week. The winner is scored once on the existing AEP/AE weeks. |
| 5 | Baseline research is staged: survey with logged queries, shortlist and tuning protocol, Yuri signs off, then implement and tune. |
| 6 | Runs are billed to the Claude subscription. |
| 7 | Both providers (Claude search, You.com) scan and judge every week. The provider layer stays swappable (You.com may be replaced). |
| 8 | Judge every new candidate with both providers, capped at 60 candidates a week by fit (up to 120 judge runs). Overflow is "seen, not judged" and goes first next week. |
| 9 | Each run ends in one pull request. A check fails the PR if it touches anything outside the agent's output paths. |
| 10 | Reviews are CSV files in the repo, one per stage. A judge review = verdict, corrected label, reason, and four yes/no checks (claim, sources, relevance, runnable class). |
| 11 | Telemetry: run id on every scorecard, evidence row and review row; full transcripts archived in a private repo; Langfuse Cloud free tier as a viewer. |
| 12 | Registry and review verdicts are public. Private notes live in the private repo under the same keys. |
| 13 | First run waits for the registry and run ids, then is started by hand in GitHub Actions. The weekly timer goes on after one clean run. |
| 14 | Private repo is created now (archive and notes only). The split happens after `protocol-v3` is scored. Long-term work starts with PJM. |
| 15 | `AGENTS.md` and `.agents/` (broken Codex port) are fixed and committed. |

First commit: record these as numbered entries in `DECISIONS.md`.

Usage warning: 2 scans plus up to 120 judges is roughly $300-400 of API-equivalent
usage a week against subscription limits. A usage limit mid-run is expected at times;
the run must degrade to a partial PR (see workstream 4).

## Workstream 1: registry and cross-week de-duplication (before first run)

- `tools/keys.py`: move `norm_url` and `norm_title` out of `tools/merge_candidates.py`
  (lines 37-44, re-imported there). Add `stable_key(urls, title)`, first match wins:
  `arxiv:<id>`, `doi:<doi>`, `zenodo:<record>`, `hf:<org>/<repo>`, `gh:<owner>/<repo>`,
  `pypi:<name>`, else `url:<normalised>`. LinkedIn URLs are never a key.
- `registry/entries.jsonl` (public, sorted by key) with `schemas/registry.schema.json`.
  Fields: `key`, `aliases`, `kind` (paper, model, framework, benchmark, method, post),
  `title`, `primary_url`, `other_urls`, `published_at`, `first_seen`, `last_seen`,
  `candidate_ids` (every slug used), `canonical_candidate_id`, `status`
  (`implemented_scored`, `judged`, `seen_not_judged`, `rejected`, `reference`),
  `status_detail` (labels per provider, scorecard paths, leaderboard rows), `queue`
  (deferred since, reason: cap, usage limit, failed), `relations`
  (`improves_on`, `new_version_of`, `extends`, `evaluates`, `replicates`,
  `compares_against`; each with target key, short paraphrased claim, evidence id),
  `notes_public`.
- `tools/registry.py`:
  - `seed` (idempotent) from the 31 scorecards, all `candidates/*/scan_*.jsonl`,
    `eval/items.yaml` primary sources, `models/pins.json`, `spec.yaml` runnable models,
    `MODELS` / `V2_MODELS` in `harness/baselines.py`, `results/leaderboard.csv`, and a
    hand-written `registry/seed_manual.yaml` for the method tables in
    `notes/standard_methods.md`, `notes/model_families.md` and `REFERENCE.md`
    (lines 168-214), each row citing its file and line.
  - `ingest <merged scan> --cap 60`: marks rows new or known and writes
    `candidates/merged/queue_<date>.jsonl` (carried-over items first, then new by rank).
  - `check <url>`, `related <key>`, `relate`, `sync`.
- Monday: de-duplication is done in code after the scan; the skills are unchanged.
  Week 2: `/scan` calls `registry.py check` before spending its fetch budget, and
  `/judge` calls `related` and records `improves_on` when a claim names a known work.
- Replace "newest file by mtime" in `tools/pipeline.py` (lines 96-101) and
  `tools/merge_candidates.py` (lines 47-51) with the date in the filename.

## Workstream 2: run ids and telemetry

Before the first run:

- `tools/run_skill.py`: `child_env` keeps `CLAUDE_CODE_OAUTH_TOKEN`, drops
  `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` (either would silently switch to
  metered billing), strips other `CLAUDE*` as now. Compute `run_id` before the child
  starts and pass it as `RECEIPTS_RUN_ID`. Record the CLI version in the meta file.
  Narrow the allowed `Bash(uv run:*)` to the exact tool scripts (`ledger.py`,
  `feeds.py`, `validate_scorecard.py`, `registry.py`), since the agent reads web pages.
- `tools/ledger.py` `add` writes `run_id` (or `interactive`). Old rows are left alone.
- `schemas/scorecard.schema.json`: optional root `provenance {run_id, session_id,
  registry_key, cli_version}`; the 31 existing cards stay valid. The wrapper stamps it
  after a successful judge and re-validates. Backfill where `judge_runs()` in
  `tools/compare_providers.py` (line 39) can map a run. Receipts also record the
  leaderboard model name and protocol version (missing today).
- Private repo: `transcripts/<yyyy>/<run_id>.jsonl.gz` and `notes/<key>.md`.

During the week:

- `tools/trace.py <candidate id or registry key>`: finds the runs, reads the transcript
  locally or from the archive checkout, prints search queries, pages fetched, ledger
  adds and the final reasoning. Reuses `run_skill.parse` and `stream_counts` in
  `dashboard/build_data.py` (line 49).
- `tools/langfuse_upload.py`: uploads each transcript to Langfuse Cloud after the run
  (one trace per run; run id, registry key, provider and skill as metadata), with a
  truncation option for page text. Chosen over Claude Code's OpenTelemetry export
  (beta, and blocked by the env stripping) and the Stop hook (fails silently,
  truncates). Free tier: 50k units a month, 30 days of data; the private archive is
  the record.

## Workstream 3: review sheets (this week; may slip to Tuesday)

- `reviews/scan.csv`, keyed by registry key: title, url, published_at, found_by, rank,
  first-seen run id, status; then `human_relevant`, `human_duplicate_of`, reason.
- `reviews/judge.csv`, keyed by registry key + provider: candidate id, run id,
  scorecard path and hash, label, runnable class, evidence strength, relevance scores,
  `stale`; then `verdict` (agree, disagree, unsure), `corrected_label`, `reason`,
  `claim_ok`, `sources_ok`, `relevance_ok`, `runnable_ok`.
- `reviews/receipt.csv`, keyed by registry key + provider: run id, protocol, verdict,
  ratios; then `verdict_ok`, `wording_ok`, reason.
- All sheets end with `reviewed_by`, `reviewed_at`, `note_public`.
- `tools/reviews.py sync` rewrites machine columns only, appends new rows, never
  deletes, and sets `stale=yes` if a scorecard changes after review. The same command
  fills the backlog (96 candidates, 31 scorecards) and runs in every weekly run.
  `tools/reviews.py check` validates values; `agreement` reports judge vs. human.
- `eval/items.yaml` `label_yuri` stays the blind ground truth. Fill it from
  `eval/label_sheet.md` before opening the judge sheet, which shows the agent's label.
  `/judge` gains one line: never read `reviews/`.
- Dashboard: new `dashboard/build_reviews.py` reads only committed files and writes
  `dashboard/reviews.js` (the existing `build_data.py` needs git-ignored
  `data/processed`, so CI cannot run it). `dashboard/index.html` gets a "Review" tab
  (scorecard, sources, agent label, review status and verdict) and a "Registry" view.

## Workstream 4: scheduled run (first run by hand, then weekly)

- `tools/weekly.py` (orchestrator; `tools/pipeline.py` stays for manual use):
  1. Scan with both providers; one failing does not stop the other.
  2. Merge; `registry.py ingest --cap 60`.
  3. Judge the queue with both providers at `--parallel 2`; stamp provenance; validate;
     remove the scorecard of a failed judge.
  4. `reviews.py sync`, `build_reviews.py`.
  5. Write `runs/weekly_<id>.json` and `.md` (the PR body).
  - Circuit breaker: after three consecutive judge failures or a rate-limit error,
    stop judging, mark the rest `seen_not_judged (usage_limit)` and still open the PR.
- `.github/workflows/weekly.yml`, `timeout-minutes`, concurrency group, pinned CLI
  version, inputs `cap`, `providers`, `dry_run`:

  | Job | Permissions | Secrets | Does |
  |---|---|---|---|
  | agent | `contents: read` | `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`), `YDC_API_KEY` | runs `weekly.py`; uploads public output as an artifact and transcripts as an encrypted artifact (one-day retention) |
  | archive | none | deploy key for the private repo, artifact key, Langfuse keys | decrypts, pushes transcripts to the private repo, uploads to Langfuse; runs even if the agent job failed |
  | pull-request | `contents: write`, `pull-requests: write` | none | applies output on `agent/weekly-<date>`, runs the guard, opens the PR |

- `tools/guard_paths.py`, an allowlist: `candidates/`, `evidence/`, `scorecards/`,
  `registry/`, `reviews/`, `runs/*.json`, `runs/*.md`, `dashboard/reviews.js`.
  It runs inside the weekly workflow and in `.github/workflows/guard.yml` for
  `agent/*` branches only (PRs opened by the workflow token may not trigger other
  workflows; human PRs for the baseline work are not blocked).
- PR body: run ids, scan statistics per provider, registry delta (new, known, judged,
  deferred and why), judged table with labels and provider agreement, failures, cost,
  archive commit, Langfuse session ids, reviewer checklist.
- Heartbeat: a ping at the end of a successful run to a dead-man service with an
  eight-day grace (service to choose); GitHub can drop scheduled runs and disables them
  in public repos after 60 days without activity.
- Trigger: `workflow_dispatch` only at first (`cap=3`, then `cap=60`); add
  `cron: "17 9 * * 1"` after one clean run.
- Deployment: GitHub Actions on the public repo is the free cloud option. Claude
  scheduled routines were checked and rejected for this job (no per-run transcripts or
  cost records, You.com setup conflicts with attaching a second repo, PR creation
  restricted).
- Yuri's setup steps: create the private repo; `claude setup-token`; add the secrets;
  add a write deploy key; turn on "Allow GitHub Actions to create and approve pull
  requests"; create the Langfuse Cloud project.

## Workstream 5: baseline research (starts now, in parallel)

Stage 1, survey. Deliverable `notes/baseline_research_v3.md` plus a "Round 3" section
in `BASELINES.md`; every query and page logged with `tools/ledger.py` under candidate
`baseline-survey-2026-11`; each method becomes a registry entry of kind `method`.

- What our judged references and candidates compare against (tally redone from the
  scorecards with file references).
- What the literature and competitions use: GEFCom 2012/2014/2017, BigDEAL 2022, the
  Vanilla and recency papers, GAM practice, Nixtla's PJM tutorial, recent
  foundation-model load papers.
- What ISOs and utilities run.
- Three named answers: strongest candidates, most widely used, practitioner's choice.
- Shortlist (expected): Vanilla with trend (incumbent, untuned), Vanilla with recency
  (`REFERENCE.md` lines 67-92), Vanilla with recency and holidays, a GAM, tuned
  LightGBM on the `lightgbm_competition` features, MSTL or double-seasonal smoothing.
  PJM's own forecast is listed as not scoreable; start capturing `load_frcstd_7_day`
  in the private repo for later.
- Tuning protocol `tuning/tuning-v3.yaml`, committed before any tuning run: zones DOM
  and JC; an explicit list of weekly origins before the first scored week (alternate
  origins tune hyperparameters, the others pick the winner); the same budget for every
  method (at most 50 configurations, seeded); metric = window MAE normalised per zone;
  tie rule; weather = archived forecasts if they cover the tuning period, otherwise
  reanalysis, stated plainly.
- Yuri signs off on the survey, shortlist and tuning protocol.

Stage 2, after sign-off:

- `harness/tune.py` refuses any scored origin and any zone outside
  `V2_DEVELOPMENT_ZONES` (`harness/data.py` line 156). New adapters in
  `harness/baselines.py` with the existing `forecast(hist, temp, cutoff)` signature,
  registered in a `V3_MODELS` dict; `lightgbm_competition` takes parameters, with a
  test that its default output is unchanged. `harness/v3.py` follows `harness/v2.py`.
- Libraries: statsmodels `GLMGam` (already in `core/`); `uv add --project core
  statsforecast` if MSTL is shortlisted. Verify each against the installed package.
- `protocol-v3.yaml` holds the tuned values as literals and the secondary rows (old
  primary, "most used", "practitioner"). Outcome sentences are written before scoring
  and say the AEP/AE weeks were already seen with untuned models. Gate run, Yuri's
  review, tag `protocol-v3`, score once, dated line in `DEVIATIONS.md`.
- Spec: keep the current file as `spec-v1.yaml`; `spec.yaml` becomes `spec-v2` with the
  new `baseline_to_beat`. Existing scorecards stay `spec-v1`. Then `run-candidate`
  goes back on. `CLAUDE.md` (benchmark line, rule 11, baseline name) needs Yuri's edit.

## Workstream 6: split and housekeeping

- Now: private repo for transcripts, private notes and the PJM forecast capture.
- `notes/split_plan.md`: public (harness, protocols, results, registry, verdicts,
  dashboard) vs. private (transcripts, notes, long-horizon work); the places
  hard-coded to 168 h (`harness/baselines.py`, `models/chronos2.py`, `harness/data.py`,
  `harness/score.py`, `fetch.py`) and to PJM (`fetch.py`, zone tuples in
  `harness/data.py`); what a 1-6 month PJM project needs that does not exist (monthly
  energy and peak targets, climate normals or scenarios, longer history).
- Before the split: add a licence; make `harness/` installable (`core/pyproject.toml`
  has `package = false` today).
- `AGENTS.md` becomes a short file pointing at `CLAUDE.md` and the shared skill files
  in `.claude/skills/` (no second copy of the skills); check Codex resolves them; commit.

## Order of work

1. Record decisions. Yuri: private repo, token, secrets, deploy key, PR setting.
2. `run_skill.py` auth fix, run id, narrowed allowlist; ledger and provenance stamping.
3. `keys.py`, `registry.py`, seed commit.
4. `weekly.py`, guard, filename-date fix, `weekly.yml`.
5. First run by hand with `cap=3`; check the PR; then `cap=60`.
6. Review sheets and backlog (may slip to Tuesday); then Langfuse upload, `trace.py`,
   Review tab, cron on.
7. Baseline survey runs alongside from step 1; sign-off; stage 2; `protocol-v3`; spec-v2.
8. Registry-aware `/scan` and `/judge` for the second weekly run. Split after v3.

## Verification

- Registry: `tests/test_keys.py` (the three slugs of one arXiv URL give one key);
  seeding twice gives no diff; ingesting the Nov 14 merged scan gives zero new entries;
  a synthetic 70-row scan queues 60 and defers 10, which come first next time.
- Run ids: with only the OAuth token in the environment the child authenticates; with
  an API key set it is dropped; a new ledger row and scorecard carry the run id;
  `tools/trace.py <candidate>` matches the transcript; the Langfuse session shows the
  same tool calls.
- Reviews: `tests/test_reviews.py` (human cells survive a sync; a changed scorecard
  goes stale); the backlog gives 31 judge rows; the Review tab opens from a fresh clone.
- Workflow: `weekly.py --cap 2` locally, then a dispatch with `cap=3`; the PR touches
  only allowed paths; a test branch editing `harness/` fails the guard; a simulated
  rate limit yields a partial PR and deferred entries; transcripts are in the private
  repo and nothing readable is in public artifacts or logs.
- Baseline: the tuner refuses AEP and scored origins; default LightGBM output is
  identical on two gate windows; the same seed gives the same winner; the scored run
  is refused before the tag; `uv run --project core pytest tests -q` and ruff pass.
