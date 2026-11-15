# Weekly run: setup and first run

What Yuri does once before the first scheduled run (decisions 43, 46, 48, 50), then how
to start it. The design is in `notes/rebaseline_plan.md`; the workflow is
`.github/workflows/weekly.yml`.

## One-time setup

1. **Private archive repo.** Create a private repository (for example
   `load-bearing-private`) with one commit (a README), so it can be cloned.
2. **Deploy key for the archive.** On the laptop:
   `ssh-keygen -t ed25519 -N "" -C weekly-archive -f /tmp/archive_key`.
   In the private repo: Settings, Deploy keys, Add deploy key, paste
   `/tmp/archive_key.pub`, tick "Allow write access". Keep `/tmp/archive_key` for step 4,
   then delete both files.
3. **Subscription token.** Run `claude setup-token` and copy the token it prints
   (valid for a year; it can only make model requests).
4. **Secrets** in the public repo (Settings, Secrets and variables, Actions, Secrets):

   | Name | Value |
   |---|---|
   | `CLAUDE_CODE_OAUTH_TOKEN` | the token from step 3 |
   | `YDC_API_KEY` | the You.com key (the same one as in `.env`) |
   | `ARCHIVE_DEPLOY_KEY` | the whole contents of `/tmp/archive_key` |
   | `ARCHIVE_ARTIFACT_KEY` | any long random string, e.g. from `openssl rand -hex 32` |
   | `HEARTBEAT_URL` | optional; a check URL from a dead-man service, 8-day grace |

   Do not add `ANTHROPIC_API_KEY`: it would take precedence over the subscription token.
5. **Variable** (same page, Variables tab): `ARCHIVE_REPO` = `owner/name` of the
   private repo.
6. **Let Actions open pull requests.** Settings, Actions, General, Workflow
   permissions: tick "Allow GitHub Actions to create and approve pull requests".
7. **Merge the `rebaseline` branch into `main`.** A workflow can only be started by hand
   once its file is on the default branch.

## First run

1. Actions, "Weekly scan and judge", Run workflow, with `queue_only` ticked. This costs
   nothing: it prints which candidates would be judged from the latest scans.
2. Run it again with `cap` = 3 and `queue_only` unticked. Expect two scans and up to six
   judge runs (three candidates, two providers), about 30 to 45 minutes, and one pull
   request from a branch named `agent/weekly-<date>-<n>`.
3. Check the pull request:
   - it changes only `candidates/`, `evidence/`, `scorecards/`, `registry/`, `reviews/`,
     `runs/`;
   - the "Guard agent pull requests" check ran on it (if GitHub did not start it for a
     pull request opened by the workflow, the same guard already ran inside the weekly
     run, twice);
   - the private repo has `transcripts/<year>/<run_id>.jsonl.gz` for each run;
   - the public run's artifacts hold only `public-output` and an encrypted file.
4. If that is clean, run with `cap` = 60, then add the `schedule` block that is written
   as a comment at the top of `weekly.yml`.

## What a run may cost

Two scans plus up to 120 judge runs is roughly $300 to $400 of API-equivalent usage a
week at the cap, drawn from the subscription's limits. After the first week only new
work is judged, so most weeks should be far smaller. When a limit is hit the run stops
starting judges, opens the pull request with what finished, and puts the rest first in
next week's queue.

## Not confirmed

- The consumer terms on unattended use of a subscription token were not read.
- On a CI runner the agent's shell is only what `tools/run_skill.py` allows (the tool
  scripts and a few read-only commands). The hackathon runs on the laptop also had the
  laptop's own settings, which allow more (for example `python3`). The `cap` = 3 run is
  the first test of the skills under the narrower shell; a judge that fails for that
  reason will say which command was denied in its transcript (`tools/trace.py`).
- Whether GitHub starts the guard workflow on a pull request opened with the workflow's
  own token.

## Reviewing

- `reviews/scan.csv`, `reviews/judge.csv`, `reviews/receipt.csv`: fill in the columns on
  the right; `uv run --project core python tools/reviews.py check` validates them and
  `... reviews.py agreement` summarises. Column meanings are at the top of
  `tools/reviews.py`.
- Fill `label_yuri` in `eval/items.yaml` from `eval/label_sheet.md` before opening
  `reviews/judge.csv`: the sheet shows the judge's label, so it is not blind.
- `uv run --project core python tools/trace.py <candidate id or registry key>` prints
  the searches, pages and reasoning behind a verdict.
- `uv run --project core python tools/registry.py check <url>` says whether a work is
  already known; `... registry.py stats` lists the registry by status.
