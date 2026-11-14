# You.com against Claude's built-in search, on the same work

Text for the Devpost page. Numbers are from the runs of Sat Nov 14, 2026; sources are
listed at the end. The section "Short version" is the part to paste.

## Short version (paste this)

**How much does the result depend on the search engine?** Our agent does two kinds of
web work: a weekly *scan* that finds newly published forecasting claims, and a *judge*
that checks one claim against its primary sources. We ran both twice on the same
inputs, once with Claude's built-in web search and once with You.com (Search, Contents
and Research through the hosted MCP server), with Claude's own search switched off in
the You.com runs.

The judge reached the same verdict on all six claims it checked both ways. The scan
found more with You.com: 53 claims against 44, with 37 in common. The You.com scan ran
one search per site, 107 in all, each limited to an exact date range, where the
built-in search ran 42 over groups of sites.

| Scan of the last 120 days, same queries and sites | Claude's built-in search | You.com |
|---|---|---|
| Searches | 42 | 107 |
| Pages logged with a reason kept or dropped | 221 | 1,233 |
| Claims kept | 44 | 53 |
| Found by both | 37 | 37 |
| Found only by this one | 7 | 16 |
| Time | 15.5 min | 16 min |
| Language-model cost | $8.67 | $14.83 |
| Search charges | included | about $0.54 |

You.com's own charges were small. The extra cost is the language model reading five
times as many pages.

## The judge, in a little more detail

| Judging one claim | Claude's built-in search | You.com |
|---|---|---|
| Claims judged both ways | 6 | 6 |
| Same verdict | 6 of 6 | |
| Primary sources cited, those 6 claims | 30 | 30 |
| How the sources are found | a helper agent that searches and fetches | 1 Research task, about 8 pages through Contents, 0 to 2 searches |
| Time per claim | 3.7 to 5.3 min | 3.1 to 3.7 min |
| Language-model cost per claim | about $2 | about $3 |

Every statement in a scorecard points to a URL, and in a You.com run each of those URLs
came through You.com.

## What to keep in mind

- One run of each scan, so some of the difference is run-to-run variation.
- The built-in search's site filter leaked for the multi-site groups, so its column is
  not a clean per-site search.
- A You.com result's date is sometimes the day the page last changed, not the day it
  was published, so the agent confirms dates before relying on them.
- Two Zenodo records, one of them our demo item, were found by neither search engine.
  They came from reading Zenodo's listing directly.

## Sources

- Scan snapshots: `comparisons/scan_2026-11-14_claude_run2/`,
  `comparisons/scan_2026-11-14_youcom_run2/`
- Judge comparison: `results/provider_comparison.csv`
- Details and feedback for You.com: `notes/youcom_usage_and_feedback.md`
