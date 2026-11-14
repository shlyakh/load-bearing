# Seed source list: forecasting methods applied to energy and load

Research report of Nov 14, 2026 (Claude research task in claude.ai, saved at Yuri's
request). Question: which blogs, newsletters, team channels and bulk repositories should
be searched for announcements and posts about forecasting methods applied to energy,
mostly electricity load.

How to read this next to the other notes:

- `notes/blog_newsletter_sources.md` (Nov 13) fetched every feed directly and recorded
  what each returned. This note is wider but less verified: it was built from web
  search and page reads, and most feed URLs here follow platform conventions and were
  not tested. Where the two disagree on a feed or on access, the Nov 13 note wins.
  Known disagreement: this report lists the IIF blog as live; the Nov 13 pass got 403
  on every IIF request.
- LinkedIn is not a source (decision 21, hard rule 10). The LinkedIn section below is
  kept only as a record of what the report found; it changes nothing. See
  `notes/social_sources.md`.
- Hard rule 9: no article text is stored here. The report's direct quotations were
  replaced with paraphrases, and links to LinkedIn scraper vendors were left out.
- Model facts (release dates, parameter counts, licences, leaderboard scores) are
  as reported by the research task and are unverified in the sense of hard rule 7.
  Several are self-reported by vendors. Check before use.

## Summary

- Highest yield for load-specific content: Tao Hong's blog, AI Horizon Forecast, the
  IIF/ISF channels, OpenSTEF (LF Energy), Amperon, GridStatus, PJM's load forecast
  development page and Load Analysis Subcommittee, the ESIG forecasting workshop, plus
  keyword-filtered arXiv / OpenAlex / Semantic Scholar queries.
- Foundation-model teams announce through GitHub releases, Hugging Face org pages and
  corporate blogs, not Substack. Leaderboard changes (GIFT-Eval, fev-bench, TIME, BOOM)
  are the "new state of the art" signal.
- Bulk layer beyond arXiv, Zenodo and Hugging Face: OpenAlex, Semantic Scholar,
  Crossref, OpenReview, OSTI.gov, SSRN/TechRxiv, RePEc NEP, journal feeds, GitHub
  search, PyPI release feeds, Hacker News (Algolia), Reddit JSON. Papers with Code was
  retired by Meta in July 2025 and redirects to Hugging Face trending papers.

## Findings that bear on the benchmark

1. Energy is a standard test domain for foundation-model evaluations, and price is the
   most common target. The Kafritsas post of 2026-11-09 runs Kumo, Nori, Chronos-2 and
   TimesFM-3 zero-shot against tuned trees on all days of 2017 German day-ahead prices
   (the open EPF benchmark of Lago et al.). It reports that every foundation model
   beat both tree models with a statistically significant gap, with Kumo and TimesFM-3
   about tied near 3.76 to 3.77 EUR/MWh average error. It also reports failures when
   the residual-load covariate leaves its historical range. For week-ahead load this
   points at extreme-temperature weeks as the place to stress-test.
   https://aihorizonforecast.substack.com/p/has-time-series-forecasting-found
2. Load-specific evidence is mixed. arXiv 2609.06656 (Pendyala, Fu, Yan, Virani;
   ISO New England and ENTSO-E data) reports that zero-shot Chronos-2 trails
   task-specific models, that its error grows faster with horizon, and that
   fine-tuning closes much of the gap. arXiv 2609.24559 (t0) reports that 11 of 30
   known-future-covariate tasks on fev-bench score worse with covariates, the largest
   drop (15%) on a 15-minute electricity series with weather covariates. arXiv
   2607.01966 covers foundation models for low-voltage peak load.
3. Licences differ and should be a recorded field. As reported: TimesFM-3 weights are
   non-commercial (TimesFM-2.5 was Apache 2.0); Toto 2.0 is Apache-2.0; Timestral has a
   modified MIT licence with a revenue threshold.
4. The operational load-forecasting community publishes outside the ML ecosystem: ISO
   stakeholder documents, ESIG workshops, Itron Brown Bags, IJF/Foresight, vendor
   blogs. PJM's long-term model is still hourly multiple regression per zone with
   weather rotation (Manual 19 revision 39, effective 2026-06-30).

## Tier 1: directly about energy and load forecasting

