# Agent runtime, scheduling and deployment: a suggestion

Written Sat Nov 14, 2026, from a web research pass done in a Claude chat session
(outside this repo). **This is a suggestion, not a decision.** Nothing here is in
`DECISIONS.md`, nothing was installed, and no code or protocol file was changed.

Evidence label: every price, limit, date and product status below is **(research
report)**: taken from that pass, which read vendor docs and pricing pages but also
secondary trackers. None of it was re-checked from this repo. Under hard rule 7, treat
each figure as unverified until checked against the live page or the installed CLI.
The items most likely to be wrong are listed under "Check before relying on it".

## The question

Which framework should run the agents; how should runs that start interactive and
become weekly and unattended be scheduled; and where should they run once they leave
the laptop. Constraints Yuri set while planning the research:

| Topic | Constraint |
|---|---|
| Model | Claude now; be able to move to other models later |
| Compute | Mostly CPU, with short GPU bursts (minutes to about an hour) |
| Autonomy | Each unattended run ends in a pull request; nothing merges without review |
| Budget | Under about $50 a month all-in at a weekly cadence |
| State | Files in Git to start, large artifacts in object storage; a database later |
| Deployment | No servers; scheduled from GitHub |

## Suggested stack

| Layer | Suggestion | Runner-up | Why the runner-up is second |
|---|---|---|---|
| Agent runtime | Keep what exists: `claude -p` plus the skills, driven by `tools/pipeline.py` and `tools/run_skill.py`. Move to the Claude Agent SDK (Python) only when typed results or branching are needed | OpenHands agent SDK (MIT, any model) | Same class of tool, but the skills would have to be ported. It is the exit plan if Claude is dropped |
| Scheduler | GitHub Actions `schedule` plus `workflow_dispatch` | Claude Code cloud scheduled tasks | Subscription usage only, research preview, fresh clone, no GPU. Fine for a scan, weak for evaluation |
| Where it runs | GitHub-hosted Ubuntu runner; the output is a pull request | The whole pipeline on Modal (cron and functions) | Loses the native GitHub token and PR path. Better once runs regularly pass 2 to 3 hours |
| GPU bursts | Modal: billed per second, monthly free credit on the starter plan | Google Cloud Run jobs with an L4 | One-hour cap per GPU task, CPU and memory minimums, more setup, no recurring credit |
| State | As now: JSONL ledgers, scorecards, `results/`, `runs/` in Git. Large artifacts in Cloudflare R2 or S3, referenced by hash | A DuckDB file, later MotherDuck or Neon free tiers | Not needed until there are hundreds of runs to query or more than one writer |

Why not LangGraph, Pydantic AI, CrewAI, the OpenAI Agents SDK, Google ADK and
similar: they supply an agent loop and leave the coding harness (file edits, shell,
test loops) to be built. The scarce part of this project is the coding harness, and
one already works. AutoGen is in maintenance mode; Microsoft Agent Framework replaced
it in 2026.

## Portability: keep the logic portable, not the runtime

The repo is already most of the way there (decision 5; `.claude/skills/providers.md`).

1. Prompts and skills stay in Markdown. The harness, ledgers, receipts and PR creation
   stay in plain Python. The search provider stays behind the provider switch. The
   agent runtime is then a replaceable "coding worker".
2. First escape hatch: the same CLI can be pointed at another endpoint with
   `ANTHROPIC_BASE_URL` (OpenRouter and LiteLLM both document this; Bedrock and
   Vertex are supported directly). Tool-call reliability on non-Claude models is
   untested and the vendors themselves warn about it.
3. Only if Claude is dropped entirely: swap the coding worker for OpenHands. The outer
   pipeline does not change.

## Scheduling

**On the laptop.** Use a launchd LaunchAgent, not cron: launchd runs a missed job when
the Mac wakes, cron skips it. Wrap the command in `caffeinate -i`. Authenticate with a
token from `claude setup-token` and keep `ANTHROPIC_API_KEY` unset in that
environment, because in `-p` mode an API key in the environment takes precedence.

