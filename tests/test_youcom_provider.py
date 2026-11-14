"""Offline checks of the youcom search provider. No You.com call, no claude run.

uv run --project core pytest tests/test_youcom_provider.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.run_skill as rs  # noqa: E402
from tools.compare_providers import compare  # noqa: E402

SENTINEL = "sentinel-not-a-real-key"


def flag_values(cmd: list[str], flag: str) -> list[str]:
    """The values after a variadic flag, up to the next flag."""
    if flag not in cmd:
        return []
    out = []
    for x in cmd[cmd.index(flag) + 1 :]:
        if x.startswith("--"):
            break
        out.append(x)
    return out


@pytest.fixture
def no_key(monkeypatch, tmp_path):
    """No key in the environment and an empty .env, whatever the real .env holds."""
    monkeypatch.delenv(rs.KEY_VAR, raising=False)
    empty = tmp_path / ".env"
    empty.write_text("OTHER=1\n")
    original = rs.youcom_key
    monkeypatch.setattr(rs, "youcom_key", lambda env_file=empty: original(env_file))

    def never(*a, **k):
        raise AssertionError("subprocess must not start without a key")

    monkeypatch.setattr(rs.subprocess, "run", never)
    return empty


def test_key_missing_refuses(no_key):
    with pytest.raises(SystemExit) as e:
        rs.youcom_key()
    assert rs.KEY_VAR in str(e.value)
    assert "OTHER" not in str(e.value)


def test_run_refuses_without_key_and_writes_nothing(no_key):
    before = set((rs.ROOT / "runs").glob("*"))
    with pytest.raises(SystemExit):
        rs.run("judge", "youcom", ["item-02"])
    assert set((rs.ROOT / "runs").glob("*")) == before


def test_key_read_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv(rs.KEY_VAR, raising=False)
    f = tmp_path / ".env"
    f.write_text(f"{rs.KEY_VAR}={SENTINEL}\n")
    assert rs.youcom_key(f) == SENTINEL


def test_mcp_config_shape():
    cfg = json.loads(rs.mcp_config())
    assert list(cfg["mcpServers"]) == ["you-com"]
    server = cfg["mcpServers"]["you-com"]
    assert server["type"] == "http"
    assert server["url"].startswith("https://api.you.com/mcp?tools=")
    assert set(server["url"].split("tools=")[1].split(",")) == {
        "you-search",
        "you-contents",
        "you-research",
    }
    assert server["headers"] == {"Authorization": "Bearer ${YDC_API_KEY}"}


def test_config_is_inline_and_key_never_in_argv(monkeypatch):
    monkeypatch.setenv(rs.KEY_VAR, SENTINEL)
    cmd = rs.command("youcom", "/judge item-02 youcom")
    assert all(SENTINEL not in x for x in cmd)
    value = flag_values(cmd, "--mcp-config")
    assert len(value) == 1
    json.loads(value[0])  # inline JSON, not a path to a file
    assert not (rs.ROOT / value[0][:200]).exists()
    assert rs.child_env("youcom")[rs.KEY_VAR] == SENTINEL  # only the child sees it


def test_youcom_tools_exclude_claude_search():
    cmd = rs.command("youcom", "/scan youcom")
    allowed = flag_values(cmd, "--allowedTools")
    assert "WebSearch" not in allowed and "WebFetch" not in allowed
    assert set(allowed) - set(rs.COMMON) == {
        "mcp__you-com__you-search",
        "mcp__you-com__you-contents",
        "mcp__you-com__you-research",
    }
    assert set(flag_values(cmd, "--disallowedTools")) == {"WebSearch", "WebFetch"}
    assert "--strict-mcp-config" in cmd


def test_claude_provider_unchanged():
    cmd = rs.command("claude", "/scan claude")
    assert flag_values(cmd, "--allowedTools") == rs.COMMON + ["WebSearch", "WebFetch"]
    assert "--mcp-config" not in cmd and "--disallowedTools" not in cmd


def test_parse_records_mcp_status(tmp_path):
    stream = tmp_path / "s.jsonl"
    lines = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["Read", "mcp__you-com__you-search"],
            "mcp_servers": [{"name": "you-com", "status": "connected"}],
        },
        {"message": {"content": [{"type": "tool_use", "name": "mcp__you-com__you-search"}]}},
        {"type": "result", "result": "ok", "total_cost_usd": 0.01},
    ]
    stream.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    result, tools, init = rs.parse(stream)
    assert result["result"] == "ok"
    assert tools == {"mcp__you-com__you-search": 1}
    assert init["mcp_servers"] == [{"name": "you-com", "status": "connected"}]
    assert init["search_tools_present"] == ["mcp__you-com__you-search"]


def test_compare_on_repo_data():
    table = compare()
    claude = {p.stem for p in (rs.ROOT / "scorecards" / "claude").glob("*.json")}
    assert claude <= {r["candidate_id"] for r in table}
    for r in table:
        if r["label_youcom"] == "":
            assert r["agree"] == ""


def test_compare_both_providers(tmp_path):
    for prov, label in (("claude", "ACCEPT_RUN"), ("youcom", "PARTIAL")):
        (tmp_path / "scorecards" / prov).mkdir(parents=True)
        card = {"label": label, "runnable_class": "not_runnable", "primary_sources": [{}, {}]}
        (tmp_path / "scorecards" / prov / "x.json").write_text(json.dumps(card))
        (tmp_path / "evidence" / prov).mkdir(parents=True)
        (tmp_path / "evidence" / prov / "x.jsonl").write_text("{}\n{}\n{}\n")
    (tmp_path / "runs").mkdir()
    meta = {
        "skill": "judge",
        "provider": "youcom",
        "args": ["x"],
        "started_at": "2026-11-14T12:00:00+00:00",
        "total_cost_usd": 0.5,
        "wall_seconds": 60.0,
        "tool_calls": {"mcp__you-com__you-research": 1, "mcp__you-com__you-contents": 2},
    }
    (tmp_path / "runs" / "a.meta.json").write_text(json.dumps(meta))
    [row] = compare(tmp_path)
    assert row["agree"] == "no"
    assert row["primary_sources_youcom"] == 2 and row["ledger_rows_claude"] == 3
    assert row["judge_cost_usd_youcom"] == 0.5 and row["provider_tool_calls_youcom"] == 3
    assert row["judge_cost_usd_claude"] == ""
