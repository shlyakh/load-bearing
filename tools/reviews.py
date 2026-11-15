"""Yuri's review sheets: one CSV per stage, filled in by hand.

    uv run --project core python tools/reviews.py sync        # add new rows, refresh the left side
    uv run --project core python tools/reviews.py check       # are the hand-filled cells valid?
    uv run --project core python tools/reviews.py agreement   # how often the judge and Yuri agree

Files (decision 47), each with the agent's columns on the left and Yuri's on the right:

  reviews/scan.csv     one row per work a scan kept (registry key)
      yours: human_relevant (y / n / unsure), human_duplicate_of (a registry key), reason
  reviews/judge.csv    one row per scorecard (registry key + provider + candidate id)
      yours: verdict (agree / disagree / unsure), corrected_label (only if you disagree),
             reason, and four checks, each y or n:
               claim_ok      the claim was extracted correctly
               sources_ok    the sources are the right primary ones
               relevance_ok  the relevance scores are fair
               runnable_ok   the runnable class is right
  reviews/receipt.csv  one row per receipt (registry key + provider + candidate id)
      yours: verdict_ok (y / n), wording_ok (y / n), reason
  every sheet ends with: reviewed_by, reviewed_at (YYYY-MM-DD), note_public

`sync` never changes or deletes a cell on your side and never deletes a row. It rewrites
the agent's columns from the registry and the scorecards and appends rows for anything
new. If a scorecard changes after you reviewed it, the row's `stale` becomes `yes`; it
stays `yes` until you clear it. Leave a cell empty for "not reviewed yet".

The 11 blind labels in eval/items.yaml stay the ground truth for those items (decision
19). When `label_yuri` is filled there and the judge row is still empty, `sync` copies
it across as a verdict; it never copies in the other direction, and /judge must not
read this folder. These sheets are public; private notes go in the private repo under
the same registry key.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import registry as rg  # noqa: E402

PROVIDERS = ("claude", "youcom")
LABELS = ("ACCEPT_RUN", "ACCEPT_STAGE3", "PARTIAL", "REJECT")
VERDICTS = ("transfers", "partially", "does_not_transfer", "untestable")
YN = ("y", "n")
TAIL = ["reviewed_by", "reviewed_at", "note_public"]

SHEETS = {
    "scan": {
        "key": ["key"],
        "machine": [
            "key",
            "title",
            "url",
            "published_at",
            "kind",
            "candidate_ids",
            "first_seen",
            "last_seen",
            "status",
        ],
        "human": ["human_relevant", "human_duplicate_of", "reason", *TAIL],
    },
    "judge": {
        "key": ["key", "provider", "candidate_id"],
        "machine": [
            "key",
            "provider",
            "candidate_id",
            "title",
            "run_id",
            "scorecard",
            "scorecard_sha",
            "label",
            "runnable_class",
            "evidence_strength",
            "relevance",
            "n_sources",
            "stale",
        ],
        "human": [
            "verdict",
            "corrected_label",
            "reason",
            "claim_ok",
            "sources_ok",
            "relevance_ok",
            "runnable_ok",
            *TAIL,
        ],
    },
    "receipt": {
        "key": ["key", "provider", "candidate_id"],
        "machine": [
            "key",
            "provider",
            "candidate_id",
            "title",
            "scorecard",
            "model",
            "protocol_version",
            "receipt_verdict",
            "measured",
            "n_windows",
            "n_windows_after_weights",
        ],
        "human": ["verdict_ok", "wording_ok", "reason", *TAIL],
    },
}
ALLOWED = {
    "human_relevant": ("y", "n", "unsure"),
    "verdict": ("agree", "disagree", "unsure"),
    "corrected_label": LABELS,
    "claim_ok": YN,
    "sources_ok": YN,
    "relevance_ok": YN,
    "runnable_ok": YN,
    "verdict_ok": YN,
    "wording_ok": YN,
}
REVIEW_CELLS = {  # a row counts as reviewed when any of these is filled
    "scan": ["human_relevant"],
    "judge": ["verdict", "claim_ok", "sources_ok", "relevance_ok", "runnable_ok"],
    "receipt": ["verdict_ok", "wording_ok"],
}


def sheet_path(name: str, root: Path) -> Path:
    return root / "reviews" / f"{name}.csv"


def read(name: str, root: Path) -> list[dict]:
    p = sheet_path(name, root)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]


def write(name: str, rows: list[dict], root: Path) -> None:
    cols = SHEETS[name]["machine"] + SHEETS[name]["human"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    p = sheet_path(name, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(buf.getvalue(), encoding="utf-8")


def reviewed(name: str, row: dict) -> bool:
    return any(row.get(c) for c in REVIEW_CELLS[name])


def scorecards(reg: rg.Registry) -> list[tuple[dict, str, Path, dict]]:
    """(entry, provider, path, card) for every scorecard the registry knows."""
    out = []
    for e in reg.entries.values():
        for rel in e["status_detail"].get("scorecards") or []:
            p = reg.root / rel
            out.append((e, p.parent.name, p, json.loads(p.read_text())))
    return out


def scan_rows(reg: rg.Registry) -> list[dict]:
    return [
        {
            "key": e["key"],
            "title": e["title"],
            "url": e["primary_url"] or "",
            "published_at": e["published_at"] or "",
            "kind": e["kind"],
            "candidate_ids": " ".join(e["candidate_ids"]),
            "first_seen": (e["first_seen"] or {}).get("date", ""),
            "last_seen": (e["last_seen"] or {}).get("date", ""),
            "status": e["status"],
        }
        for e in reg.entries.values()
        if e["candidate_ids"]
    ]


def judge_rows(reg: rg.Registry) -> list[dict]:
    out = []
    for e, provider, p, card in scorecards(reg):
        rel = card.get("relevance") or {}
        scores = [rel.get(k) for k in ("target_match", "horizon_match", "covariates_match")]
        out.append(
            {
                "key": e["key"],
                "provider": provider,
                "candidate_id": card["candidate_id"],
                "title": card["title"],
                "run_id": (card.get("provenance") or {}).get("run_id", ""),
                "scorecard": str(p.relative_to(reg.root)),
                "scorecard_sha": hashlib.sha256(p.read_bytes()).hexdigest()[:12],
                "label": card.get("label", ""),
                "runnable_class": card.get("runnable_class", ""),
                "evidence_strength": card.get("evidence_strength", ""),
                "relevance": "target {} / horizon {} / covariates {}".format(*scores),
                "n_sources": str(len(card.get("primary_sources") or [])),
                "stale": "",
            }
        )
    return out


def receipt_rows(reg: rg.Registry) -> list[dict]:
    out = []
    for e, provider, p, card in scorecards(reg):
        r = card.get("receipt")
        if not r:
            continue
        measured = "; ".join(
            f"{m['zone']} {m['regime']} {m['error_ratio']} [{m['ci90'][0]}, {m['ci90'][1]}]"
            for m in r.get("measured") or []
        )
        after = r.get("n_windows_after_weights")
        out.append(
            {
                "key": e["key"],
                "provider": provider,
                "candidate_id": card["candidate_id"],
                "title": card["title"],
                "scorecard": str(p.relative_to(reg.root)),
                "model": r.get("model", ""),
                "protocol_version": r.get("protocol_version", ""),
                "receipt_verdict": r.get("verdict", ""),
                "measured": measured,
                "n_windows": str(r.get("n_windows", "")),
                "n_windows_after_weights": "" if after is None else str(after),
            }
        )
    return out


def blind_labels(root: Path) -> dict[str, str]:
    p = root / "eval" / "items.yaml"
    if not p.exists():
        return {}
    items = yaml.safe_load(p.read_text())["items"]
    return {i["id"]: i["label_yuri"] for i in items if i.get("label_yuri")}


def merge(name: str, old: list[dict], fresh: list[dict]) -> tuple[list[dict], int]:
    """Old rows with their machine side refreshed, then the new rows. Returns the rows
    and how many are new."""
    spec = SHEETS[name]
    ident = lambda r: tuple(r.get(k, "") for k in spec["key"])  # noqa: E731
    by = {ident(r): r for r in fresh}
    out, seen = [], set()
    for r in old:
        k = ident(r)
        seen.add(k)
        new = by.get(k)
        if new is None:  # its source is gone: keep the row as it is
            out.append(r)
            continue
        row = {c: r.get(c, "") for c in spec["human"]} | new
        if name == "judge":
            changed = r.get("scorecard_sha") and r["scorecard_sha"] != new["scorecard_sha"]
            row["stale"] = "yes" if (changed and reviewed(name, r)) else r.get("stale", "")
        out.append(row)
    added = sorted((r for k, r in by.items() if k not in seen), key=ident)
    out += [{c: "" for c in spec["human"]} | r for r in added]
    return out, len(added)


def sync(root: Path | None = None) -> dict[str, int]:
    root = root or ROOT
    reg = rg.Registry(root=root)
    reg.refresh()
    fresh = {"scan": scan_rows(reg), "judge": judge_rows(reg), "receipt": receipt_rows(reg)}
    added = {}
    for name, rows in fresh.items():
        merged, added[name] = merge(name, read(name, root), rows)
        if name == "judge":
            blind = blind_labels(root)
            for r in merged:
                mine = blind.get(r["candidate_id"])
                if mine and not reviewed(name, r):
                    r["verdict"] = "agree" if mine == r["label"] else "disagree"
                    r["corrected_label"] = "" if mine == r["label"] else mine
                    r["reviewed_by"] = "yuri (blind label, eval/items.yaml)"
        write(name, merged, root)
    return added


def problems(root: Path | None = None) -> list[str]:
    root = root or ROOT
    keys = set(rg.load(root))
    out = []
    for name in SHEETS:
        for n, r in enumerate(read(name, root), start=2):
            where = f"reviews/{name}.csv line {n}"
            for col in SHEETS[name]["human"]:
                v, ok = r.get(col, ""), ALLOWED.get(col)
                if ok is None:
                    continue
                if v and v not in ok:
                    out.append(
                        f"{where}: {col} is {v!r}; use one of {', '.join(ok)} or leave it empty"
                    )
            when = r.get("reviewed_at", "")
            if when and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when):
                out.append(f"{where}: reviewed_at is {when!r}; use YYYY-MM-DD")
            dup = r.get("human_duplicate_of", "")
            if dup and dup not in keys:
                out.append(f"{where}: human_duplicate_of {dup!r} is not a registry key")
            if r.get("corrected_label") and r.get("verdict") == "agree":
                out.append(f"{where}: a corrected label with the verdict 'agree'")
            if r.get("stale", "") not in ("", "yes"):
                out.append(f"{where}: stale is {r['stale']!r}; use yes or leave it empty")
    return out


def agreement(root: Path | None = None) -> str:
    root = root or ROOT
    lines = []
    for name in SHEETS:
        rows = read(name, root)
        done = [r for r in rows if reviewed(name, r)]
        lines.append(f"{name}: {len(done)} of {len(rows)} rows reviewed")
    rows = [r for r in read("judge", root) if r.get("verdict")]
    for provider in PROVIDERS:
        mine = [r for r in rows if r["provider"] == provider]
        if not mine:
            continue
        agree = sum(1 for r in mine if r["verdict"] == "agree")
        lines.append(f"judge, {provider}: you agreed with {agree} of {len(mine)} labels")
        for col in ("claim_ok", "sources_ok", "relevance_ok", "runnable_ok"):
            checked = [r for r in mine if r.get(col)]
            if checked:
                bad = sum(1 for r in checked if r[col] == "n")
                lines.append(f"  {col}: {bad} of {len(checked)} marked wrong")
        for r in mine:
            if r["verdict"] == "disagree":
                fix = r.get("corrected_label") or "?"
                lines.append(f"  disagree: {r['candidate_id']}: judge {r['label']}, you {fix}")
    stale = [r for r in read("judge", root) if r.get("stale") == "yes"]
    if stale:
        lines.append(f"{len(stale)} reviewed scorecards changed since your review (stale = yes)")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["sync", "check", "agreement"])
    a = ap.parse_args()
    if a.cmd == "sync":
        print(json.dumps({"new_rows": sync()}))
    elif a.cmd == "check":
        bad = problems()
        for b in bad:
            print(b)
        if bad:
            sys.exit(1)
        print("reviews: every filled cell is valid")
    else:
        print(agreement())


if __name__ == "__main__":
    main()
