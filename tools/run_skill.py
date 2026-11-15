"""Run one skill headless and keep the full record of the run.

    uv run --project core python tools/run_skill.py scan claude
    uv run --project core python tools/run_skill.py judge claude item-02
    uv run --project core python tools/run_skill.py judge youcom item-02
    uv run --project core python tools/run_skill.py smoke youcom      # one contents call
    uv run --project core python tools/run_skill.py scan claude --note "write to ..._run3"

Starts `claude -p "/<skill> <args> <provider>"` in this repository and writes
  runs/<run_id>.jsonl      every message, tool call, search and fetch (git-ignored: it
                           holds page text)
  runs/<run_id>.meta.json  provider, skill, arguments, git commit, session id, turns,
                           tokens, estimated cost, duration, the provider tools that were
                           allowed and denied (names only) (committed)
The child sees the run id as RECEIPTS_RUN_ID, so tools/ledger.py stamps it on every
evidence row, and a judge run's scorecard gets a `provenance` block naming the run.

Authentication. The child keeps CLAUDE_CODE_OAUTH_TOKEN (the subscription token from
`claude setup-token`, the only login a CI runner has) and loses ANTHROPIC_API_KEY and
ANTHROPIC_AUTH_TOKEN, which would take precedence and bill a metered key (decision 43).
Every other CLAUDE* variable is dropped, as before, so a run started from inside a
Claude Code session does not inherit that session's settings.

Shell access. A scan or judge run may start only the tool scripts its skill names
(BASH_SCRIPTS), not any `uv run` command: the agent reads web pages, so its shell is
kept narrow. run-candidate keeps `uv run` because a person-supervised run starts models.

The provider decides which search tools the run may use:
  claude   WebSearch and WebFetch.
  youcom   the hosted You.com MCP server only, as server `you-com`. WebSearch and
           WebFetch are denied (the user settings pre-approve WebSearch, so allowing
           alone would not stop a fallback) and --strict-mcp-config keeps every other
           MCP server out. The config is passed inline with the header
           `Authorization: Bearer ${YDC_API_KEY}`: the CLI expands the variable from the
           child's environment, so the key is in no file, no argument and no metadata.
           YDC_API_KEY comes from the environment or `.env`; without it the run refuses.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FILE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Skill"]
COMMON = [*FILE_TOOLS, "Bash(uv run:*)"]  # run-candidate, and any skill not listed below
UV_TOOL = "uv run --project core python tools/"
BASH_SCRIPTS = {
    "scan": ["feeds.py", "ledger.py", "registry.py"],
    "judge": ["ledger.py", "validate_scorecard.py", "registry.py"],
    "smoke": [],
}
RUN_ID_VAR = "RECEIPTS_RUN_ID"
KEEP_ENV = {"CLAUDE_CODE_OAUTH_TOKEN"}
DROP_ENV = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}

YOUCOM_SERVER = "you-com"
YOUCOM_TOOLS = ["you-search", "you-contents", "you-research"]
# you-research is off on the hosted server unless requested with ?tools= (notes/hackathon_tools.md).
YOUCOM_URL = "https://api.you.com/mcp?tools=" + ",".join(YOUCOM_TOOLS)
KEY_VAR = "YDC_API_KEY"

TOOLS = {
    "claude": ["WebSearch", "WebFetch"],
    "youcom": [f"mcp__{YOUCOM_SERVER}__{t}" for t in YOUCOM_TOOLS],
}
DENIED = {"claude": [], "youcom": ["WebSearch", "WebFetch"]}

SMOKE_URL = "https://zenodo.org/records/24161799"
SMOKE_PROMPT = (
    f"Smoke test of the search provider. Call mcp__{YOUCOM_SERVER}__you-contents exactly "
    f"once on {SMOKE_URL}. Do not call any other tool and do not write any file. Reply in "
    "three lines: the page title, the record's publication date if shown, and the list of "
    f"mcp__{YOUCOM_SERVER}__ tools available in this session."
)


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def youcom_key(env_file: Path = ROOT / ".env") -> str:
    """YDC_API_KEY from the environment, else from .env. Exits if missing. The value is
    returned to the caller only, never printed."""
    key = os.environ.get(KEY_VAR, "").strip()
    if not key and env_file.exists():
        from dotenv import dotenv_values

        key = (dotenv_values(env_file).get(KEY_VAR) or "").strip()
    if not key:
        sys.exit(
            f"provider youcom needs {KEY_VAR}: add it to .env (see .env.example and "
            "notes/youcom_provider.md). Nothing was run."
        )
    return key


def mcp_config() -> str:
    """Inline MCP config for the hosted You.com server. Holds the placeholder
    ${YDC_API_KEY}, never the key: the CLI expands it from the child's environment."""
    server = {
        "type": "http",
        "url": YOUCOM_URL,
        "headers": {"Authorization": "Bearer ${" + KEY_VAR + "}"},
    }
    return json.dumps({"mcpServers": {YOUCOM_SERVER: server}})


