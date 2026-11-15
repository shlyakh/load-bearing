"""Combine the latest scan of every provider into one candidate list.

    uv run --project core python tools/merge_candidates.py [--date YYYY-MM-DD]

Reads the newest candidates/<provider>/scan_*.jsonl of each provider (claude, youcom)
and writes candidates/merged/scan_<date>.jsonl. Two candidates are the same claim when
their primary URLs match after normalising (scheme, `www.`, trailing slash, arXiv
version and abs/pdf form) or when their titles match exactly ignoring case and spaces.
A claim found under two different primary URLs and two different titles stays as two
rows; `possible_duplicates` in the report lists rows that share a secondary URL.

Each merged row keeps the fields of a scan row and adds:
  found_by       providers whose scan kept it
  ranks          its position in each of those scans (1 = closest to the spec)
  ids            its candidate_id in each scan
  from_listing   true when any scan found it through a direct listing (tools/feeds.py)
The row's own candidate_id is the one that already has a scorecard, if any, so judged
claims are not judged again under a second name; otherwise the first provider's.

Order: by best rank in any scan; ties go to the claim more scans found, then to the
better rank in the other scan. `tools/pipeline.py <provider> --candidates-from merged`
judges from this list.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.keys import norm_title, norm_url  # noqa: E402

PROVIDERS = ("claude", "youcom")


def scan_order(path: Path) -> tuple[str, int]:
    """Sort key for scan_<date>[_run<N>].jsonl: the date, then the run number. The file
    time is not used: on a fresh clone every file has the same one."""
    m = re.match(r"scan_(\d{4}-\d{2}-\d{2})(?:_run(\d+))?$", path.stem)
    return (m.group(1), int(m.group(2) or 1)) if m else ("", 0)


def latest(root: Path, provider: str) -> Path | None:
    files = sorted((root / "candidates" / provider).glob("scan_*.jsonl"), key=scan_order)
    return files[-1] if files else None


def has_scorecard(root: Path, cid: str) -> bool:
    return any((root / "scorecards" / p / f"{cid}.json").exists() for p in PROVIDERS)


def merge(scans: dict[str, list[dict]], root: Path = ROOT) -> list[dict]:
    """scans: provider -> rows in scan order. Returns merged rows, best first."""
    groups: list[dict] = []
    by_key: dict[str, dict] = {}
    for provider, rows in scans.items():
        for rank, row in enumerate(rows, start=1):
            keys = ["u:" + norm_url(row["primary_url"]), "t:" + norm_title(row["title"])]
            group = next((by_key[k] for k in keys if k in by_key), None)
            if group is None:
                group = {"rows": {}, "ranks": {}}
                groups.append(group)
            for k in keys:
                by_key.setdefault(k, group)
            if provider not in group["rows"]:  # a scan listing one claim twice: keep the first
                group["rows"][provider] = row
                group["ranks"][provider] = rank
    out = []
    for g in groups:
        ids = {p: r["candidate_id"] for p, r in g["rows"].items()}
        judged = [i for i in ids.values() if has_scorecard(root, i)]
        first = next(iter(g["rows"].values()))
        base = next((r for r in g["rows"].values() if r["candidate_id"] in judged), first)
        others = {
            u for r in g["rows"].values() for u in [r["primary_url"], *(r.get("other_urls") or [])]
        }
        out.append(
            dict(base)
            | {
                "other_urls": sorted(others - {base["primary_url"]}),
                "found_by": list(g["rows"]),
                "ranks": g["ranks"],
                "ids": ids,
                "from_listing": any("feed:" in (r.get("query") or "") for r in g["rows"].values()),
            }
        )
    out.sort(
        key=lambda r: (min(r["ranks"].values()), -len(r["found_by"]), sum(r["ranks"].values()))
    )
    return out


def possible_duplicates(rows: list[dict]) -> list[tuple[str, str]]:
    """Pairs of merged rows that share any URL: likely one claim under two primary URLs."""
    seen: dict[str, str] = {}
    pairs = []
    for r in rows:
        for u in {norm_url(x) for x in [r["primary_url"], *r["other_urls"]]}:
            if u in seen and seen[u] != r["candidate_id"]:
                pairs.append((seen[u], r["candidate_id"]))
            seen.setdefault(u, r["candidate_id"])
    return sorted(set(pairs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument(
        "--files", nargs="+", default=[], help="scan files to merge (candidates/<provider>/...)"
    )
    ap.add_argument("--out", default="", help="output path; default candidates/merged/scan_<date>")
    a = ap.parse_args()
    given = {Path(f).resolve().parent.name: Path(f).resolve() for f in a.files}
    scans, sources = {}, {}
    for p in PROVIDERS:
        f = given.get(p) if a.files else latest(ROOT, p)
        if f:
            scans[p] = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
            sources[p] = str(f.relative_to(ROOT))
    if not scans:
        raise SystemExit("no scan files under candidates/")
    rows = merge(scans)
    out = (
        Path(a.out).resolve() if a.out else ROOT / "candidates" / "merged" / f"scan_{a.date}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    both = sum(1 for r in rows if len(r["found_by"]) > 1)
    print(f"sources: {sources}")
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)} claims, {both} found by more than one scan")
    for p in scans:
        only = sum(1 for r in rows if r["found_by"] == [p])
        print(f"  only {p}: {only}")
    judged = sum(1 for r in rows if has_scorecard(ROOT, r["candidate_id"]))
    print(f"  already judged: {judged}")
    for a_id, b_id in possible_duplicates(rows):
        print(f"  possible duplicate (shared URL): {a_id} / {b_id}")


if __name__ == "__main__":
    main()