| Rank | Source | URL | Who / type | Why relevant | Activity (as reported) | How to monitor |
|---|---|---|---|---|---|---|
| 1 | Energy Forecasting (Tao Hong) | http://blog.drhongtao.com/ | Individual (UNC Charlotte, BigDEAL Lab); Blogger | The reference load-forecasting blog: GEFCom/BigDEAL data, IJF calls, reviewer guidance | Posts 2026-07-02 and 2026-08-07 | Blogger feed (`/feeds/posts/default`); about monthly |
| 2 | AI Horizon Forecast (Nikos Kafritsas) | https://aihorizonforecast.substack.com/ | Individual; Substack, partly paid | Hands-on foundation-model evaluations, including a two-part electricity-price series | Posts 2026-11-05 and 2026-11-09 | RSS at `/feed`; about weekly |
| 3 | IIF blog, ISF, IJF, Foresight | https://forecasters.org/blog/ ; https://isf.forecasters.org/ | Professional society | Tao Hong energy-forecasting award, IJF special issues, Foresight practitioner papers | Blog post 2026-05-01; ISF 2026 held Jun 28 to Jul 1; ISF 2027 Jun 20 to 23, Paphos | Feed unverified (403 on Nov 13); IJF via Crossref |
| 4 | OpenSTEF / LF Energy | https://lfenergy.org/projects/openstef/ | Open-source project (Alliander) | Production short-term load forecasting; 4.0 is modular and adds a foundation-models package | 4.0 announced 2026-07-31; PyPI releases to 2026-10-21 | `https://pypi.org/rss/project/openstef/releases.xml`; GitHub API releases |
| 5 | PJM load forecast pages, Load Analysis Subcommittee | https://www.pjm.com/planning/resource-adequacy-planning/load-forecast-dev-process | ISO | Model specs (Manual 19, 2026 supplement), Itron model review, data-center accuracy report (2026-05-29) | Items dated Jan to Jul 2026 | No RSS; weekly page diff; LAS meeting materials |
| 6 | GridStatus blog and Insights | https://blog.gridstatus.io/ ; https://www.gridstatus.io/insights | Company | ISO forecast-vs-actual analyses (July 2026 heat wave), long-term forecast coverage, open `gridstatus` library | Insights to Oct 2026 | Blog feed at `/rss` unverified; Insights page diff |
| 7 | Amperon blog and resources | https://www.amperon.co/blog | Vendor | Describes its methods: hybrid regression and boosted trees, mid-term demand from ECMWF ensembles, AIFS, net load | Items to Oct 2026 | Page diff; no confirmed RSS |
| 8 | ESIG Forecasting and Meteorology workshop | https://www.esig.energy/event/forecasting-and-meteorology-in-power-systems-workshop/ | Industry association | ISO operational forecasting, large-load and data-center forecasting, probabilistic forecasting at MISO and ISO-NE | Jun 15 to 16, 2026; fall workshop Oct 26 to 30, 2026 | Event calendar; slides posted after events |
| 9 | Itron forecasting blog, Brown Bags | https://na.itron.com/blog | Vendor | Utility short- and long-term practice, data-center load, annual survey | Brown Bag scheduled 2026-12-08 | Manual |
| 10 | IEEE PES Working Group on Energy Forecasting and Analytics | https://site.ieee.org/pes-psope/subcommittees/power-system-economics-subcommittee/working-group-on-energy-forecasting-and-analytics/ | IEEE working group | Origin of GEFCom; PESGM panels | Page stale; group met at PESGM 2025 | Track the PESGM program |
| 11 | Hyndsight (Rob Hyndman) | https://robjhyndman.com/hyndsight/ | Individual | Evaluation rigour; a 2026-08-25 post on evaluating foundation-model claims | Latest post late Oct 2026 | RSS `https://robjhyndman.com/hyndsight/index.xml` (fetched Nov 13) |
| 12 | Pierre Pinson | http://pierrepinson.com/ | Individual (IJF editor-in-chief) | Probabilistic energy forecasting, award announcements | Post 2026-04-30; sources conflict on activity | WordPress; low volume |
| 13 | Rafał Weron | https://p.wz.pwr.edu.pl/~weron.rafal/ ; https://ideas.repec.org/e/pwe42.html | Academic | Electricity price forecasting benchmarks, temporal hierarchies | Grant runs 2026 to 2030 | RePEc NEP |
| 14 | BigDEAL competitions, GEFCom data | via blog.drhongtao.com; doi 10.1049/stg2.12162 | Academic competitions | Peak magnitude, timing and shape; GEFCom2012/2014 load data | No 2026 challenge found | Tao Hong's blog |
| 15 | Nixtla energy pages | https://www.nixtla.io/industries/energy ; https://www.nixtla.io/docs/use_cases/forecasting_energy_demand | Vendor | TimeGPT on PJM demand; accuracy figure is the vendor's own tutorial | Active 2026 | See Nixtla below |

