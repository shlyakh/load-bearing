# Demo script: three minutes, live

Written Sat Nov 14, 2026, about noon, from the results in the repository at that time.
Numbers to re-check before going on stage are marked (check). The scan line changes if
the corrected You.com scan finishes; see the last section.

## Before you start

- Browser: https://shlyakh.github.io/receipts/ open on the Receipt tab. Reload once.
- Terminal, in the repo, font large. Have these two ready in the history:

  ```
  uv run --project core python tools/run_skill.py smoke youcom
  uv run --project core python tools/compare_providers.py
  ```

- Editor tab: `scorecards/youcom/item-02.json`, scrolled to `primary_sources`.
- Start the smoke command as you begin to speak in beat 2. It takes about 17 seconds.
- A full `/judge` takes three to four minutes. Do not run one live. Show a finished one.

## The script

| Time | Show | Say |
|---|---|---|
| 0:00 to 0:25 | Dashboard, "The problem" tab | "Every week a new forecasting model claims to be the best. I forecast electricity load for a living, and I cannot tell which claims apply to my problem. So I built an agent that reads each claim as it appears, checks its sources, and then measures the model on my own data. I get a receipt, not hype." |
| 0:25 to 1:05 | Terminal: smoke test running, then the scorecard file | "Here is one claim, published this week: in Great Britain, a pretrained model called Chronos-2 roughly ties a plain regression once both get the same weather forecast. The ratio is 0.97. The judge agent uses You.com for this. Research finds the primary sources, Contents reads them, and every statement in the scorecard points to a URL. This call is live." (point at the three You.com tool names in the output) "And this is the finished scorecard: five primary sources, pre-registered yes, same inputs for the baseline yes, and one mismatch, their horizon is a day and mine is a week." |
| 1:05 to 1:50 | Dashboard, Receipt tab | "Does the claim transfer to a US grid, a week ahead? I ran the same model on PJM load, 48 weeks, all of them after the model's weights were published, so it cannot have trained on them. Against my first baseline, a temperature-only regression, the model's error is 0.73 of the baseline's on the Dominion zone. That looks like a clear win, not a tie. The receipt says: partially transfers." |
| 1:50 to 2:25 | Dashboard, New zones tab | "Then the agent's search turned up the benchmark this field actually uses. Against that, the lead mostly disappears: 0.95 on Dominion, 1.00 on Jersey Central. So I froze the rules, picked two zones no model had been run on, and scored once. 1.01 and 0.89, both inconclusive. The first baseline made the model look 27 percent better. The right baseline closed most of that gap." |
| 2:25 to 2:50 | Dashboard, New claims tab, the provider table; click the You.com switch | "How much does this depend on the search engine? I judged the same claims twice, once with Claude's built-in search and once with You.com. Five claims, five identical verdicts. The scan ran both ways too: 40 new claims from You.com, 44 from Claude, 29 in common. You.com returns a date on every result, which is what makes 'what was published this week' possible at all." |
| 2:50 to 3:00 | Dashboard, How it works tab | "Find, judge, run, receipt. The protocol was frozen at a git tag before the scored run, and the scored run happened once. Receipts, not hype." |

## Numbers used, and where they come from

| Number | Source |
|---|---|
| GB claim 0.97 (0.966, range 0.931 to 1.001) | `scorecards/youcom/gb-demand-weather-zero-shot-backtest.json`, `receipt.claimed` |
| 0.73 on DOM (0.665 to 0.805); JC 0.817, inconclusive | `results/primary.md` |
| 48 weeks, all after the weights | same scorecard, `n_windows`, `n_windows_after_weights` |
| "partially" | same scorecard, `receipt.verdict` |
| 0.95 DOM and 1.00 JC against the standard benchmark (0.946, 0.997) | `results/README.md`, protocol-v1.1 |
| 1.01 AEP and 0.89 AE, both inconclusive (45 weeks) | `results/README.md`, protocol-v2 |
| 27 percent | 1 minus 0.73 |
| Five of five verdicts agree | `results/provider_comparison.csv` (check) |
| 40, 44 and 29 claims | `notes/youcom_usage_and_feedback.md`, scan table (check) |
| Five primary sources on item-02 | `scorecards/youcom/item-02.json` |

## Wording to keep

- Say "transfers", "partially transfers", "does not transfer". Never "the claim is
  true" or "false": the receipt tests whether a result carries over to our problem.
- Call the first baseline "the temperature-only regression".
- If asked about training overlap: all 48 scored weeks postdate the Chronos-2 weights;
  earlier years of the same public series may be in its training data.
- If asked what was built today: the You.com provider's live runs, the provider
  comparison, the wider source lists and the dashboard's New claims additions. The
  harness, data, baselines and protocol are prior work, disclosed in `README.md`.

## If something goes wrong

| Problem | Do |
|---|---|
| Smoke test is slow or fails | Keep talking and switch to the scorecard file. Say: "the live call is slow on this network; here is the same call's result from this morning." Run records are in `runs/`. |
| No network | Open `dashboard/index.html` from disk; it needs no network. Skip the live call. |
| Asked for a live judge | "A full judge takes about three minutes; here is what one produces", and show the scorecard and `evidence/youcom/item-02.jsonl`. |
| Asked what You.com did worse | A query with several `site:` filters searched the open web without an error, and batches of URLs sometimes timed out. Both are in `notes/youcom_usage_and_feedback.md`. |

## Questions you may get

- **Cost?** About $3 of language-model cost per judged claim and a few cents of You.com
  charges; a scan is $9 to $10.
- **Why two zones first, then two more?** We had already looked at the first two, so a
  fair test needed zones chosen by a stated rule before any model ran on them.
- **Is the regression a straw man?** That is the finding: against the field's standard
  benchmark the model's lead is within the margin.

## If the corrected You.com scan finishes

Replace the scan sentence in the 2:25 beat with the new counts from the scan table in
`notes/youcom_usage_and_feedback.md`. Nothing else in the script depends on it.
