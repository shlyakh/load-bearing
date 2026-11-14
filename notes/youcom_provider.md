# The `youcom` search provider: how to turn it on

**Update, Nov 14, late morning:** the key is in `.env` and the provider has run live
(smoke test, nine judges started, one scan). What the live runs settled, what they
cost and what was changed is in `notes/youcom_usage_and_feedback.md`; of the open
points below, 1, 4, 5 and 6 are answered there, 2 partly (the balance check works), 3
and 7 are still open. The sections below are kept as written before the first call.

Wired on Sat Nov 14, 2026, before a key existed. No You.com call has been made yet.

## What is in place

- `tools/run_skill.py <skill> youcom ...` runs the skill headless against the hosted
  You.com MCP server, named `you-com`, at
  `https://api.you.com/mcp?tools=you-search,you-contents,you-research` (the `?tools=`
  part switches on the research tool, which is off by default).
- The MCP config is passed inline (`--mcp-config '<json>'`) with the header
  `Authorization: Bearer ${YDC_API_KEY}`. The CLI expands the variable from the child
  process's environment, so the key is in no file, no command-line argument, no
  `runs/*.meta.json` and no saved stream. Nothing is added to `~/.claude.json`
  (unlike `claude mcp add`).
- Allowed: the common tools plus `mcp__you-com__you-search`, `mcp__you-com__you-contents`,
  `mcp__you-com__you-research`. Denied: `WebSearch`, `WebFetch` (the user settings
  pre-approve `WebSearch`, so allowing alone would not stop a fallback).
  `--strict-mcp-config` keeps every other MCP server, claude.ai connectors included,
  out of the run.
- The run refuses to start if `YDC_API_KEY` is missing from both the environment and
  `.env`. This matters: with the variable unset, the CLI still connects and sends an
  empty bearer token without an error.
- `runs/<id>.meta.json` records `provider_tools_allowed`, `provider_tools_denied`,
  `mcp_server` (name and URL), `mcp_servers` (status from the session's init line) and
  `search_tools_present` (the search tools the session actually had). A run whose
  `you-com` status is not `connected` prints a warning.
- How each skill calls the tools: `.claude/skills/providers.md`, section `youcom`.
- `tools/pipeline.py youcom --candidates-from claude` judges the candidates of the
  latest Claude scan, so both providers are compared on the same inputs.
- `tools/compare_providers.py` writes `results/provider_comparison.csv`.

Verified offline (CLI 2.1.323, a local mock MCP server, a fake key): the config shape,
the header reaching the server, the `?tools=` query reaching the server, the tool
names `mcp__you-com__you-*`, that `--strict-mcp-config` leaves only `you-com`, and
that the deny list removes WebSearch and WebFetch from the session.

## Turning it on

1. Add the key to `.env` (git-ignored; never paste it into a command line or a chat):
   `YDC_API_KEY=...`
2. Smoke test: one `you-contents` call on the Zenodo record, about $0.001 of You.com
   plus a few cents of model cost:
   `uv run --project core python tools/run_skill.py smoke youcom`
   Expect the record's title and date, and the three `mcp__you-com__` tool names. Then
   check the meta file: `mcp_servers` shows `you-com` `connected` and
   `search_tools_present` lists only the three You.com tools.
3. Judge the demo item:
   `uv run --project core python tools/run_skill.py judge youcom item-02`
   Output: `scorecards/youcom/item-02.json`, `evidence/youcom/item-02.jsonl`.
4. Judge the candidates Claude already judged:
   `uv run --project core python tools/pipeline.py youcom --candidates-from claude --only chronos2-covariate-grid-load gb-demand-weather-zero-shot-backtest pjm-cold-spell-calibration-benchmark tsfm-load-covariate-uncertainty`
   (or `--judge 5` for the next unjudged ones). A new You.com scan:
   `uv run --project core python tools/pipeline.py youcom --scan --judge 3`
5. Compare: `uv run --project core python tools/compare_providers.py`

## Untested, because no key was available

- Any call to the live server: authentication, the real tool list, the real argument
  names and result fields.
- Whether `you-research` is really present with `?tools=` on the live server.
- Whether the skills follow `providers.md` (exact-range `freshness`, `site:` per group,
  `exclude_domains`, research tier, citations from `sources`) in a real run.
- You.com charges: `total_cost_usd` in the meta files is the Claude client's model
  estimate only; You.com charges are not counted anywhere yet. `provider_tool_calls`
  in the comparison gives the call counts to price by hand (search $5 per 1k, contents
  $1 per 1k pages, research standard $0.05 a call).
- The smoke prompt and the `/judge` budget for You.com (2 research calls, 5 searches,
  10 pages) are first guesses.

## Open points the first live run should settle

From the "Not verified" list in `notes/hackathon_tools.md`:

1. The exact tool names as Claude Code shows them for the live server (the mock gave
   `mcp__you-com__you-search` etc.; the live server must report the same tool names
   `you-search`, `you-contents`, `you-research`). If they differ, change
   `YOUCOM_TOOLS` in `tools/run_skill.py` and the table in `providers.md`.
2. Whether Research is included in the hackathon credits, and how many credits there
   are. Ask at kickoff; the live check is `you-balance`, which this wiring does not
   request (add it to `YOUCOM_TOOLS` for one run, or check the balance in the account).
3. `output_schema` limits: not used yet. If the judge is moved to structured research
   output, the scorecard schema needs a reduced copy (`additionalProperties: false`,
   all properties required, no `pattern`/`format`/`minItems`, depth 5, 100 properties).
4. Whether `count` and date-range `freshness` behave through MCP as in the REST docs.
5. Whether every web result carries `page_age`.
6. Whether the Zenodo record (item-02) is findable by `you-search`, or only by passing
   its URL to `you-contents` (the fallback in `HACKATHON.md`).
7. Whether Contents live fetches obey `robots.txt`.

## A loose end, unchanged here

The user settings also pre-approve `Bash(python3:*)`, `Bash(python:*)` and several
`curl` commands. A run of either provider could in principle reach the web through
them. Neither provider's tool list blocks that today; a `--disallowedTools` entry for
those would close it if it shows up in a stream.