Other energy sources named but not checked: ERCOT, NYISO (Gold Book), ISO-NE (CELT),
MISO, CAISO and SPP load-forecast pages; EIA (API); NREL, LBNL, PNNL, EPRI (indexed in
OSTI.gov); NERC reliability assessments; Climate Change AI
(https://www.climatechange.ai/, NeurIPS 2026 workshop Dec 11); Open Climate Fix;
Electricity Maps; WattTime; Yes Energy; Enverus; Modo Energy; Energy Exemplar;
Forecasting Impact podcast (https://forecastingimpact.buzzsprout.com/).

## Tier 2a: foundation-model teams (announcement channels)

| Rank | Team / model | Channels | Latest release (as reported) | Energy angle | Monitor via |
|---|---|---|---|---|---|
| 1 | Google Research, TimesFM | github.com/google-research/timesfm ; huggingface.co/google ; research.google/blog | TimesFM-3, 2026-08-31: 330M parameters, natively multivariate, non-commercial weights; BigQuery support reported as preview (from a snippet, not opened) | Weather covariates | GitHub API releases; HF org |
| 2 | Amazon Science / AutoGluon, Chronos and fev | github.com/amazon-science/chronos-forecasting ; github.com/autogluon/fev ; amazon.science | Chronos-2 (Oct 2025), small and synth variants | Paper case study on ENTSO-E load and German price; GitHub Discussion 337 on domains | GitHub API releases and discussions |
| 3 | Mistral, Timestral | https://mistral.ai/news/timestral/ ; huggingface.co/mistralai/Timestral-209M | 2026-10-15; 5M to 209M parameters, long context, CPU inference; self-reported top of GIFT-Eval (MASE 0.658 vs t0-gamma 0.661, TimesFM-3 0.667, Chronos-2 0.698) | Coverage stresses energy and 15-minute sensor use | Mistral news page; HF org |
| 4 | Datadog, Toto and BOOM | https://www.datadoghq.com/blog/ai/toto-2/ ; github.com/DataDog/toto | Toto 2.0, Apr 2026; Apache-2.0; exogenous variables still planned | No covariates yet | GitHub API releases |
| 5 | Nixtla, TimeGPT and open libraries | https://www.nixtla.io/blog ; github.com/Nixtla ; docs.nixtla.io | TimeGPT-2 / 2.1 | PJM demand tutorials | Blog page diff; GitHub API releases |
| 6 | Salesforce AI Research, Moirai / uni2ts, GIFT-Eval | github.com/SalesforceAIResearch/uni2ts ; GIFT-Eval space on Hugging Face | Moirai-2 on the leaderboard | GIFT-Eval has an energy domain | Leaderboard diffs |
| 7 | IBM Research, Granite TTM | github.com/ibm-granite/granite-tsfm ; huggingface.co/ibm-granite | TTM r2 | Small models | GitHub / HF |
| 8 | THUML (Tsinghua), Timer, Timer-XL, Sundial, Time-Series-Library | github.com/thuml | Sundial (ICML 2025) | Standard ETT / Electricity benchmarks | GitHub |
| 9 | Others | NX-AI TiRex; Prior Labs TabPFN-TS; Kumo; CMU MOMENT; Lag-Llama; Synthefy; t0 (arXiv 2609.24559) | not checked | TabPFN-TS reported strong on covariate tasks | arXiv keyword alerts |
| | Libraries | Darts, sktime, GluonTS, PyTorch Forecasting, Skforecast, Prophet, Greykite | not checked | Baselines | PyPI release feeds |

Leaderboards: GIFT-Eval (Salesforce), fev-bench (autogluon/fev), TIME, BOOM (Datadog,
observability data). Note that GIFT-Eval scores many energy series univariately, so a
leaderboard gain says little about covariate-driven load.

GitHub access: `github.com/robots.txt` disallows the `.atom` feeds; use the REST API
(see `notes/blog_newsletter_sources.md`).

## Tier 2b: individual newsletters and blogs

| Rank | Source | URL | Notes | Activity (as reported) |
|---|---|---|---|---|
| 1 | Valeriy Manokhin | https://valeman.substack.com/ | Conformal prediction, probabilistic forecasting, critiques of deep-learning claims; promotional | Posts to Oct 2026 |
| 2 | The Forecaster (Marco Peixeiro) | https://medium.com/the-forecaster | Hands-on foundation-model articles | Last post 2026-07-27 |
| 3 | Rami Krispin | https://ramikrispin.substack.com/ | Weekly curated time-series digest | Active |
| 4 | Mindful Modeler (Christoph Molnar) | https://mindfulmodeler.substack.com/ | Tabular foundation models for forecasting | Active |
| 5 | randomstorms | https://randomstorms.substack.com/ | First-principles series on foundation models and covariates | Active 2026 |

Not checked (mostly active on social media rather than blogs): Christoph Bergmeir,
Slawek Smyl, Stephan Kolassa, Tim Januschowski, Sean Taylor, Casper Solheim Bojer,
Konrad Banachewicz, Skforecast blog, Azul Garza, Max Mergenthaler.

Dormant: The Business Forecasting Deal (SAS, Michael Gilliland) has ended.

Substack and Medium `robots.txt` name AI crawlers; that is an owner decision recorded
in the Nov 13 note.

## Tier 3: broad sources, keyword filter only

Hugging Face blog and trending papers; Towards Data Science; Medium tag feeds
(`medium.com/feed/tag/time-series-forecasting`); Reddit r/MachineLearning,
r/datascience, r/energy; Hacker News. Avoid SEO news aggregators: during the research
they gave conflicting release dates for the same model.

## Bulk and aggregator sources

| Source | Endpoint | Access | Notes |
|---|---|---|---|
| arXiv | export.arxiv.org/api/query ; rss.arxiv.org/rss/cs.LG | API, RSS | cs.LG, stat.ML, stat.AP, eess.SY, eess.SP, physics.soc-ph |
| OpenAlex | api.openalex.org | Free REST API | Good for journals (IJF, Applied Energy, Energy and AI, IEEE TSG) |
| Semantic Scholar | api.semanticscholar.org | Free API, key recommended | Citation expansion from seed papers |
| Crossref | api.crossref.org | Free REST API | New DOIs by ISSN (IJF 0169-2070, Applied Energy 0306-2619) |
| OpenReview | openreview.net (API v2) | API | ICLR / NeurIPS / ICML and time-series workshops |
| OSTI.gov | osti.gov | API | DOE lab reports |
| SSRN, TechRxiv | papers.ssrn.com ; techrxiv.org | Search, alerts | Energy economics and IEEE preprints |
| RePEc / IDEAS, NEP | ideas.repec.org | RSS, email (NEP-ENE, NEP-FOR) | Working papers |
| Hugging Face papers | huggingface.co/papers/trending | Web, HF API | Successor to Papers with Code |
| alphaXiv | alphaxiv.org | Web | Discussion layer |
| Google Scholar alerts | scholar.google.com | Email only | Author and phrase alerts |
| IEEE Xplore, ScienceDirect | ieeexplore.ieee.org ; sciencedirect.com | IEEE API (key) | ScienceDirect RSS is disallowed by robots (Nov 13 note); use Crossref |
| GitHub | api.github.com | API | Topics: time-series-forecasting, load-forecasting, energy-forecasting |
| PyPI | `pypi.org/rss/project/<pkg>/releases.xml` | RSS | chronos-forecasting, timesfm, openstef, toto-models, neuralforecast |
| Kaggle | kaggle.com | API | Energy competitions and datasets |
| Hacker News | hn.algolia.com/api | Free API | Keyword search |
| Reddit | `reddit.com/r/<sub>/search.json` | Rate-limited | |
| YouTube | YouTube Data API | API | ISF talks, Itron webinars |
| Conferences | ISF, ACM e-Energy, IEEE PESGM, PSCC, PMAPS, NeurIPS/ICML/ICLR workshops, CCAI | via OpenReview / Crossref | |

## LinkedIn (record only; excluded by decision 21)

The report found no official keyword search over public posts and confirmed that the
User Agreement bars scraping. Its conclusion matches `notes/social_sources.md`: use
LinkedIn only for manual reading, and add the primary source a post links to (paper,
repository, release) to the lists above. The report also suggested search-engine
queries restricted to LinkedIn; that is not adopted here, since snippets are not
evidence under hard rule 10.

## Query strings

- Core: "load forecasting", "electricity demand forecasting", "short-term load
  forecasting", "medium-term load forecasting", "mid-term load forecasting",
  "probabilistic load forecasting", "peak load forecasting", "net load",
  "week-ahead load".
- Method and domain: ("foundation model" OR TSFM OR "zero-shot") AND (load OR
  electricity OR "power demand"); model names TimesFM, Chronos-2, Moirai, TimeGPT,
  Toto, Timestral, TabPFN-TS, TiRex, Sundial, each AND load.
- Domain anchors: PJM, ERCOT, MISO, NYISO, ISO-NE, CAISO, SPP, ENTSO-E, GEFCom,
  BigDEAL, "data center load", "large load".
- Benchmarks: GIFT-Eval, fev-bench, "TIME benchmark", BOOM, "EPF benchmark".

## The report's suggestions (not decisions)

1. Automate the feed and API layer first; weekly page diff for pages without feeds
   (PJM, Amperon, ESIG, Itron).
2. Score relevance on four fields: target is load or net load rather than price;
   weather covariate handling; horizon of a week or more; licence.
3. Stress-test any foundation-model claim on out-of-range temperature weeks.

## Caveats from the report

- Activity dates are from pages retrieved in Nov 2026. Entries marked "not checked"
  need a liveness check.
- Only the Hyndsight feed was confirmed by the report; other feed paths are platform
  conventions.
- Timestral and Toto 2.0 rankings are self-reported; Nixtla's PJM figure is from its
  own tutorial.

## Pages the report cited

Papers and model pages:
https://arxiv.org/pdf/2607.01966 ,
https://arxiv.org/html/2609.06656v1 ,
https://arxiv.org/pdf/2609.24559 ,
https://arxiv.org/pdf/2609.00089 ,
https://arxiv.org/pdf/2510.15821 ,
https://arxiv.org/pdf/2602.06909 ,
https://arxiv.org/pdf/2509.04208 ,
https://arxiv.org/pdf/2602.14024 ,
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5067419 ,
https://github.com/amazon-science/chronos-forecasting ,
https://github.com/amazon-science/chronos-forecasting/discussions/337 ,
https://github.com/DataDog/toto/tree/main/toto2 ,
https://mistral.ai/news/timestral/ ,
https://robjhyndman.com/papers/fdashape.pdf ,
https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/stg2.12162

PJM:
https://www.pjm.com/-/media/DotCom/documents/manuals/m19.pdf ,
https://www.pjm.com/-/media/DotCom/planning/res-adeq/load-forecast/load-forecast-supplement-2026.pdf ,
https://www.pjm.com/-/media/DotCom/committees-groups/cifp-lla/2026/20260220/20260220-item-01---manual-19-revisions---redline.pdf ,
https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/fact-sheets/load-forecasting-supports-reliability-and-efficiency.pdf

Posts and project pages:
https://aihorizonforecast.substack.com/p/timesfm-25-hands-on-tutorial-with ,
https://aihorizonforecast.substack.com/p/toto-20-the-upgraded-time-series ,
https://aihorizonforecast.substack.com/p/timer-xl-long-context-foundation ,
https://aihorizonforecast.substack.com/p/moment-a-foundation-model-for-time ,
https://mindfulmodeler.substack.com/p/time-series-forecasting-with-tabular ,
https://ramikrispin.substack.com/p/issue-64-forecasting-with-foundation ,
https://randomstorms.substack.com/p/time-series-foundation-models-intro ,
https://lfenergy.org/openstef-4-0-is-here-any-ml-approach-any-it-stack-one-energy-forecasting-ecosystem/ ,
https://lfenergy.org/openstef-4-launch-a-new-way-of-building-energy-forecasting-solutions/ ,
https://blog.gridstatus.io/early-july-2026-heat-wave/ ,
https://opensource.gridstatus.io/en/latest/ ,
https://www.amperon.co/blog/always-innovating-amperons-new-techniques-to-improve-energy-forecasting ,
https://www.amperon.co/blog/amperon-integrates-ai-weather-forecasts-from-ecmwf ,
https://www.amperon.co/blog/wind-solar-net-load-forecasting-day-ahead-optimization ,
https://forecasters.org/blog/2026/05/01/call-for-nominations-for-the-iif-tao-hong-award-2026-energy-forecasting/ ,
http://pierrepinson.com/index.php/2026/04/30/iif-tao-hong-award-2026/ ,
https://www.climatechange.ai/events/neurips2026 ,
https://forecastingimpact.buzzsprout.com/1641538/episodes/12065704-tao-hong-on-energy-forecasting