**In the cloud.** One weekly workflow, split so that no job holds more than it needs:

| Job | Does | Holds |
|---|---|---|
| agent | scan, judge, write the candidate adapter | `contents: read`, the model key, the search key |
| evaluate | runs the harness; sends GPU work to Modal | the Modal token; no model key |
| pull request | commits ledgers, scorecards, receipt; opens the PR | `contents: write`, `pull-requests: write` |

Set `timeout-minutes`, a `concurrency` group, an odd cron minute, and branch
protection on `main`. A plain step that installs the CLI and calls `tools/pipeline.py`
is simpler than the official `anthropics/claude-code-action`; that action is more
useful for `@claude` follow-ups on the PR itself.

Known limits of GitHub's scheduler: runs can be delayed or dropped under load,
schedules fire only from the default branch, and scheduled workflows in a public repo
are disabled after 60 days without activity. Add a heartbeat ping at the end of the
run that alerts when none arrives for 8 days.

One conflict with current behaviour: `tools/pipeline.py` deliberately refuses to start
model runs headless (`NO_MODEL_RUNS`). The split above keeps that rule: the agent job
still never runs a model; the evaluate job does, with no LLM in it.

**Interactive first, unattended later.** The skills are the agent definitions in both
modes: `/judge <id>` in a session now, `claude -p "/judge <id>"` later. In unattended
runs, open questions go into the PR description, and the review comment is the reply.
No pause-and-resume machinery is needed.

## Phases

| Phase | Changes | Stays |
|---|---|---|
| 0: today | Manual sessions plus `tools/pipeline.py` by hand | — |
| 1: laptop, scheduled | launchd job; per-skill tool allowlists and turn caps recorded in `runs/*.meta.json` | skills, harness, ledgers |
| 2: GitHub Actions | the three-job workflow; a capped API key; Modal deployment; object storage; heartbeat | `tools/pipeline.py`, skills, ledger format, local interactive use |
| 3: optional | DuckDB, then a hosted database; an experiment tracker; other models through a gateway; an orchestrator only if candidates run in parallel | PR as the review queue, frozen protocol |

Do not build yet: an orchestrator (Dagster, Prefect, Temporal and similar are overkill
for one weekly linear pipeline), a database, or a multi-framework abstraction.

## Cost at a weekly cadence (about 4.3 runs a month)

Modelled, not measured. `runs/*.meta.json` already records `total_cost_usd`; a few
real pipeline runs will replace this table.

| Item | Per month |
|---|---|
| Mid-tier model for judging and coding, with prompt caching | about $17 |
| Small model for triage | under $1 |
| You.com search beyond the free daily quota | $0 to $3 |
| Modal GPU, one run of about 40 minutes a week | $2 to $7, inside the free credit |
| GitHub Actions, private repo, about 60 minutes a week | $0, inside the included minutes |
| Object storage | under $1 |
| **Total** | **about $18 to $28** |

Levers: turn and budget caps per step, a stop after N failed test cycles, stable
prompts first so caching hits, the small model for triage, the Batch API for bulk
judging outside the agent loop. The budget breaks if runs grow several-fold in tokens,
if the largest model becomes the default, or if fine-tuning needs many GPU hours.

## Risks and guardrails

