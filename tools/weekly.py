"""The weekly run: scan with every provider, judge what is new, write the run report.

    uv run --project core python tools/weekly.py                      # both providers, cap 60
    uv run --project core python tools/weekly.py --cap 3
    uv run --project core python tools/weekly.py --providers claude --cap 2
    uv run --project core python tools/weekly.py --skip-scan --dry-run   # show the queue only

Steps (decisions 38, 44, 45, 46):
  1. scan      `/scan` once per provider, as recorded headless runs (tools/run_skill.py).
               A provider whose scan fails is left out; the run goes on with the others.
  2. merge     the scans of this run into candidates/merged/scan_<date>[_runN].jsonl.
  3. registry  tools/registry.py decides what is new. Works already judged, rejected or
               implemented are skipped. The queue (works deferred earlier first, then new
               ones by fit, at most --cap) goes to candidates/merged/queue_<date>[_runN].jsonl.
  4. judge     every queued candidate with every provider, --parallel at a time. Each
               scorecard is stamped with its run id and validated; the scorecard of a
               failed judge is removed.
  5. record    registry statuses, the review sheets, and runs/weekly_<id>.json and .md.
               The .md is the pull request text.

It never runs `/run-candidate` and never starts a model (decision 38).

Stopping early. After a failure that looks like a usage limit, or after three judge
failures in a row, no further judge run is started. What was not judged is marked in
the registry (`usage_limit` or `failed`) and goes first next week. The report is still
written, so the run still ends in a pull request with whatever finished.

Exit status: 0 when the run produced a report, even a partial one (the report's `ok`
field and the pull request text say what failed); 1 when no scan finished.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import registry as rg  # noqa: E402
from tools.merge_candidates import latest, merge  # noqa: E402
from tools.run_skill import cli_version, git, run, youcom_key  # noqa: E402
from tools.schedule_gate import WEEK_ANCHOR  # noqa: E402
from tools.validate_scorecard import errors  # noqa: E402

PROVIDERS = ("claude", "youcom")
LIMIT = re.compile(
    r"usage limit|rate.?limit|limit reached|hit your .{0,20}limit|out of (extra )?usage|quota", re.I
)
STOP_AFTER = 3  # judge failures in a row
# The weekly budget (`--week-budget`; Yuri, 2026-11-19: a fifth of the Fable weekly limit).
# The estimates are what a step cost with Fable 5.2 on 2026-11-19 and 20, rounded up; a
# step is not started when the week's spend plus its estimate would pass the budget.
JUDGE_ESTIMATE_USD = 3.0
SCAN_ESTIMATE_USD = 12.5  # one provider


SAY = threading.Lock()


def say(text: str, row: str = "") -> None:
    """One timestamped progress line on standard output, which is the Actions step log.
    `row`, a markdown table row, also goes to the run's Summary page. The repository is
    public and so are its logs: only ids, counts, times, costs and labels belong here,
    never page text or search queries."""
    with SAY:
        print(f"{datetime.now(UTC):%H:%M:%S} {text}", flush=True)
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if row and path:
            with open(path, "a") as f:
                f.write(row + "\n")


def beat(what: str):
    """The callback a run reports its counts to, about once a minute."""

    def tell(n: dict) -> None:
        say(
            f"{what}: working, {n['seconds'] // 60} min, {n['turns']} turns, "
            f"{n['searches']} searches, {n['fetches']} fetches, {n['other']} other tool calls"
        )

    return tell


def mins(meta: dict) -> str:
    return f"{(meta.get('wall_seconds') or 0) / 60:.1f} min"


def suffix(day: str) -> str:
    """'' for the first weekly run of a day, '_run2' and so on for later ones, counting
    every scan and queue file already written for that day."""
    names = [p.stem for p in (ROOT / "candidates").glob(f"*/*_{day}*.jsonl")]
    runs = [int(m.group(1)) for n in names if (m := re.search(r"_run(\d+)$", n))]
    used = max(runs, default=1 if any(n.endswith(day) for n in names) else 0)
    return f"_run{used + 1}" if used else ""


def week_start(now: datetime, anchor: str = WEEK_ANCHOR) -> datetime:
    """The start of the 7-day budget period that holds `now`."""
    a = datetime.fromisoformat(anchor)
    return a + timedelta(days=7 * ((now - a) // timedelta(days=7)))


def week_spent(now: datetime, anchor: str = WEEK_ANCHOR) -> float:
    """Estimated cost of the weekly runs recorded since this budget period began. Only
    reports on this branch count, so a run whose pull request is not merged is unseen."""
    since, total = week_start(now, anchor), 0.0
    for f in (ROOT / "runs").glob("weekly_*.json"):
        r = json.loads(f.read_text())
        if datetime.fromisoformat(r["started_at"]) >= since:
            total += r.get("total_cost_usd") or 0
    return round(total, 2)


def scan_age_days(provider: str, day: str) -> int | None:
    """Days between `day` and the date in the name of the provider's latest scan."""
    f = latest(ROOT, provider)
    m = re.search(r"scan_(\d{4}-\d{2}-\d{2})", f.name) if f else None
    return (date.fromisoformat(day) - date.fromisoformat(m.group(1))).days if m else None