def common_tools(skill: str = "") -> list[str]:
    """File tools plus the shell commands this skill may start."""
    if skill not in BASH_SCRIPTS:
        return COMMON
    return [*FILE_TOOLS, *(f"Bash({UV_TOOL}{s}:*)" for s in BASH_SCRIPTS[skill])]


def command(provider: str, prompt: str, model: str = "", skill: str = "") -> list[str]:
    """The headless CLI call for one run."""
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
    cmd += ["--allowedTools", *common_tools(skill), *TOOLS[provider]]
    if DENIED[provider]:
        cmd += ["--disallowedTools", *DENIED[provider]]
    if provider == "youcom":
        cmd += ["--strict-mcp-config", "--mcp-config", mcp_config()]
    if model:
        cmd += ["--model", model]
    return cmd


def child_env(provider: str, run_id: str = "") -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k in KEEP_ENV or not (k.startswith("CLAUDE") or k in DROP_ENV)
    }
    if provider == "youcom":
        env[KEY_VAR] = youcom_key()
    if run_id:
        env[RUN_ID_VAR] = run_id
    return env


def cli_version() -> str | None:
    try:
        out = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def with_key(text: str, key: str, value: dict) -> str:
    """The JSON object in `text` with one more top-level key, leaving every existing line
    as it was (scorecards are written by agents with differing indentation). A key that
    is already present means a full rewrite."""
    card = json.loads(text)
    body = text.rstrip()
    lines = body.splitlines()
    if key in card or len(lines) < 3 or not body.endswith("}"):
        return json.dumps(card | {key: value}, indent=1) + "\n"
    pad = lines[1][: len(lines[1]) - len(lines[1].lstrip())]
    block = json.dumps(value, indent=len(pad) or 1).replace("\n", "\n" + pad)
    out = body[:-1].rstrip() + f',\n{pad}"{key}": {block}\n}}\n'
    assert json.loads(out) == card | {key: value}
    return out


def stamp_provenance(meta: dict, since: float) -> list[str]:
    """Write the run's id into the scorecard a judge run produced. The scorecard is the
    one named after the first argument; when the argument was a URL, any scorecard of this
    provider written since the run started that carries no provenance yet. A scorecard
    that would become invalid is left alone. Returns the paths stamped."""
    from tools.validate_scorecard import errors

    folder = ROOT / "scorecards" / meta["provider"]
    named = folder / f"{meta['args'][0]}.json" if meta["args"] else None
    if named is not None and named.exists():
        paths = [named] if named.stat().st_mtime >= since else []
    else:
        paths = [p for p in folder.glob("*.json") if p.stat().st_mtime >= since]
    done = []
    for p in paths:
        try:
            card = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(card, dict) or (named is None and card.get("provenance")):
            continue
        card["provenance"] = {
            "run_id": meta["run_id"],
            "session_id": meta.get("session_id"),
            "cli_version": meta.get("cli_version"),
        }
        if errors(card):
            continue
        p.write_text(with_key(p.read_text(), "provenance", card["provenance"]))
        done.append(str(p.relative_to(ROOT)))
    return done


def parse(stream: Path) -> tuple[dict, dict, dict]:
    """The final result line, a count of tool calls, and from the init line the MCP
    server status and the provider tools that were present, from a saved stream."""
    result, tools, init = {}, {}, {}
    for line in stream.read_text().splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(m, dict):
            continue
        if m.get("type") == "result":
            result = m
        if m.get("type") == "system" and m.get("subtype") == "init" and not init:
            present = m.get("tools") or []
            init = {
                "mcp_servers": [
                    {"name": s.get("name"), "status": s.get("status")}
                    for s in m.get("mcp_servers") or []
                    if isinstance(s, dict)
                ],
                "search_tools_present": sorted(
                    t for t in present if t in ("WebSearch", "WebFetch") or t.startswith("mcp__")
                ),
            }
        message = m.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools[block["name"]] = tools.get(block["name"], 0) + 1
    return result, tools, init


