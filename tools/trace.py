"""How was this verdict reached? Print the searches, pages and reasoning of a run.

    uv run --project core python tools/trace.py timesfm-3              # a candidate id
    uv run --project core python tools/trace.py arxiv:2611.07784       # a registry key
    uv run --project core python tools/trace.py 20261114T174352_judge_youcom_timesfm-3_0c48
    uv run --project core python tools/trace.py timesfm-3 --provider youcom --full

For a candidate or a registry key it lists every recorded run about that work (judge
and run-candidate runs, under every candidate id the work has had), then prints each
run's steps in order: search queries, pages fetched, ledger rows added, files written,
what the agent said, and its final report. `--full` prints the agent's text unshortened.

Transcripts are read from runs/<run_id>.jsonl (git-ignored: they hold page text), or
from a checkout of the private archive named by RECEIPTS_ARCHIVE_DIR, where they are
transcripts/<year>/<run_id>.jsonl.gz. Tool results (the page text itself) are never
printed, only what was asked for.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import registry as rg  # noqa: E402


def metas(root: Path) -> list[dict]:
    out = []
    for p in sorted((root / "runs").glob("*.meta.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def runs_for(what: str, root: Path, provider: str = "") -> tuple[list[dict], str]:
    """The run records for a run id, a candidate id or a registry key, oldest first,
    and a line saying what was matched."""
    all_runs = metas(root)
    exact = [m for m in all_runs if m.get("run_id") == what]
    if exact:
        return exact, f"run {what}"
    reg = rg.Registry(root=root)
    key = reg.by_alias.get(what) or reg.by_cid.get(what)
    ids = set(reg.entries[key]["candidate_ids"]) if key else {what}
    stamped = set()
    for cid in ids:
        for p in (root / "scorecards").glob(f"*/{cid}.json"):
            rid = (json.loads(p.read_text()).get("provenance") or {}).get("run_id")
            if rid:
                stamped.add(rid)
    found = [
        m
        for m in all_runs
        if m.get("run_id") in stamped
        or (m.get("skill") in ("judge", "run-candidate") and (m.get("args") or [""])[0] in ids)
    ]
    if provider:
        found = [m for m in found if m.get("provider") == provider]
    found.sort(key=lambda m: m.get("started_at") or "")
    label = f"{key} (candidate ids: {', '.join(sorted(ids))})" if key else f"candidate {what}"
    return found, label


def transcript(run_id: str, root: Path) -> list[dict] | None:
    local = root / "runs" / f"{run_id}.jsonl"
    text = None
    if local.exists():
        text = local.read_text()
    elif os.environ.get("RECEIPTS_ARCHIVE_DIR"):
        hits = list(
            Path(os.environ["RECEIPTS_ARCHIVE_DIR"]).glob(f"transcripts/*/{run_id}.jsonl.gz")
        )
        if hits:
            text = gzip.decompress(hits[0].read_bytes()).decode()
    if text is None:
        return None
    out = []
    for line in text.splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(m, dict):
            out.append(m)
    return out


def short(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 3] + "..."


def describe(name: str, args: dict) -> str | None:
    """One line for a tool call, or None for a call not worth showing."""
    tool = name.split("__")[-1]
    if tool in ("WebSearch", "you-search"):
        return f"SEARCH   {args.get('query', '')}"
    if tool == "you-research":
        return f"RESEARCH {short(args.get('input') or args.get('query') or '', 300)}"
    if tool == "WebFetch":
        return f"FETCH    {args.get('url', '')}"
    if tool == "you-contents":
        urls = args.get("urls") or [args.get("url", "")]
        return "\n".join(f"FETCH    {u}" for u in urls)
    if tool == "Bash":
        cmd = args.get("command", "")
        if "ledger.py add" in cmd:
            return f"LEDGER   {short(cmd.split('ledger.py add', 1)[1], 400)}"
        return f"SHELL    {short(cmd, 200)}"
    if tool in ("Write", "Edit"):
        return f"WRITE    {args.get('file_path', '')}"
    if tool == "Read":
        return f"READ     {args.get('file_path', '')}"
    if tool in ("Task", "Agent"):
        return f"SUBAGENT {short(args.get('prompt') or args.get('description') or '', 300)}"
    return None


def steps(stream: list[dict], full: bool) -> list[str]:
    out = []
    for m in stream:
        if m.get("type") == "assistant":
            content = (m.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    text = block["text"].strip() if full else short(block["text"], 300)
                    out.append(f"SAID     {text}")
                elif block.get("type") == "tool_use":
                    line = describe(block.get("name", ""), block.get("input") or {})
                    if line:
                        out.append(line)
        elif m.get("type") == "result":
            out.append("REPORT   " + str(m.get("result") or "").strip())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", help="a candidate id, a registry key or a run id")
    ap.add_argument("--provider", default="", choices=["", "claude", "youcom"])
    ap.add_argument("--full", action="store_true", help="do not shorten the agent's text")
    ap.add_argument("--list", action="store_true", help="list the runs only")
    a = ap.parse_args()
    found, label = runs_for(a.what, ROOT, a.provider)
    print(f"{label}: {len(found)} recorded run(s)")
    if not found:
        sys.exit("no run record matches; scorecards from before run records have none")
    for m in found:
        cost = m.get("total_cost_usd")
        print(
            f"\n=== {m['run_id']}\n    {m.get('skill')} / {m.get('provider')}, started "
            f"{m.get('started_at')}, {m.get('num_turns')} turns, "
            f"{m.get('wall_seconds')} s, estimated ${cost}, commit {m.get('git_commit')}"
            + (f", FAILED: {m['failure']}" if m.get("failure") else "")
        )
        if a.list:
            continue
        stream = transcript(m["run_id"], ROOT)
        if stream is None:
            print(
                "    transcript not on this machine; set RECEIPTS_ARCHIVE_DIR to a checkout of "
                "the private archive"
            )
            continue
        for line in steps(stream, a.full):
            print("    " + line.replace("\n", "\n    "))


if __name__ == "__main__":
    main()
