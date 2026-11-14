"""A failed step must be visible to whoever started the run. No claude run, no network.

uv run --project core pytest tests/test_pipeline_failures.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.pipeline as pl  # noqa: E402
import tools.run_skill as rs  # noqa: E402

OK = {"exit_code": 0, "timed_out": False, "is_error": False, "num_turns": 12}


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({}, None),
        ({"timed_out": True, "exit_code": -1}, "timed out"),
        ({"exit_code": 1}, "the CLI exited with status 1"),
        ({"is_error": True}, "the CLI reported an error"),
        ({"num_turns": None}, "the run ended without a result"),
    ],
)
def test_failure_reasons(change, reason):
    assert rs.failure(OK | change) == reason


def test_cli_exits_nonzero_when_the_run_failed(monkeypatch, capsys):
    meta = OK | {"exit_code": 1, "run_id": "r1", "total_cost_usd": 1.0, "result": ""}
    meta["failure"] = rs.failure(meta)
    monkeypatch.setattr(rs, "run", lambda *a, **k: meta)
    monkeypatch.setattr(sys, "argv", ["run_skill.py", "scan", "claude"])
    with pytest.raises(SystemExit) as stop:
        rs.main()
    assert "FAILED" in str(stop.value.code)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch repository with one older scan holding two candidates."""
    (tmp_path / "candidates" / "claude").mkdir(parents=True)
    (tmp_path / "scorecards" / "claude").mkdir(parents=True)
    (tmp_path / "runs").mkdir()
    rows = [{"candidate_id": "a"}, {"candidate_id": "b"}]
    (tmp_path / "candidates" / "claude" / "scan_old.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    monkeypatch.setattr(pl, "ROOT", tmp_path)
    return tmp_path


def fake_run(calls, fail):
    def run(skill, provider, args, note="", model=""):
        calls.append((skill, *args))
        meta = OK | {"run_id": f"{skill}-{'-'.join(args)}", "total_cost_usd": 1.0, "result": ""}
        if skill == "judge":  # a judge writes its scorecard, even one that is then cut off
            card = {"label": "ACCEPT_RUN", "runnable_class": "direct_adapter"}
            path = pl.ROOT / "scorecards" / provider / f"{args[0]}.json"
            path.write_text(json.dumps(card))
        if (skill, *args) in fail:
            meta |= {"exit_code": 1}
        return meta | {"failure": rs.failure(meta)}

    return run


def test_failed_scan_stops_before_judging(repo, monkeypatch):
    calls: list = []
    monkeypatch.setattr(pl, "run", fake_run(calls, fail={("scan",)}))
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "claude", "--scan"])
    with pytest.raises(SystemExit) as stop:
        pl.main()
    assert "scan FAILED" in str(stop.value.code)
    assert calls == [("scan",)]  # the older scan was not judged
    [record] = (repo / "runs").glob("pipeline_*.json")
    assert json.loads(record.read_text())["scan"]["failure"]


def test_failed_judge_gets_no_receipt_and_the_run_exits_nonzero(repo, monkeypatch):
    calls: list = []
    monkeypatch.setattr(pl, "run", fake_run(calls, fail={("judge", "a")}))
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "claude", "--judge", "2", "--parallel", "1"])
    # the failed judge leaves a scorecard behind; it must not be turned into a receipt
    with pytest.raises(SystemExit) as stop:
        pl.main()
    assert "1 step(s) FAILED" in str(stop.value.code) and "a judge" in str(stop.value.code)
    assert ("run-candidate", "b") in calls and ("run-candidate", "a") not in calls


def test_clean_run_exits_normally(repo, monkeypatch):
    calls: list = []
    monkeypatch.setattr(pl, "run", fake_run(calls, fail=set()))
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "claude", "--judge", "2", "--parallel", "1"])
    pl.main()
    assert [c for c in calls if c[0] == "judge"] == [("judge", "a"), ("judge", "b")]
