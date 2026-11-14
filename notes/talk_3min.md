# Three-minute talk: talking points

Written for the hackathon presentation on Nov 14, 2026. The same text is in the speaker
notes of the slide deck: https://claude.ai/artifact/APSUpcPFEfifCXQw9cZGXj (private until
shared from its Share menu). Numbers come from `results/` and the run records of Nov 14;
`notes/demo_script.md` is the older version for a live dashboard walkthrough.

Links to show: dashboard https://shlyakh.github.io/load-bearing/ , code
https://github.com/shlyakh/load-bearing , video `video/out/receipts_demo.mp4` (164 s).

## 1. Receipts for Forecasting Papers (about 15 s)

Every week a new forecasting model claims to be the best. I built live research agents that read those claims as they appear, check them against their primary sources, and then measure the runnable ones on my own data.

So instead of hype, I get a receipt: what was claimed, and what we measured.

## 2. Why electricity load (about 25 s)

We picked electricity load as the test case. It is a hot topic for two reasons: demand is growing, partly because of data centers, and foundation models for time series have improved quickly, so new claims arrive every week.

A disclaimer: week-ahead load forecasting is a well-known problem. We are not trying to beat what power providers and energy hedge funds already model. We chose it because these forecasts run fast enough to build the whole idea in a day, and because weather does real work as an input.

The benchmark: hourly load in four PJM zones, forecast every Monday for the next 168 hours. JC and DOM to start; AEP and AE kept back for a fresh test.

## 3. How it works (about 30 s)

There are three agents, each a headless Claude run with a fixed list of tools, and two plain scripts around them.

A script reads public listings with exact dates. Agent one, the scan, searches for new claims and keeps only dated ones that point at a primary source. Agent two, the judge, reads those sources and scores the claim against our problem, with a citation for every statement. Agent three runs the model, but only registered models, under rules frozen at a git tag, scored once.

The receipt is written by a script: the agent supplies the claim in words, never a number.

The scan and the judge can use Claude's own search or You.com, and the outputs are kept apart, so we can compare them.

## 4. One receipt, end to end (about 35 s)

Here is one receipt. A pre-registered study this week found that in Great Britain, Chronos-2 roughly ties a plain regression once both get the same weather forecast: a ratio of 0.97.

On our Dominion zone, against our first baseline, we measured 0.73. That looks like a clear win. But the agent's search turned up the benchmark this field actually uses, and against it the ratio is 0.95: close to a tie again.

So we froze the rules, picked two zones no model had been run on, and scored once: 1.01 and 0.89. Neither clears our ten percent bar.

The receipt says the claim partially transfers. The point: our first baseline made the model look 27 percent better than it is.

## 5. You.com against Claude's built-in search (about 30 s)

We ran the same scan twice, same queries, same sites: once with Claude's built-in search, once with You.com.

You.com kept 53 claims against 44. 37 were found by both, and 16 only by You.com. The reason is practical: every You.com result carries a date, and a search can be held to one site and an exact date range, so the agent ran one narrow search per site.

The judge uses You.com's Research API to find the primary sources and Contents to read them. On the six claims judged both ways, the verdicts were identical, so the verdict does not depend on one search engine.

You.com's own charges for all of this were under two dollars at list prices. Most of the cost is the language model reading pages.

## 6. Honest about what can't be tested (about 20 s)

So far the agents have judged 25 claims and written 11 receipts: six partially transfer and five are untestable.

Untestable is a result, not a failure. TimesFM 3.0 and Timestral were released after most of our test weeks, so they may have trained on them. The leaderboard flags them as grey diamonds and the receipt refuses to call it.

And when a paper said the way you encode the calendar matters, we registered four new encodings and scored them once. None made the calendar help.

## 7. Open Crawl (about 20 s)

We also tried Open Crawl. I imported my Claude history and ran a code review with Codex, asking how the agents are deployed, live and on a schedule, once without Open Crawl and once with it.

Without it, the review explained what the code does and found a real bug: a failed agent run still reported success, so a scheduler could carry on with an old scan.

With it, the review also recovered why: the plan from earlier sessions to keep the command-line agents and run them weekly on GitHub Actions, with every run ending in a pull request.

We fixed the bug the same afternoon.

## 8. Receipts, not hype (about 10 s)

Next: a weekly run that ends in a pull request, so a person reviews every receipt before it lands; and forecasts made before the week happens, so models released this month can be tested fairly.

Find, judge, run, receipt. Receipts, not hype. Thank you.

Total: about 185 seconds. If running long, cut slide 6 to its first sentence.
