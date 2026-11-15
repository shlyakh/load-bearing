"""Offline checks of the run id, the child environment and the narrowed shell rules.

uv run --project core pytest tests/test_run_ids.py -q
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.ledger as ledger  # noqa: E402
import tools.run_skill as rs  # noqa: E402
from tools.validate_scorecard import errors  # noqa: E402


def test_child_keeps_subscription_token_and_drops_api_keys(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "metered")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "metered")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = rs.child_env("claude", "run-1")
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
    assert "CLAUDE_CODE_ENTRYPOINT" not in env and "CLAUDECODE" not in env
    assert env[rs.RUN_ID_VAR] == "run-1"
    assert not rs.RUN_ID_VAR.startswith("CLAUDE")  # or the child would lose it


def test_scan_and_judge_get_named_scripts_only():
    for skill in ("scan", "judge"):
        tools = rs.common_tools(skill)
        bash = [t for t in tools if t.startswith("Bash(")]
        assert bash and "Bash(uv run:*)" not in tools
        scripts = [t for t in bash if t.startswith("Bash(uv ")]
        assert all(t.startswith("Bash(uv run --project core python tools/") for t in scripts)
        others = {t[5:].split(":")[0] for t in bash if t not in scripts}
        assert others == set(rs.READ_ONLY)
        assert not others & {"python", "python3", "sh", "bash", "curl", "env", "printenv", "git"}
        cmd = rs.command("claude", f"/{skill} claude", skill=skill)
        assert "Bash(uv run:*)" not in cmd
    assert "Bash(uv run --project core python tools/ledger.py:*)" in rs.common_tools("judge")
    assert "Bash(uv run:*)" in rs.common_tools("run-candidate")


def test_skill_commands_are_covered_by_the_shell_rules():
    """Every `uv run` line in the scan and judge skills starts with an allowed prefix."""
    import re

    for skill in ("scan", "judge"):
        text = (rs.ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text()
        allowed = [rs.UV_TOOL + s for s in rs.BASH_SCRIPTS[skill]]
        for cmd in re.findall(r"`(uv run [^`]+)`", text):
            assert any(cmd.startswith(a) for a in allowed), cmd


def test_ledger_row_carries_run_id(monkeypatch, tmp_path):
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    a = argparse.Namespace(
        url="https://example.org/a",
        title="t",
        published="unknown",
        note="n",
        provider="manual",
        candidate="x",
    )
    monkeypatch.setenv("RECEIPTS_RUN_ID", "run-7")
    ledger.add(a)
    monkeypatch.delenv("RECEIPTS_RUN_ID")
    a.note = "second"
    ledger.add(a)
    rows = [json.loads(x) for x in (tmp_path / "evidence/manual/x.jsonl").read_text().splitlines()]
    assert [r["run_id"] for r in rows] == ["run-7", "interactive"]


def test_stamp_provenance_only_touches_this_runs_scorecard(monkeypatch, tmp_path):
    src = sorted((rs.ROOT / "scorecards" / "claude").glob("*.json"))[0]
    card = json.loads(src.read_text())
    card.pop("provenance", None)
    folder = tmp_path / "scorecards" / "claude"
    folder.mkdir(parents=True)
    mine, other = folder / "mine.json", folder / "other.json"
    for p in (mine, other):
        p.write_text(json.dumps(card))
    old = time.time() - 3600
    os.utime(other, (old, old))
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    meta = {
        "provider": "claude",
        "args": ["mine"],
        "run_id": "r1",
        "session_id": "s",
        "cli_version": "v",
    }
    assert rs.stamp_provenance(meta, time.time() - 60) == ["scorecards/claude/mine.json"]
    stamped = json.loads(mine.read_text())
    assert stamped["provenance"]["run_id"] == "r1" and not errors(stamped)
    assert "provenance" not in json.loads(other.read_text())
