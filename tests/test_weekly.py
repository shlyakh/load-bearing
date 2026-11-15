"""The weekly orchestrator and the path guard, with the headless runs faked.

uv run --project core pytest tests/test_weekly.py -q
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.guard_paths as guard  # noqa: E402
import tools.merge_candidates as mc  # noqa: E402
import tools.registry as rg  # noqa: E402
import tools.run_skill as rs  # noqa: E402
import tools.weekly as wk  # noqa: E402

REAL = wk.ROOT
CARD = json.loads((REAL / "scorecards" / "claude" / "item-02.json").read_text())


def cand(i: int) -> dict:
    return {
        "candidate_id": f"work-{i}",
        "title": f"Synthetic work number {i}",
        "primary_url": f"https://arxiv.org/abs/2701.{i:05d}",
        "other_urls": [],
        "published_at": "2027-01-01",
        "candidate_type": "paper",
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """An empty copy of the repo layout; every module's ROOT points at it."""
    for d in (
        "candidates/claude",
        "candidates/youcom",
        "scorecards/claude",
        "scorecards/youcom",
        "runs",
    ):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "schemas").mkdir()
    shutil.copy(REAL / "schemas" / "scorecard.schema.json", tmp_path / "schemas")
    for m in (wk, rg, mc, rs):
        monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(wk, "youcom_key", lambda: "k")
    monkeypatch.setattr(wk, "cli_version", lambda: "test")
    monkeypatch.setattr(wk, "git", lambda *a: "abc1234")
    yield tmp_path
    assert not list((REAL / "runs").glob("weekly_2027*"))  # nothing leaked into the real repo


def fake_run(repo: Path, n_candidates: int, fail: dict[tuple[str, str], str]):
    """A stand-in for run_skill.run: scans write candidate files, judges write a valid
    scorecard unless `fail` names (provider, candidate id) with a result text."""
    calls = []

    def run(skill, provider, args, note="", model=""):
        calls.append((skill, provider, *args))
        meta = {
            "run_id": f"r-{skill}-{provider}-{'-'.join(args)}",
            "total_cost_usd": 1.0,
            "failure": None,
            "result": "done",
        }
        if skill == "scan":
            target = repo / note.split("Write the candidates to ")[1].split(" ")[0]
            target.write_text("".join(json.dumps(cand(i)) + "\n" for i in range(n_candidates)))
        elif (provider, args[0]) in fail:
            meta |= {"failure": "the CLI reported an error", "result": fail[(provider, args[0])]}
            (repo / "scorecards" / provider / f"{args[0]}.json").write_text("{half")
        else:
            card = CARD | {"candidate_id": args[0]}
            (repo / "scorecards" / provider / f"{args[0]}.json").write_text(json.dumps(card))
        return meta

    return run, calls


def weekly(monkeypatch, *argv: str) -> dict:
    monkeypatch.setattr(sys, "argv", ["weekly.py", "--date", "2027-01-04", *argv])
    wk.main()
    rep = sorted((wk.ROOT / "runs").glob("weekly_*.json"))[-1]
    return json.loads(rep.read_text())


def test_clean_run_judges_each_candidate_with_both_providers(repo, monkeypatch):
    run, calls = fake_run(repo, 3, {})
    monkeypatch.setattr(wk, "run", run)
    rep = weekly(monkeypatch, "--parallel", "1")
    assert rep["ok"] and len(rep["judges"]) == 6 and rep["total_cost_usd"] == 8.0
    assert sorted(c[0] for c in calls).count("judge") == 6
    reg = rg.load(repo)
    assert all(e["status"] == "judged" and e["queue"] is None for e in reg.values())
    md = next((repo / "runs").glob("weekly_*.md")).read_text()
    assert "Label agreement between providers: 3 of 3" in md and "None." in md


def test_cap_limits_candidates_not_judge_runs(repo, monkeypatch):
    run, calls = fake_run(repo, 5, {})
    monkeypatch.setattr(wk, "run", run)
    rep = weekly(monkeypatch, "--cap", "2", "--parallel", "1")
    assert len(rep["judges"]) == 4 and len(rep["registry"]["deferred_by_cap"]) == 3
    reasons = [e["queue"]["reason"] for e in rg.load(repo).values() if e["queue"]]
    assert reasons == ["cap"] * 3


def test_usage_limit_stops_judging_and_still_writes_the_report(repo, monkeypatch):
    run, calls = fake_run(repo, 4, {("claude", "work-1"): "You have hit your usage limit."})
    monkeypatch.setattr(wk, "run", run)
    rep = weekly(monkeypatch, "--parallel", "1")
    assert rep["stopped"] == "usage_limit" and not rep["ok"]
    started = [j for j in rep["judges"] if not j.get("skipped")]
    assert len(started) == 3  # work-0 twice, work-1 once; nothing after the limit
    assert not (
        repo / "scorecards" / "claude" / "work-1.json"
    ).exists()  # half-written card removed
    reg = rg.load(repo)
    left = {e["canonical_candidate_id"]: e["queue"]["reason"] for e in reg.values() if e["queue"]}
    assert left == {"work-1": "usage_limit", "work-2": "usage_limit", "work-3": "usage_limit"}
    md = next((repo / "runs").glob("weekly_*.md")).read_text()
    assert "judging stopped early (usage_limit)" in md


def test_one_provider_scan_failing_does_not_stop_the_other(repo, monkeypatch):
    run, _ = fake_run(repo, 2, {})

    def flaky(skill, provider, args, note="", model=""):
        if skill == "scan" and provider == "youcom":
            return {"run_id": "x", "failure": "timed out", "result": None, "total_cost_usd": 0}
        return run(skill, provider, args, note, model)

    monkeypatch.setattr(wk, "run", flaky)
    rep = weekly(monkeypatch, "--parallel", "1")
    assert not rep["ok"] and len(rep["queue"]) == 2 and len(rep["judges"]) == 4


def test_no_scan_at_all_exits_nonzero(repo, monkeypatch):
    bad = lambda *a, **k: {"run_id": "x", "failure": "timed out", "result": None}  # noqa: E731
    monkeypatch.setattr(wk, "run", bad)
    with pytest.raises(SystemExit):
        weekly(monkeypatch)


def test_guard_allows_outputs_and_refuses_everything_else():
    ok = ["candidates/claude/scan_2027-01-04.jsonl", "candidates/merged/queue_2027-01-04.jsonl"]
    ok += ["candidates/feeds/feeds_2027-01-04.jsonl", "evidence/youcom/x.jsonl"]
    ok += ["scorecards/claude/x.json", "registry/entries.jsonl", "reviews/judge.csv"]
    ok += ["runs/weekly_1.json", "runs/weekly_1.md", "runs/r.meta.json", "dashboard/reviews.js"]
    assert all(guard.allowed(p) for p in ok)
    bad = ["harness/baselines.py", "protocol-v2.yaml", "spec.yaml", "data/raw/x.csv"]
    bad += [".github/workflows/weekly.yml", "tools/ledger.py", "schemas/scorecard.schema.json"]
    bad += [".claude/skills/judge/SKILL.md", "runs/x.jsonl", "scorecards/claude/sub/x.json"]
    bad += [
        "registry/seed_manual.yaml",
        "dashboard/index.html",
        "evidence/raw/page.html",
        "CLAUDE.md",
    ]
    assert not any(guard.allowed(p) for p in bad)
