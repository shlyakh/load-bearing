# Search providers

The skills use three capabilities and never name a tool directly. Every result goes
through `tools/ledger.py` into `evidence/<provider>/<candidate_id>.jsonl`; `/judge`
reasons only from the ledger.

| Capability | `claude` | `youcom` (hosted MCP server `you-com`) |
|---|---|---|
| `search(query, since, domains)` | WebSearch | `mcp__you-com__you-search` |
| `fetch(url)` | WebFetch | `mcp__you-com__you-contents` |
| `research(question)` | a subagent that searches and fetches | `mcp__you-com__you-research` |

Outputs are kept apart per provider (`evidence/<provider>/`, `candidates/<provider>/`,
`scorecards/<provider>/`) so the two can be compared on the same inputs
(`tools/compare_providers.py`).

Independent of the provider, `tools/feeds.py` reads the arXiv, Hugging Face and Zenodo
listings directly (`candidates/feeds/`). They give exact dates, which web search does not.

Rules for every provider:
- `linkedin.com` is never searched, fetched or cited. A LinkedIn URL may be stored as
  an identifier in `discovered_via` only.
- Store URLs and short paraphrases. Never store the text of someone else's post or page.
- Search window: `scan.window_days` in `spec.yaml` (120 days).
- Use only the provider's own tools. A `youcom` run has no WebSearch or WebFetch; if a
  You.com tool fails, record the failure in the ledger and the report, do not route
  around it.

## `youcom`: how to call the tools

Tool names are as Claude Code shows them for server `you-com` (`tools/run_skill.py`
sets it up; `notes/youcom_provider.md` turns it on).

`you-search` (search)
- `freshness`: an exact range `YYYY-MM-DDtoYYYY-MM-DD`, from the window start to today
  (for example `2026-07-17to2026-11-14`). The words `day`, `week`, `month`, `year` are
  also accepted, but the scan uses the exact range.
- Domains: `include_domains` cannot be set through MCP. Restrict with exactly one
  `site:` per query, so a group of `scan.domains` with several domains takes one call
  per domain. Checked live on Nov 14: `(site:a OR site:b)` does not restrict at all
  (results came from the open web), and two `site:` terms returned one domain only.
  The open-web group has no `site:`.
- Always `exclude_domains: ["linkedin.com"]` (accepted together with `site:` on the
  live server, although the tool text says the two cannot be combined).
- `extraction: "none"` in the scan: results then carry `snippets`, which is enough to
  shortlist. The server's default is `highlights`, which returned about 70% more text
  for the same ten results. Use `highlights` only when a snippet cannot settle
  whether a page is on topic, instead of a separate fetch.
- `count`: 50 for a `site:` query, 20 for the open web (the server's default is 30).
  First page only (`offset` 0).
- Each result has `title`, `url`, `description` and `page_age` (present on every result
  in the Nov 14 checks, and inside the `freshness` range). Still treat `page_age` as a
  provisional date: a result without it is `unknown` until fetched.

`you-contents` (fetch)
- `urls`: up to 10 per call (the live tool accepts 100; 10 keeps one reply readable);
  ask for markdown. A URL that comes back empty is a failed
  fetch: record it as such, do not guess the page.
- Never pass a `linkedin.com` URL.

`you-research` (research)
- The live tool is asynchronous: the first call returns a `task_id`, and the same tool
  is called again with that `task_id` until the answer is ready. Those polls are not
  new research tasks: the budget counts tasks, not calls.
- `research_effort: "standard"` (about $0.05 a task, 10 to 30 s). Not `lite`, which
  cannot take an output schema; not `deep` or higher without a reason in the report.
- `source_control`: `exclude_domains: ["linkedin.com"]`. Set `freshness` only when the
  question is about recent work; `/judge` reads older primary sources too.
- The answer has inline `[[n]]` markers and a `sources` list (`url`, `title`,
  `snippets`). Cite from `sources`, never from the answer text: each source used gets
  its own ledger row (URL, title, date if known, a short paraphrase in your words).
  Snippets are page text: paraphrase them, never paste them into a note.
- An answer sentence with no source behind it is not evidence.
