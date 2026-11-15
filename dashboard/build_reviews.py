"""Export the review sheets and the registry for the dashboard's Review tab.

    uv run --project core python dashboard/build_reviews.py

Reads only committed files (reviews/*.csv, registry/entries.jsonl, scorecards/), so it
runs on a fresh clone and in the weekly workflow, unlike build_data.py, which needs the
git-ignored processed data. Writes dashboard/reviews.js (window.REVIEWS).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import registry as rg  # noqa: E402
from tools import reviews as rv  # noqa: E402

CHECKS = ("claim_ok", "sources_ok", "relevance_ok", "runnable_ok")


def judge_row(r: dict, root: Path) -> dict:
    path = root / r["scorecard"]
    card = json.loads(path.read_text()) if path.exists() else {}
    keep = ("key", "provider", "candidate_id", "title", "run_id", "scorecard", "label")
    keep += ("runnable_class", "evidence_strength", "relevance", "stale", "verdict")
    keep += ("corrected_label", "reason", *CHECKS, "reviewed_at", "note_public")
    return {k: r.get(k, "") for k in keep} | {
        "reviewed": rv.reviewed("judge", r),
        "label_reason": card.get("label_reason", ""),
        "claims": [c.get("text", "") for c in card.get("claims") or []][:4],
        "sources": [
            {"url": s["url"], "kind": s.get("kind", "")} for s in card.get("primary_sources") or []
        ],
        "receipt_verdict": (card.get("receipt") or {}).get("verdict", ""),
    }


def build(root: Path | None = None) -> dict:
    root = root or ROOT
    judge = [judge_row(r, root) for r in rv.read("judge", root)]
    scan = rv.read("scan", root)
    receipt = rv.read("receipt", root)
    relevant = {r["key"]: r.get("human_relevant", "") for r in scan}
    entries = [
        {
            "key": e["key"],
            "title": e["title"],
            "url": e["primary_url"],
            "kind": e["kind"],
            "status": e["status"],
            "labels": e["status_detail"].get("labels") or {},
            "models": e["status_detail"].get("leaderboard_models") or [],
            "first_seen": (e["first_seen"] or {}).get("date"),
            "last_seen": (e["last_seen"] or {}).get("date"),
            "queue": (e["queue"] or {}).get("reason"),
            "relations": [{"type": x["type"], "target": x["target"]} for x in e["relations"]],
            "note": e["notes_public"],
            "human_relevant": relevant.get(e["key"], ""),
        }
        for e in rg.load(root).values()
    ]
    count = lambda name, rows: sum(1 for r in rows if rv.reviewed(name, r))  # noqa: E731
    return {
        "counts": {
            "scan": [count("scan", scan), len(scan)],
            "judge": [sum(1 for r in judge if r["reviewed"]), len(judge)],
            "receipt": [count("receipt", receipt), len(receipt)],
            "disagree": sum(1 for r in judge if r["verdict"] == "disagree"),
            "stale": sum(1 for r in judge if r["stale"] == "yes"),
            "works": len(entries),
        },
        "judge": judge,
        "registry": entries,
    }


def main() -> None:
    data = build()
    out = ROOT / "dashboard" / "reviews.js"
    out.write_text("window.REVIEWS = " + json.dumps(data, ensure_ascii=False) + ";\n")
    n, m = len(data["judge"]), len(data["registry"])
    print(f"wrote {out.relative_to(ROOT)}: {n} scorecards, {m} works")


if __name__ == "__main__":
    main()
