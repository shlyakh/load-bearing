# You.com in this project: how it is used, what we measured, and feedback

Written Sat Nov 14, 2026, during the hackathon, from the first live runs. Everything
marked "checked live" was observed that day against the hosted MCP server
(`api.you.com/mcp`, server version 4.0.7). Prices are from You.com's documentation and
were not reconciled against the account. `notes/youcom_provider.md` covers how the
provider is wired and switched on; this note covers what happened when it ran.

## What the project does with You.com

The agent finds newly published forecasting claims, judges each one against a written
problem spec with cited sources, and for runnable ones measures the method on our own
PJM load benchmark. You.com is the search provider for the first two steps. The same
steps also run on Claude's built-in web search, so the two can be compared on the same
claims.

| Step | You.com tool | What it does there | Typical use per run |
|---|---|---|---|
| `/scan` (find claims) | Search | One query per topic and per site, limited to the last 120 days, to list dated pages about forecasting | 42 searches and 1 page fetch in the one run observed (it stopped early) |
| `/judge` (check one claim) | Research, `standard` effort | Finds the claim's primary sources and any independent replication, with citations | 1 task |
| `/judge` | Contents | Reads the primary sources themselves: paper, repository, model card | about 8 pages |
| `/judge` | Search | Targeted lookups, such as a paper by its exact title | 0 to 2 searches |
| `/run-candidate` (measure) | none | Reads the scorecard and the leaderboard; no web access | 0 |

Not used: the Answer API (not offered through the MCP server), Finance Research, the
Inference Router, and `you-discover` (see below). `you-balance` is not in the agent's
tool list; it was called by hand.

All calls go through the hosted MCP server with a bearer key passed per run. The agent
has no other web tool in a You.com run: Claude's own search and fetch are denied, so
every cited source in a You.com scorecard came through You.com.

## Results so far

Six claims judged on You.com, all six scorecards valid against the schema.

| Measure | Claude's own search | You.com |
|---|---|---|
| Claims judged under both | 6 | 6 |
| Same verdict | 6 of 6 | |
| Primary sources cited, those 6 claims | 30 | 30 |
| Evidence rows logged, those 6 claims | 70 | 110 |
| Model cost per judge | $1.85 to $2.29 (3 with a record) | $2.81 to $3.04 |
| Time per judge | 224 to 316 s | 186 to 222 s |

Read the cost row with care: it is the language model's cost, not the search charge,
and the You.com runs cost more partly because Research answers and fetched pages are
long and are read by the model. You.com's own charges for the six judges were about
$0.38 at documented prices (6 research tasks, 50 pages, 5 searches).

### The scan

Four You.com scans were started on Nov 14. Two stopped at the Claude usage limit and
wrote nothing (42 and 91 searches, $7.25 and $14.51 of model cost). Two ran to the end:
one in the late morning with the grouped `site:` form that does not restrict, and a
corrected one in the early afternoon with one `site:` per query. The table compares the
corrected scan with a Claude scan on the same `spec.yaml`.

| Measure | Claude's own search | You.com, one `site:` per query |
|---|---|---|
| Queries and domains | 7 queries, 6 groups | 7 queries, 12 sites plus the open web |
| Searches / page-fetch calls | 42 / 14 | 107 / 2 |
| Pages logged with a reason | 221 | 1,233 |
| Candidates kept | 44 | 53 |
| In both (same primary URL) | 37 | 37 |
| Only in this scan | 7 | 16 |
| Time | 931 s | 970 s |
| Model cost | $8.67 | $14.83 |
| Search charges | included in the model cost | about $0.54 at documented prices |

- Found only by You.com: sixteen items, six Zenodo records and six arXiv papers,
  plus journal articles (IET, Electronics, an Elsevier journal) and one vendor
  blog post. Found only by Claude: seven.