| Risk | Guardrail |
|---|---|
| Runaway spend | Caps at four levels: provider spend limit, per-step turn or budget cap, job timeout, Modal budget. Write the run's cost in the PR |
| Running generated code | Ephemeral runners or Modal sandboxes only. The agent job has no write token and no cloud credentials. Candidate code runs in a separate step. New dependencies are reviewed in the PR |
| Prompt injection from fetched pages | Scan and judge get no shell and no edit tools and emit schema-validated JSON (already the case for scorecards). The coding step sees the scorecard, not raw pages. Fetch from an allowlist of domains |
| Leaderboard overfitting | Already the repo's strongest area: frozen protocol, harness-owned cutoffs, gate then score once. Add a CI check that fails if an agent PR touches `harness/`, `protocol*.yaml` or `data/`, and report attempts per candidate. A 2026 study of coding agents in an auto-research loop found they memorised evaluation rows until a held-out set was added (arXiv 2607.18064) |
| Results that cannot be reproduced | Pinned environments, weight revisions (rule 13), data hashes (rule 6), the exact command in the run's meta file, the GPU type on the leaderboard row |
| Schedule fails silently | Heartbeat, failure notification, `workflow_dispatch` for reruns |
| Subscription terms change | Use the subscription on the laptop only; the cloud run uses an API key |

## Prior art

- Karpathy's `autoresearch` (2026): one editable file, a frozen evaluator, an
  append-only results log. Reuse the pattern; it matches this harness.
- AIDE (WecoAI, MIT): tree search over code drafts toward a metric. Possible inner
  loop for tuning one candidate. It would need the gate-origin rule enforced around it.
- OpenHands: the model-agnostic coding worker named above.
- Sakana's AI Scientist and the MLE-bench agents: heavier than needed; useful for
  ideas on novelty checks and automated review.

No existing project scans the literature, implements into a private harness and opens
a PR end to end.

## Where this touches the repo's rules

- LinkedIn stays out (rule 10, decisions 21 and 25). The research brief mentioned it
  as a source; that part is not carried over.
- Scheduled runs commit URLs and paraphrased claims only (rule 9).
- Moving runs to a GPU changes the "Mac laptop, default to CPU" environment line. A row
  scored on a GPU should say so, after one window is shown to match CPU output, as the
  MPS rule already requires.
- Unattended scoring must still respect "gate, tag, then score once" (rule 12): a new
  candidate is a secondary row under a protocol addendum, not an edit to a tagged one.

## Check before relying on it

- Model prices per million tokens, and whether higher subscription tiers now include
  monthly API credits usable by `claude -p`.
- Whether a `claude setup-token` token works inside GitHub Actions (an open issue
  reports failures), and the exact name of the per-run budget flag in the installed CLI.
- That `--bare` mode ignores the subscription token and needs an API key.
- You.com: the free daily quota and the per-call price; the signup credit is reported
  inconsistently.
- Modal: the size of the monthly credit and GPU hourly rates.
- GitHub Actions: included minutes for private repos and the per-job time limit.
- Cloud scheduled tasks and Managed Agents: both were preview or beta; limits and
  pricing may have moved.
- Free-tier limits of MotherDuck, Neon, Turso and Weights & Biases.

## Sources to start from

- Claude Code headless mode: https://code.claude.com/docs/en/headless
- Claude Code authentication: https://code.claude.com/docs/en/authentication
- Claude Code in GitHub Actions: https://code.claude.com/docs/en/github-actions
- Claude Code legal and compliance (subscription vs API key): https://code.claude.com/docs/en/legal-and-compliance
- Cloud scheduled tasks: https://code.claude.com/docs/en/routines
- Claude API pricing: https://platform.claude.com/docs/en/about-claude/pricing
- GitHub Actions schedule event: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- OpenRouter with Claude Code: https://openrouter.ai/docs/cookbook/coding-agents/claude-code-integration
- LiteLLM with the Agent SDK: https://docs.litellm.ai/docs/tutorials/claude_agent_sdk
- You.com pricing: https://you.com/pricing
- Cloud Run pricing: https://cloud.google.com/run/pricing
- MotherDuck pricing: https://motherduck.com/product/pricing/
- Neon free plan: https://neon.com/faqs/free-plan-limits-and-quotas
- Turso pricing: https://turso.tech/pricing
- AIDE: https://github.com/wecoai/aideml
- OpenHands agent SDK paper: https://arxiv.org/abs/2511.03690
