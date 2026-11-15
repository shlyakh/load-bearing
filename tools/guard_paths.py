"""Fail if a weekly run changed anything outside the agent's output paths.

    uv run --project core python tools/guard_paths.py                  # working tree vs HEAD
    uv run --project core python tools/guard_paths.py --base origin/main   # a branch vs main

The weekly run (tools/weekly.py) may write candidates, evidence, scorecards, the
registry, the review sheets, run records and the review data of the dashboard. It may
not touch the harness, a protocol, the spec, the data, the skills, the tools, the
schemas or a workflow (decision 46). This is an allowlist: a path that is not listed
fails, whatever it is. Exit status 1 lists the offending paths.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED = [
    "candidates/*/*.jsonl",
    "evidence/claude/*.jsonl",
    "evidence/youcom/*.jsonl",
    "scorecards/claude/*.json",
    "scorecards/youcom/*.json",
    "registry/entries.jsonl",
    "reviews/*.csv",
    "runs/*.json",
    "runs/*.md",
    "dashboard/reviews.js",
]


def allowed(path: str) -> bool:
    # fnmatch's * crosses "/", so compare the number of path parts as well
    return any(
        fnmatch.fnmatchcase(path, pat) and path.count("/") == pat.count("/") for pat in ALLOWED
    )


def changed(base: str | None) -> list[str]:
    def git(*a: str) -> list[str]:
        r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True)
        return [x for x in r.stdout.splitlines() if x]

    if base:
        return git("diff", "--name-only", f"{base}...HEAD")
    tracked = git("diff", "--name-only", "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard")
    return sorted(set(tracked + untracked))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default=None, help="compare HEAD with this ref, not the working tree")
    a = ap.parse_args()
    bad = [p for p in changed(a.base) if not allowed(p)]
    if bad:
        print("Outside the weekly run's output paths:")
        for p in bad:
            print(f"  {p}")
        sys.exit(1)
    print("guard: every changed path is an allowed output path")


if __name__ == "__main__":
    main()
