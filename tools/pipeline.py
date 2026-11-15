"""Scan, judge and run candidates in one command, each step a recorded headless run.

    uv run --project core python tools/pipeline.py claude                 # reuse the latest scan
    uv run --project core python tools/pipeline.py claude --scan --judge 5
    uv run --project core python tools/pipeline.py claude --only timestral timesfm-3
    uv run --project core python tools/pipeline.py youcom --candidates-from claude --judge 5
    uv run --project core python tools/pipeline.py youcom --candidates-from merged --judge 5

Steps (each is `claude -p "/<skill> ..."` through tools/run_skill.py):
  1. scan            only with --scan; otherwise the latest candidates/<provider>/scan_*.jsonl
                     (--candidates-from <other provider> judges another provider's scan, so
                     both providers are compared on the same candidates)
                     (--candidates-from merged judges the combined list of all scans,
                     best first: run tools/merge_candidates.py after the scans)
  2. judge           the first --judge candidates that have no scorecard yet (the file is
                     ordered by fit to the spec), or exactly the ids given with --only
  3. run-candidate   every scorecard of this run's candidates labelled ACCEPT_RUN with no
                     receipt. Headless runs do not start model runs: if the model row is
                     not on the leaderboard the step stops and says what is needed.
Writes runs/pipeline_<id>.json (committed) and prints one line per candidate.
Failures are not swallowed: a failed scan stops the run before any judging, a candidate
whose judge failed gets no receipt, and the command exits nonzero if any step failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.merge_candidates import scan_order  # noqa: E402
from tools.run_skill import run, youcom_key  # noqa: E402

NO_MODEL_RUNS = (
    "Headless pipeline run. If the model row this scorecard needs is already in "
    "results/leaderboard.csv, write the receipt (step 5) and report. If it is not, do NOT "
    "download weights, change code or run any model: stop and report which model row is "
    "missing and which steps of the skill a person has to run."
)


def scorecard(provider: str, cid: str) -> dict | None:
    path = ROOT / "scorecards" / provider / f"{cid}.json"
    return json.loads(path.read_text()) if path.exists() else None


def step(meta: dict) -> dict:
    keep = (
        "run_id",
        "exit_code",
        "timed_out",
        "is_error",
        "num_turns",
        "total_cost_usd",
        "failure",
    )
    return {k: meta.get(k) for k in keep} | {"wall_seconds": meta.get("wall_seconds")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("provider", choices=["claude", "youcom"])
    ap.add_argument("--scan", action="store_true", help="run a new scan first")
    ap.add_argument("--judge", type=int, default=2, help="how many unjudged candidates to judge")
    ap.add_argument("--only", nargs="+", default=[], help="candidate ids to process")
    ap.add_argument("--parallel", type=int, default=2, help="judge runs at the same time")
    ap.add_argument("--model", default="", help="model for every step; default is the CLI's own")
    ap.add_argument(
        "--candidates-from",
        choices=["claude", "youcom", "merged"],
        default=None,
        help="read the latest scan of this provider instead of the run's own; 'merged' is "
        "the combined list written by tools/merge_candidates.py",
    )
    a = ap.parse_args()
    if a.provider == "youcom":
        youcom_key()  # refuse before any step starts, not inside a worker thread
    source = a.candidates_from or a.provider
    if a.scan and source != a.provider:
        sys.exit("--scan writes this provider's own candidates; drop --candidates-from")
    started = datetime.now(UTC)
    out: dict = {"provider": a.provider, "started_at": started.isoformat(timespec="seconds")}

    if a.scan:
        out["scan"] = step(run("scan", a.provider, [], model=a.model))
        if out["scan"]["failure"]:
            # Do not go on to judge an older scan as if it were this one.
            pid = f"pipeline_{started:%Y%m%dT%H%M%S}_{a.provider}"
            (ROOT / "runs" / f"{pid}.json").write_text(json.dumps(out, indent=1) + "\n")
            sys.exit(f"{pid}: the scan FAILED ({out['scan']['failure']}); nothing was judged")
    files = sorted((ROOT / "candidates" / source).glob("scan_*.jsonl"), key=scan_order)
    if not files:
        sys.exit(f"no candidates file for {source}: run with --scan or --candidates-from claude")
    out["candidates_file"] = str(files[-1].relative_to(ROOT))
    cands = [json.loads(x) for x in files[-1].read_text().splitlines() if x.strip()]
    ids = [c["candidate_id"] for c in cands]
    if a.only:
        missing = [i for i in a.only if i not in ids]
        if missing:
            sys.exit(f"not in {out['candidates_file']}: {missing}")
        chosen = a.only
    else:
        chosen = [i for i in ids if scorecard(a.provider, i) is None][: a.judge]
    rows = {i: {"candidate_id": i} for i in chosen}

    to_judge = [i for i in chosen if scorecard(a.provider, i) is None]
    with ThreadPoolExecutor(max(1, a.parallel)) as pool:
        metas = pool.map(lambda i: run("judge", a.provider, [i], model=a.model), to_judge)
        for i, m in zip(to_judge, metas, strict=True):
            rows[i]["judge"] = step(m)

    for i in chosen:  # one at a time: receipts read and write the shared results
        card = scorecard(a.provider, i)
        if (rows[i].get("judge") or {}).get("failure"):
            continue  # this run's judge did not finish: do not build a receipt on its scorecard
        if card and card.get("label") == "ACCEPT_RUN" and not card.get("receipt"):
            m = run("run-candidate", a.provider, [i], note=NO_MODEL_RUNS, model=a.model)
            rows[i]["run_candidate"] = step(m)
            rows[i]["run_candidate_report"] = m.get("result")

    for i in chosen:
        card = scorecard(a.provider, i) or {}
        receipt = card.get("receipt") or {}
        rows[i] |= {
            "label": card.get("label"),
            "runnable_class": card.get("runnable_class"),
            "receipt_verdict": receipt.get("verdict"),
        }
    out["candidates"] = list(rows.values())
    steps = [out.get("scan")] + [
        r.get(k) for r in rows.values() for k in ("judge", "run_candidate")
    ]
    out["total_cost_usd"] = round(sum(s["total_cost_usd"] or 0 for s in steps if s), 2)
    pid = f"pipeline_{started:%Y%m%dT%H%M%S}_{a.provider}"
    (ROOT / "runs" / f"{pid}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{pid}: {out['candidates_file']}, estimated cost ${out['total_cost_usd']}")
    for r in out["candidates"]:
        label = r["label"] or "not judged"
        verdict = r["receipt_verdict"] or "none"
        print(f"  {r['candidate_id']}: {label} ({r['runnable_class']}), receipt: {verdict}")
    failed = [
        f"{r['candidate_id']} {k.replace('_', '-')}: {r[k]['failure']}"
        for r in out["candidates"]
        for k in ("judge", "run_candidate")
        if (r.get(k) or {}).get("failure")
    ]
    if failed:  # a nonzero status, so a scheduler does not report success
        sys.exit(f"{pid}: {len(failed)} step(s) FAILED\n  " + "\n  ".join(failed))


if __name__ == "__main__":
    main()