- 39 of the 53 were found by a search; 14 came only from the direct listings
  (`tools/feeds.py`). Both completed You.com scans missed the same two Zenodo records
  by search: the demo item (24161799) and the PJM cold-spell benchmark (24010850).
- The eight sites added from the seed list (four practice sites, four model-team sites)
  produced no kept candidate in any scan beyond the Timestral and TimesFM-3
  announcements, which were already candidates. They did produce noise: 69 vendor
  pages, 65 PJM news and committee pages, 101 off-topic publisher pages.
- The earlier, uncorrected You.com scan (42 searches, $10.33) kept 40 candidates, 39 of
  which are also in the corrected scan. Restricting properly found more, at about 45%
  more model cost.
- **Search dates are not always publication dates.** The scan found the TimesFM-3 blog
  post dated 2026-09-25 in search where the page says August 31, and most amperon.co
  posts dated 2026-07-22 for content from 2024 and 2025. So a result's date can be the
  day the page was last seen changed. The scan treats it as provisional for this reason.
- `you-contents` returned HTTP 504 three times on batches of URLs in the first completed
  scan; each URL came back when retried alone or in a smaller batch.
- The Claude scan's own domain restriction also leaked to arXiv, PMC and patent pages
  for the multi-site groups, so the Claude column is not a clean per-site search either.

## What the live server does (checked live)

1. **Tool names** are `you-search`, `you-contents`, `you-research`, as assumed.
   `?tools=you-search,you-contents,you-research` does switch on Research.
2. **Research is asynchronous.** The first call returns a task id; the same tool is
   then called with that id until the answer is ready. One judge made 1 task and 4
   polls. A log that counts tool calls therefore overstates research use about
   eightfold (48 calls were 6 tasks).
3. **Dates.** Every result in ten test searches carried `page_age`, and every date fell
   inside the requested `freshness` range (an exact `YYYY-MM-DDtoYYYY-MM-DD` range). The
   filter works as documented. What the date means is less certain: in the full scan
   some dates were later than the page's own publication date (see the scan section).
4. **One `site:` restricts; several do not.** `site:arxiv.org` returned only arXiv.
   `(site:lfenergy.org OR site:pjm.com)` returned the open web (Wikipedia, vendor
   pages). Two `site:` terms with or without `OR` returned one of the two domains only.
   Our instructions used the parenthesised form for domain groups; they now say one
   `site:` per call.
5. **`site:` together with `exclude_domains` is accepted**, although the tool's own
   description says the two cannot be combined.
6. **Highlights are the default.** `extraction` defaults to `highlights` and `count` to
   30. For the same ten results, highlights returned about 38,000 characters against
   about 22,000 with `extraction: "none"`, which still includes snippets. For a scan of
   40 or more searches that difference is mostly model cost, so the scan keeps `none`.
7. **Contents** accepts up to 100 URLs a call (the REST guide says 10). Fetching the
   Zenodo record by URL worked on the first try.
8. **Balance.** `you-balance` reported 917 cents on Nov 14, late morning, after the
   runs above and two scan attempts in progress. The starting credit was not recorded.

Not settled: whether Contents
obeys `robots.txt` on a live fetch (matters for Substack and Medium, where the site
owners discourage AI crawlers); structured output from Research (`output_schema`), not
used yet.

## `you-discover`

It is not a web discovery tool. It searches catalogues of agent tooling (GitHub's and
Hugging Face's agent finders and You.com's own catalogue) for skills, MCP servers and
plugins that fit a task. It needs no key.

Three queries were tried:

| Query, in short | What came back | Use to us |
|---|---|---|
| Find new forecasting papers and model releases | A skill that maps a trending Hugging Face model to its paper; a paper-digest skill; two unrelated finance and sales forecasting skills; a retail demand-forecasting MCP server | The model-to-paper resolver is the same job as one step of `/scan`. Worth reading, not adopting blind |
| Load forecasting data for US grid operators | The retail demand server again; database, charting and sales tools | None. The match was on the words "load" and "electric" |
| Search arXiv and Hugging Face for new papers | Hugging Face's paper-lookup skill and paper-publishing skill; You.com's own web skill; unrelated Hugging Face skills | The paper-lookup skill reads Hugging Face paper pages as markdown, a possible extra listing for `tools/feeds.py` |

