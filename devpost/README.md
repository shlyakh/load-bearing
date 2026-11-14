# Images for the Devpost page

Made on Nov 14, 2026, from the dashboard as it stood at about 15:15. Every image except
the cover is a capture of the live dashboard (`dashboard/index.html`) at twice screen
resolution. To redo a capture after the dashboard changes, open the same tab and panel,
or ask for the capture script (headless Chrome, kept outside the repo).

## Recommendation

**Thumbnail: `1_cover.png`.** It is the only image that says what the project is
without the video: the name, the one-line pitch, three numbers, and the zones. It is
1800 × 1200 (3:2). Devpost's exact thumbnail size was not checked; the project editor
states it next to the upload field. If it asks for another shape, crop the right edge
of the map, not the text.

**Gallery, in this order:**

| # | File | Caption to use | Why it is in the set |
|---|---|---|---|
| 1 | `1_cover.png` | Receipts for Forecasting Papers | Same as the thumbnail; Devpost shows the gallery first on the page |
| 2 | `2_receipt.png` | A receipt: a published claim against what we measured, per zone, with its 90% range | The core idea in one picture |
| 3 | `3_youcom_scan.png` | The same scan with You.com and with Claude's search: 53 claims against 44, 16 found only by You.com | The You.com result the hackathon judges will look for |
| 4 | `4_leaderboard.png` | Every model against the same baseline; models published after most test weeks are flagged | Shows the benchmark is real and honest about leakage |
| 5 | `7_zones_map.png` | Four PJM zones: two for development, two kept back for a fresh test | Context for non-specialists |
| 6 | `6_open_crawl.png` | Code review with and without the project's history in Open Crawl | Covers the Open Crawl prize |
| 7 | `5_how_it_works.png` | Setup once, then every week: listings, scan, judge, run, receipt | The architecture; tall, so it reads best last, when opened full size |

If only five images fit: drop 4 and 6.

**Video:** `video/out/receipts_demo.mp4` (164 s, git-ignored, on the laptop only).
Devpost takes a YouTube or Vimeo link, not a file, so upload it there first. Do not use
`dashboard/tour.webm`: it is the silent tour from the morning, before the You.com and
Open Crawl tabs existed.

## Notes on the images

- The cover's three numbers come from `results/` and the run records: 0.73 and 0.95
  are Chronos-2's error ratios on DOM against the temperature-only regression and
  against Vanilla with trend (forecast weather, 48 weeks); 53 and 44 are the claims
  kept by the two scans of Nov 14; 6 of 6 is `results/provider_comparison.csv`.
- "Powered by You.com" on the cover is the event's own name for itself. You.com is the
  search provider in the agent; it did not review or endorse the project.
- The zone map is drawn from counties each utility reports serving (EIA-861 Service
  Territory 2025, checked against ORNL/HIFLD polygons) on us-atlas county outlines. It
  is not PJM's official zone boundary (`notes/zone_geography.md`).
- The receipt image reads "Does not transfer: model clearly better" for DOM. That is
  correct for the claim it tests (a tie in Great Britain): a clear win here means the
  tie did not carry over.