def failure(meta: dict) -> str | None:
    """Why a run did not finish properly, or None when it did. A run counts as failed when
    the CLI timed out, exited nonzero, reported an error, or ended without a result line
    (for example when it was cut off by a usage limit)."""
    if meta.get("timed_out"):
        return "timed out"
    if meta.get("exit_code") != 0:
        return f"the CLI exited with status {meta.get('exit_code')}"
    if meta.get("is_error"):
        return "the CLI reported an error"
    if meta.get("num_turns") is None:
        return "the run ended without a result"
    return None


def run(
    skill: str, provider: str, args: list[str], note: str = "", model: str = "", timeout: int = 3600
) -> dict:
    """Run one skill headless, save the stream and the metadata, return the metadata
    (with the final message under "result")."""
    if provider not in TOOLS:
        sys.exit(f"unknown provider {provider}")
    if skill == "smoke" and provider != "youcom":
        sys.exit("smoke tests the youcom provider only")
    env = child_env(provider)  # refuses youcom without a key, before anything is written
    started = datetime.now(UTC)
    since = time.time()
    # The first argument and a random suffix keep runs started in the same second apart.
    what = "".join(c if c.isalnum() else "-" for c in (args[0] if args else "all"))[:40]
    run_id = f"{started:%Y%m%dT%H%M%S}_{skill}_{provider}_{what}_{secrets.token_hex(2)}"
    if skill == "smoke":
        prompt = SMOKE_PROMPT
    else:
        prompt = " ".join([f"/{skill}", *args, provider]) + (f"\n\n{note}" if note else "")
    env[RUN_ID_VAR] = run_id
    cmd = command(provider, prompt, model, skill)
    stream = ROOT / "runs" / f"{run_id}.jsonl"
    stream.parent.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    timed_out = False
    with stream.open("w") as f:
        try:
            code = subprocess.run(
                cmd,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=subprocess.PIPE,
                env=env,
                timeout=timeout,
            ).returncode
        except subprocess.TimeoutExpired:
            code, timed_out = -1, True
    result, tools, init = parse(stream)
    dirty = "-dirty" if git("status", "--porcelain", "--untracked-files=no") else ""
    meta = {
        "run_id": run_id,
        "skill": skill,
        "provider": provider,
        "args": args,
        "note": note,
        "model_requested": model or None,
        "provider_tools_allowed": TOOLS[provider],
        "provider_tools_denied": DENIED[provider],
        "mcp_server": {"name": YOUCOM_SERVER, "url": YOUCOM_URL} if provider == "youcom" else None,
        **init,
        "git_commit": git("rev-parse", "--short", "HEAD") + dirty,
        "cli_version": cli_version(),
        "started_at": started.isoformat(timespec="seconds"),
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "exit_code": code,
        "timed_out": timed_out,
        "session_id": result.get("session_id"),
        "is_error": result.get("is_error"),
        "num_turns": result.get("num_turns"),
        "total_cost_usd": result.get("total_cost_usd"),  # the client's estimate; no You.com charges
        "usage": result.get("usage"),
        "model_usage": result.get("modelUsage"),
        "tool_calls": tools,
    }
    meta["failure"] = failure(meta)
    if skill == "judge" and not meta["failure"]:
        meta["scorecards_stamped"] = stamp_provenance(meta, since)
    (ROOT / "runs" / f"{run_id}.meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    if provider == "youcom":
        status = {s["name"]: s["status"] for s in init.get("mcp_servers", [])}
        if status.get(YOUCOM_SERVER) != "connected":
            print(
                f"WARNING: MCP server {YOUCOM_SERVER} was {status.get(YOUCOM_SERVER)!r}, "
                "so the run had no search tools",
                file=sys.stderr,
            )
    return {**meta, "result": result.get("result")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill", choices=["scan", "judge", "run-candidate", "smoke"])
    ap.add_argument("provider", choices=sorted(TOOLS))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--note", default="", help="extra instruction appended to the prompt")
    ap.add_argument("--model", default="", help="model for the run; default is the CLI's own")
    a = ap.parse_args()
    meta = run(a.skill, a.provider, a.args, a.note, a.model)
    print(json.dumps({k: meta[k] for k in ("run_id", "exit_code", "num_turns", "total_cost_usd")}))
    if meta["result"]:
        print(meta["result"])
    if meta["failure"]:  # so a shell, a scheduler or a pipeline sees the failure
        sys.exit(f"{meta['run_id']} FAILED: {meta['failure']}")


if __name__ == "__main__":
    main()
