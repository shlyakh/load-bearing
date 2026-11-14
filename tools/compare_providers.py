"""Compare the judge under two search providers, candidate by candidate.

    uv run --project core python tools/compare_providers.py

Reads scorecards/<provider>/<id>.json, evidence/<provider>/<id>.jsonl and the judge runs
in runs/*.meta.json (matched by skill, provider and candidate id; the latest run wins).
Writes results/provider_comparison.csv and prints it. A candidate judged under one
provider only gets empty columns for the other and an empty `agree`.

`judge_cost_usd` is the client's estimate of model cost; it does not include search
charges by You.com. `provider_tool_calls` counts the provider's search, fetch and
research calls in that run.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.run_skill import TOOLS  # noqa: E402

PROVIDERS = ("claude", "youcom")
FIELDS = [
    "label",
    "runnable_class",
    "primary_sources",
    "ledger_rows",
    "judge_cost_usd",
    "judge_wall_seconds",
    "provider_tool_calls",
]


def judge_runs(root: Path) -> dict[tuple[str, str], dict]:
    """Latest judge run per (provider, candidate id)."""
    out: dict[tuple[str, str], dict] = {}
    for p in sorted((root / "runs").glob("*.meta.json")):
        try:
            m = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if m.get("skill") != "judge" or not m.get("args"):
            continue
        key = (m.get("provider"), m["args"][0])
        if key not in out or (m.get("started_at") or "") >= (out[key].get("started_at") or ""):
            out[key] = m
    return out


def side(root: Path, provider: str, cid: str, runs: dict) -> dict:
    card_path = root / "scorecards" / provider / f"{cid}.json"
    if not card_path.exists():
        return {f: "" for f in FIELDS}
    card = json.loads(card_path.read_text())
    ledger = root / "evidence" / provider / f"{cid}.jsonl"
    rows = sum(1 for x in ledger.read_text().splitlines() if x.strip()) if ledger.exists() else 0
    m = runs.get((provider, cid), {})
    calls = m.get("tool_calls") or {}
    cost = m.get("total_cost_usd")
    return {
        "label": card.get("label", ""),
        "runnable_class": card.get("runnable_class", ""),
        "primary_sources": len(card.get("primary_sources") or []),
        "ledger_rows": rows,
        "judge_cost_usd": "" if cost is None else round(cost, 4),
        "judge_wall_seconds": m.get("wall_seconds", ""),
        "provider_tool_calls": sum(calls.get(t, 0) for t in TOOLS[provider]) if m else "",
    }


def compare(root: Path = ROOT) -> list[dict]:
    ids = sorted(
        {p.stem for prov in PROVIDERS for p in (root / "scorecards" / prov).glob("*.json")}
    )
    runs = judge_runs(root)
    table = []
    for cid in ids:
        sides = {prov: side(root, prov, cid, runs) for prov in PROVIDERS}
        a, b = (sides[p]["label"] for p in PROVIDERS)
        row = {"candidate_id": cid}
        for f in FIELDS:
            for prov in PROVIDERS:
                row[f"{f}_{prov}"] = sides[prov][f]
            if f == "label":
                row["agree"] = ("yes" if a == b else "no") if a and b else ""
        table.append(row)
    return table


def main() -> None:
    table = compare()
    cols = ["candidate_id"] + [
        c
        for f in FIELDS
        for c in [f"{f}_{p}" for p in PROVIDERS] + (["agree"] if f == "label" else [])
    ]
    out = ROOT / "results" / "provider_comparison.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(table)
    w = csv.DictWriter(sys.stdout, fieldnames=cols)
    w.writeheader()
    w.writerows(table)
    both = [r for r in table if r["agree"]]
    agreed = sum(r["agree"] == "yes" for r in both)
    print(f"\n{len(table)} candidates, {len(both)} judged under both, {agreed} agree. Wrote {out}")


if __name__ == "__main__":
    main()
