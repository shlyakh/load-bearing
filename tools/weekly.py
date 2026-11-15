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
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import registry as rg  # noqa: E402
from tools.merge_candidates import latest, merge  # noqa: E402
from tools.run_skill import cli_version, git, run, youcom_key  # noqa: E402
from tools.validate_scorecard import errors  # noqa: E402

PROVIDERS = ("claude", "youcom")
LIMIT = re.compile(r"usage limit|rate.?limit|limit reached|out of (extra )?usage|quota", re.I)
STOP_AFTER = 3  # judge failures in a row


def suffix(day: str) -> str:
    """'' for the first weekly run of a day, '_run2' and so on for later ones, counting
    every scan and queue file already written for that day."""
    names = [p.stem for p in (ROOT / "candidates").glob(f"*/*_{day}*.jsonl")]
    runs = [int(m.group(1)) for n in names if (m := re.search(r"_run(\d+)$", n))]
    used = max(runs, default=1 if any(n.endswith(day) for n in names) else 0)
    return f"_run{used + 1}" if used else ""


def read_rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def step(meta: dict) -> dict:
    keep = ("run_id", "wall_seconds", "num_turns", "total_cost_usd", "failure", "session_id")
    return {k: meta.get(k) for k in keep}


def hit_limit(meta: dict) -> bool:
    return bool(meta.get("failure")) and bool(LIMIT.search(str(meta.get("result") or "")))


def scan(provider: str, day: str, tag: str, model: str) -> dict:
    """One provider's scan. Returns its step record with `file` (or None when it failed
    or wrote no file)."""
    target = ROOT / "candidates" / provider / f"scan_{day}{tag}.jsonl"
    note = (
        f"Weekly run. Write the candidates to {target.relative_to(ROOT)} and use "
        f"`--candidate scan-{day}{tag.replace('_', '-')}` for the scan ledger."
    )
    meta = run("scan", provider, [], note=note, model=model)
    out = step(meta) | {"provider": provider, "file": None, "limit": hit_limit(meta)}
    if not meta["failure"]:
        if target.exists() and read_rows(target):
            out["file"] = str(target.relative_to(ROOT))
        else:
            out["failure"] = f"the scan finished but {target.relative_to(ROOT)} is missing or empty"
    return out


class Judging:
    """Runs the judge tasks and stops starting new ones when the breaker trips."""

    def __init__(self, day_tag: str, model: str):
        self.queue_file = f"candidates/merged/queue_{day_tag}.jsonl"
        self.model = model
        self.lock = threading.Lock()
        self.in_a_row = 0
        self.stopped: str | None = None

    def one(self, task: tuple[str, str]) -> dict:
        cid, provider = task
        out = {"candidate_id": cid, "provider": provider}
        with self.lock:
            if self.stopped:
                return out | {"skipped": self.stopped}
        card = ROOT / "scorecards" / provider / f"{cid}.json"
        note = (
            f"Weekly run. The candidate row is in {self.queue_file}. "
            f"Write the scorecard to {card.relative_to(ROOT)}."
        )
        since = time.time()
        meta = run("judge", provider, [cid], note=note, model=self.model)
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
            self.in_a_row = self.in_a_row + 1 if failure else 0
            if hit_limit(meta):
                self.stopped = self.stopped or "usage_limit"
            elif self.in_a_row >= STOP_AFTER:
                self.stopped = self.stopped or "failed"
        out |= step(meta) | {"failure": failure}
        if not failure:
            c = json.loads(card.read_text())
            out |= {"label": c.get("label"), "runnable_class": c.get("runnable_class")}
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
        "--dry-run", action="store_true", help="stop after choosing the queue; write nothing"
    )
    a = ap.parse_args()
    if a.dry_run and not a.skip_scan:
        sys.exit("--dry-run needs --skip-scan (a scan is a paid run)")
    if "youcom" in a.providers and not a.dry_run:
        youcom_key()  # refuse before any step starts
    started, t0 = datetime.now(UTC), time.perf_counter()
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
    }

    # 1. scan
    if a.skip_scan:
        for p in a.providers:
            f = latest(ROOT, p)
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
    judging = Judging(f"{a.date}{tag}", a.model)
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
    rep["ok"] = not failures and not judging.stopped and not rep["tool_errors"]
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