Verdict: not part of the claim pipeline. It is a way to find building blocks before
writing one, and it would have been useful a week ago. Results are leads to code by
third parties; nothing was installed or run.

## What we changed because of the live runs

- `.claude/skills/providers.md`: one `site:` per call; `extraction: "none"` in the
  scan; research budget counted in tasks, not calls; the notes above on `count`,
  `page_age` and the Contents limit.
- `spec.yaml`: two more domain groups and three load-specific queries (from
  `notes/source_seed_list.md`). With one `site:` per call these groups cost more
  searches; the scan in progress was started before the fix and treated the
  multi-domain groups as open-web searches.

Still to do: count research tasks instead of calls in `tools/compare_providers.py` and
on the dashboard; add You.com charges to the run records (today only the model cost is
recorded); try `output_schema` so Research returns the scorecard fields directly.

## Feedback for You.com

What worked well:

- **Dated results with a strict range.** Exact-range `freshness` plus `page_age` on
  every result is what makes a "what was published this week" scan possible. Claude's
  built-in search returns no date field at all.
- **Research with sources as a list.** Citations arrive as URLs with titles, separate
  from the prose, so each can be logged and opened. The judge's rule "cite from the
  sources list, never from the answer text" was easy to follow.
- **The hosted MCP server.** One URL and one header, no install, and the tool list can
  be narrowed per run. Wiring took minutes once a key existed.
- **Cost.** Search charges were a rounding error next to the model cost.

What cost us time or would have misled us, in the scan specifically: batches of URLs
to Contents timing out with 504 where single URLs succeeded (a partial result with the
failed URLs marked would be easier to handle), and a large share of GitHub issue
threads among results for release-related queries.

What cost us time or would have misled us:

1. **Several `site:` terms fail silently.** A grouped query returned open-web results
   with no error or warning. An error, or support for `OR` between `site:` terms,
   would have caught it. As it stands a user believes the search was restricted.
2. **`include_domains` is host-only through MCP.** Understandable as a safety choice,
   but it leaves `site:` as the model's only allowlist, which makes point 1 matter more.
3. **Documentation and live server disagree** in small ways: the tool text says
   `site:` and `exclude_domains` cannot be combined (they can); the Contents guide says
   10 URLs (the tool takes 100); the default `extraction` is `highlights` on MCP, which
   a reader of the REST guide would not expect and which raises the model's token bill.
4. **Research polling looks like many calls.** A note in the tool description that
   polls are free and are not new tasks, or a separate `you-research-status` tool,
   would keep usage logs honest.
5. **The name `you-discover`** suggests content discovery. Its description is clear,
   but the doc pages we read name it without describing it.
6. **A wrong key gives two different errors.** With a malformed key, `you-balance`
   said the key was invalid or expired while `you-search` returned a bare 401 with no
   text. (Our mistake: quotes left around the key in a test script.) The same message
   on both would help.
7. **`page_age` is not always the publication date.** For a dated-claims scan the
   difference between "published" and "last changed" matters. Two separate fields, or a
   note saying which one `page_age` is, would let the agent trust it without a fetch.
8. **Usage in the response.** Each reply carries a `you/usage` block with the product
   and result count. Adding the charge in cents would let an agent keep its own running
   total without calling `you-balance`.

## Sources read on Nov 14

https://you.com/docs/welcome , https://you.com/docs/llms.txt ,
https://you.com/docs/agents/mcp-server.md , https://you.com/docs/choose-the-right-api.md ,
https://you.com/docs/guides/search/retrieve-page-content.md ,
https://github.com/youdotcom-oss/mcp . Earlier reading is listed in
`notes/hackathon_tools.md`.