def read_rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def step(meta: dict) -> dict:
    keep = ("run_id", "wall_seconds", "num_turns", "total_cost_usd", "failure", "session_id")
    return {k: meta.get(k) for k in keep}


def hit_limit(meta: dict) -> bool:
    """A failed run whose error is the subscription's limit: status 429, or the CLI's
    message ("You've hit your 5-hour limit")."""
    text = f"{meta.get('error_text') or ''} {meta.get('result') or ''}"
    limited = str(meta.get("api_error_status")) == "429" or bool(LIMIT.search(text))
    return bool(meta.get("failure")) and limited


def scan(provider: str, day: str, tag: str, model: str) -> dict:
    """One provider's scan. Returns its step record with `file` (or None when it failed
    or wrote no file)."""
    target = ROOT / "candidates" / provider / f"scan_{day}{tag}.jsonl"
    note = (
        f"Weekly run. Write the candidates to {target.relative_to(ROOT)} and use "
        f"`--candidate scan-{day}{tag.replace('_', '-')}` for the scan ledger."
    )
    what = f"scan {provider}"
    say(f"{what}: started")
    meta = run("scan", provider, [], note=note, model=model, progress=beat(what))
    out = step(meta) | {"provider": provider, "file": None, "limit": hit_limit(meta)}
    if not meta["failure"]:
        if target.exists() and read_rows(target):
            out["file"] = str(target.relative_to(ROOT))
        else:
            out["failure"] = f"the scan finished but {target.relative_to(ROOT)} is missing or empty"
    cost = f"${meta.get('total_cost_usd') or 0:.2f}"
    n = len(read_rows(target)) if out["file"] else 0
    result = f"{n} candidates" if not out["failure"] else f"FAILED: {out['failure']}"
    say(
        f"{what}: done in {mins(meta)}, {cost}, {result}",
        f"| scan | {provider} | | {mins(meta)} | {cost} | {result} |",
    )
    return out


class Judging:
    """Runs the judge tasks and stops starting new ones when the breaker trips."""

    def __init__(self, day_tag: str, model: str, budget_left: float | None = None):
        self.queue_file = f"candidates/merged/queue_{day_tag}.jsonl"
        self.model = model
        self.budget_left = budget_left  # dollars this run may still spend; None for no budget
        self.lock = threading.Lock()
        self.in_a_row = 0
        self.stopped: str | None = None
        self.number: dict[tuple[str, str], int] = {}  # task -> its place in the run
        self.spent = 0.0  # this run's judge cost so far
        self.spent_before = 0.0  # the week's cost before judging began

    def one(self, task: tuple[str, str]) -> dict:
        cid, provider = task
        out = {"candidate_id": cid, "provider": provider}
        what = f"judge {self.number.get(task, '?')}/{len(self.number) or '?'} {provider} {cid}"
        with self.lock:
            if not self.stopped and self.budget_left is not None:
                if self.budget_left < JUDGE_ESTIMATE_USD:
                    self.stopped = "budget"
                else:
                    self.budget_left -= JUDGE_ESTIMATE_USD  # held until the real cost is known
            if self.stopped:
                say(
                    f"{what}: not started ({self.stopped})",
                    f"| judge | {provider} | {cid} | | | not started ({self.stopped}) |",
                )
                return out | {"skipped": self.stopped}
        say(f"{what}: started")
        card = ROOT / "scorecards" / provider / f"{cid}.json"
        note = (
            f"Weekly run. The candidate row is in {self.queue_file}. "
            f"Write the scorecard to {card.relative_to(ROOT)}."
        )
        since = time.time()
        meta = run("judge", provider, [cid], note=note, model=self.model, progress=beat(what))
        failure = meta["failure"]
        if not failure and not card.exists():
            failure = "the judge finished but wrote no scorecard"
        if not failure:
            errs = errors(json.loads(card.read_text()))
            if errs:
                failure = "the scorecard is invalid: " + "; ".join(errs[:3])
        if failure and card.exists() and card.stat().st_mtime >= since:
            card.unlink()  # do not leave a half-finished verdict for review
        with self.lock:
            if self.budget_left is not None:
                self.budget_left += JUDGE_ESTIMATE_USD - (meta.get("total_cost_usd") or 0)
            self.in_a_row = self.in_a_row + 1 if failure else 0
            self.spent += meta.get("total_cost_usd") or 0
            total = f"judging so far ${self.spent:.2f}, week ${self.spent_before + self.spent:.2f}"
            if hit_limit(meta):
                self.stopped = self.stopped or "usage_limit"
            elif self.in_a_row >= STOP_AFTER:
                self.stopped = self.stopped or "failed"
        out |= step(meta) | {"failure": failure}
        if not failure:
            c = json.loads(card.read_text())
            out |= {"label": c.get("label"), "runnable_class": c.get("runnable_class")}
        cost = f"${meta.get('total_cost_usd') or 0:.2f}"
        result = f"FAILED: {failure}" if failure else f"label {out['label']}"
        say(
            f"{what}: done in {mins(meta)}, {cost}, {result}; {total}",
            f"| judge | {provider} | {cid} | {mins(meta)} | {cost} | {result} |",
        )
        return out


def optional_tool(script: str, *args: str) -> str | None:
    """Run a repo tool if it exists (the review sheets arrive after the first run).
    Returns an error text, or None."""
    if not (ROOT / script).exists():
        return None
    r = subprocess.run(
        [sys.executable, str(ROOT / script), *args], cwd=ROOT, capture_output=True, text=True
    )
    return None if r.returncode == 0 else f"{script} {' '.join(args)}: {r.stderr.strip()[-400:]}"


def markdown(rep: dict, reg: rg.Registry) -> str:
    """The pull request text."""
    r = rep["registry"]
    judged = [j for j in rep["judges"] if not j.get("failure") and not j.get("skipped")]
    failed = [j for j in rep["judges"] if j.get("failure")]
    skipped = [j for j in rep["judges"] if j.get("skipped")]
    lines = [
        f"# Weekly scan and judge, {rep['date']}",
        "",
        f"Run `{rep['weekly_id']}`, commit `{rep['git_commit']}`, CLI `{rep['cli_version']}`. "
        f"Estimated model cost ${rep['total_cost_usd']} "
        "(the client's estimate; no You.com charges). "
        f"Wall time {rep['wall_minutes']} min.",
        "",
    ]
    if rep.get("budget"):
        b = rep["budget"]
        after = round(b["spent_before_usd"] + rep["total_cost_usd"], 2)
        lines += [
            f"Budget for the week from {b['week_started'][:10]}: ${b['week_budget_usd']:g}. "
            f"Spent before this run ${b['spent_before_usd']}, after it ${after}."
            + (" The scan was skipped to stay inside it." if b.get("scan_skipped") else ""),
            "",
        ]
    if not rep["ok"]:
        lines += ["**This run did not finish cleanly.** See Failures below.", ""]
    lines += [
        "## Scans",
        "",
        "| Provider | Candidates | Cost | Run | Result |",
        "|---|---|---|---|---|",
    ]
    for s in rep["scans"]:
        n = len(read_rows(ROOT / s["file"])) if s.get("file") else 0
        lines.append(
            f"| {s['provider']} | {n} | ${s.get('total_cost_usd') or 0:.2f} | `{s.get('run_id')}` "
            f"| {s.get('failure') or 'ok'} |"
        )
    lines += [
        "",
        "## Registry",
        "",
        f"- New works: {len(r['new'])}",
        f"- Already known (judged, rejected or implemented; skipped): {len(r['known'])}",
        f"- Seen in an earlier scan but never judged: {len(r['unjudged_seen_before'])}",
        f"- Carried over from an earlier run: {len(r['carried_over'])}",
        f"- Queued for judging: {len(r['queued'])} (cap {rep['cap']})",
        f"- Deferred by the cap, first next week: {len(r['deferred_by_cap'])}",
        f"- Not finished this run, first next week: {len(rep['sync']['unfinished'])}",
    ]
    for label, key in (
        ("Possible new versions of a known work (check)", "possible_new_version"),
        (
            "New works that link to a known work (possible duplicates, check)",
            "shares_url_with_known",
        ),
    ):
        if r[key]:
            lines += ["", f"{label}:"] + [f"- `{k}`" for k in r[key]]
    lines += [
        "",
        "## Judged",
        "",
        "| Work | Candidate | Provider | Label | Class | Run |",
        "|---|---|---|---|---|---|",
    ]
    keys = {q["candidate_id"]: q["registry_key"] for q in rep["queue"]}
    for j in sorted(judged, key=lambda j: (j["candidate_id"], j["provider"])):
        cid, p = j["candidate_id"], j["provider"]
        title = reg.entries[keys[cid]]["title"][:60].replace("|", "/")
        lines.append(
            f"| {title} | [{cid}](scorecards/{p}/{cid}.json) | {p} | {j['label']} "
            f"| {j['runnable_class']} | `{j['run_id']}` |"
        )
    by: dict[str, dict[str, str]] = {}
    for j in judged:
        by.setdefault(j["candidate_id"], {})[j["provider"]] = j["label"]
    both = [v for v in by.values() if len(v) > 1]
    agree = sum(1 for v in both if len(set(v.values())) == 1)
    lines += [
        "",
        f"Label agreement between providers: {agree} of {len(both)} "
        "candidates judged by more than one.",
    ]
    lines += ["", "## Failures", ""]
    problems = [f"scan {s['provider']}: {s['failure']}" for s in rep["scans"] if s.get("failure")]
    problems += [f"judge {j['candidate_id']} ({j['provider']}): {j['failure']}" for j in failed]
    if rep["stopped"]:
        problems.append(
            f"judging stopped early ({rep['stopped']}); {len(skipped)} judge runs were not started"
        )
    problems += rep["tool_errors"]
    lines += [f"- {p}" for p in problems] or ["None."]
    lines += [
        "",
        "## Review",
        "",
        "- [ ] `reviews/scan.csv`: new rows have `human_relevant`",
        "- [ ] `reviews/judge.csv`: new rows have a verdict and the four checks",
        "- [ ] Possible duplicates and new versions above are resolved",
        "- [ ] Failures above are understood",
        "",
        "To see how a verdict was reached: "
        "`uv run --project core python tools/trace.py <candidate id>`.",
        "Transcripts of these runs are in the private archive under the run ids above.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--providers", nargs="+", choices=PROVIDERS, default=list(PROVIDERS))
    ap.add_argument("--cap", type=int, default=60, help="most candidates judged in this run")
    ap.add_argument("--parallel", type=int, default=2, help="judge runs at the same time")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--model", default="", help="model for every step; default is the CLI's own")
    ap.add_argument("--skip-scan", action="store_true", help="use each provider's latest scan")
    ap.add_argument(
        "--scan-every",
        type=int,
        default=0,
        metavar="DAYS",
        help="scan only when a provider's latest scan is at least this many days old",
    )
    ap.add_argument(
        "--cap-with-scan", type=int, default=None, help="the cap for a run that also scans"
    )
    ap.add_argument(
        "--week-budget",
        type=float,
        default=0,
        metavar="USD",
        help="most estimated model cost in one budget week, over all weekly runs; 0 for none",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="stop after choosing the queue; write nothing"
    )
    a = ap.parse_args()
    if a.dry_run and not a.skip_scan:
        sys.exit("--dry-run needs --skip-scan (a scan is a paid run)")
    if "youcom" in a.providers and not a.dry_run:
        youcom_key()  # refuse before any step starts
    started, t0 = datetime.now(UTC), time.perf_counter()
    budget = None
    if a.week_budget and not a.dry_run:
        spent = week_spent(started)
        budget = {
            "week_budget_usd": a.week_budget,
            "week_started": week_start(started).isoformat(timespec="seconds"),
            "spent_before_usd": spent,
            "left_usd": round(a.week_budget - spent, 2),
        }
        if budget["left_usd"] < JUDGE_ESTIMATE_USD:
            print(f"this week's budget is used (${spent} of ${a.week_budget}); nothing was started")
            return
    why_no_scan = "--skip-scan was given" if a.skip_scan else ""
    if a.scan_every and not a.skip_scan:
        ages = [scan_age_days(p, a.date) for p in a.providers]
        if all(x is not None and x < a.scan_every for x in ages):
            a.skip_scan = True  # the week's scans are recent enough
            why_no_scan = f"the latest scans are {max(ages)} days old, under {a.scan_every}"
    if budget and not a.skip_scan:
        if budget["left_usd"] < SCAN_ESTIMATE_USD * len(a.providers) + JUDGE_ESTIMATE_USD:
            budget["scan_skipped"] = True  # judge from the latest scans instead
            a.skip_scan = True
            why_no_scan = "the week's budget cannot cover a scan"
    if not a.skip_scan and a.cap_with_scan is not None:
        a.cap = a.cap_with_scan
    tag = "" if a.dry_run else suffix(a.date)
    weekly_id = f"weekly_{started:%Y%m%dT%H%M%S}"
    rep: dict = {
        "weekly_id": weekly_id,
        "date": a.date,
        "started_at": started.isoformat(timespec="seconds"),
        "providers": a.providers,
        "cap": a.cap,
        "git_commit": git("rev-parse", "--short", "HEAD"),
        "scans": [],
        "judges": [],
        "stopped": None,
        "tool_errors": [],
        "budget": budget,
    }

    if not a.dry_run:
        week = ""
        if budget:
            week = f", week budget ${budget['spent_before_usd']} of ${a.week_budget:g} spent"
        say(
            f"{weekly_id}: model {a.model or 'the CLI default'}, providers "
            f"{' '.join(a.providers)}, cap {a.cap}{week}",
            "| Step | Provider | Candidate | Time | Cost | Result |\n|---|---|---|---|---|---|",
        )

    # 1. scan
    if a.skip_scan:
        for p in a.providers:
            f = latest(ROOT, p)
            if not a.dry_run:
                say(f"scan {p}: NOT scanning ({why_no_scan}); reusing {f.name if f else 'nothing'}")
            rep["scans"].append(
                {"provider": p, "file": str(f.relative_to(ROOT)) if f else None, "reused": True}
            )
    else:
        with ThreadPoolExecutor(len(a.providers)) as pool:
            rep["scans"] = list(pool.map(lambda p: scan(p, a.date, tag, a.model), a.providers))
    scans = {s["provider"]: read_rows(ROOT / s["file"]) for s in rep["scans"] if s.get("file")}
    rep["cli_version"] = cli_version()
    out_json = ROOT / "runs" / f"{weekly_id}.json"
    if not scans:
        rep |= {"ok": False, "registry": None}
        out_json.write_text(json.dumps(rep, indent=1) + "\n")
        sys.exit(f"{weekly_id}: no scan finished; nothing was judged")

    # 2. merge, 3. registry
    merged = merge(scans, ROOT)
    reg = rg.Registry(root=ROOT)
    merged_file = ROOT / "candidates" / "merged" / f"scan_{a.date}{tag}.jsonl"
    res = rg.ingest(reg, merged, a.date, str(merged_file.relative_to(ROOT)), a.cap)
    rep["registry"], rep["queue"] = res["report"], res["queue"]
    if a.dry_run:
        print(json.dumps({k: len(v) for k, v in res["report"].items()}))
        for q in res["queue"]:
            mark = "  (carried over)" if q["carried_over"] else ""
            print(f"  {q['candidate_id']}  {q['registry_key']}{mark}")
        return
    merged_file.parent.mkdir(parents=True, exist_ok=True)
    merged_file.write_text("".join(json.dumps(r) + "\n" for r in merged))
    queue_file = merged_file.with_name(f"queue_{a.date}{tag}.jsonl")
    queue_file.write_text("".join(json.dumps(r) + "\n" for r in res["queue"]))
    rg.save(reg.entries, ROOT)

    # 4. judge
    tasks = [
        (q["candidate_id"], p)
        for q in res["queue"]
        for p in a.providers
        if not (ROOT / "scorecards" / p / f"{q['candidate_id']}.json").exists()
    ]
    left = None
    if budget:
        left = budget["left_usd"] - sum(s.get("total_cost_usd") or 0 for s in rep["scans"])
    judging = Judging(f"{a.date}{tag}", a.model, left)
    judging.number = {t: i for i, t in enumerate(tasks, 1)}
    scans_cost = sum(s.get("total_cost_usd") or 0 for s in rep["scans"])
    judging.spent_before = (budget["spent_before_usd"] if budget else 0) + scans_cost
    say(f"queue: {len(res['queue'])} works, {len(tasks)} judge runs, {a.parallel} at a time")
    if any(s.get("limit") for s in rep["scans"]):
        judging.stopped = "usage_limit"  # a scan already hit the limit: do not start judges
    with ThreadPoolExecutor(max(1, a.parallel)) as pool:
        rep["judges"] = list(pool.map(judging.one, tasks))
    rep["stopped"] = judging.stopped

    # 5. record
    rep["sync"] = rg.sync(reg, judging.stopped or "failed")
    rg.save(reg.entries, ROOT)
    for script, args in (("tools/reviews.py", ["sync"]), ("dashboard/build_reviews.py", [])):
        err = optional_tool(script, *args)
        if err:
            rep["tool_errors"].append(err)
    steps = rep["scans"] + rep["judges"]
    rep["total_cost_usd"] = round(sum(s.get("total_cost_usd") or 0 for s in steps), 2)
    rep["wall_minutes"] = round((time.perf_counter() - t0) / 60, 1)
    failures = [s for s in steps if s.get("failure")]
    # Stopping at the budget is the plan working, not a run that went wrong.
    rep["ok"] = not failures and judging.stopped in (None, "budget") and not rep["tool_errors"]
    out_json.write_text(json.dumps(rep, indent=1) + "\n")
    out_json.with_suffix(".md").write_text(markdown(rep, reg))
    done = sum(1 for j in rep["judges"] if not j.get("failure") and not j.get("skipped"))
    print(
        f"{weekly_id}: {len(res['queue'])} queued, {done} of {len(tasks)} judge runs finished, "
        f"{len(failures)} failed, stopped early: {judging.stopped or 'no'}, "
        f"estimated cost ${rep['total_cost_usd']}"
    )
    print(f"report: {out_json.with_suffix('.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
