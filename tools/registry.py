"""Registry of the works we know: papers, models, frameworks, benchmarks, methods.

    uv run --project core python tools/registry.py seed
    uv run --project core python tools/registry.py ingest candidates/merged/scan_<date>.jsonl \
        --date <date> --cap 60 [--run-id <id>]
    uv run --project core python tools/registry.py sync [--unfinished usage_limit|failed]
    uv run --project core python tools/registry.py check <url> [<url> ...]
    uv run --project core python tools/registry.py related <key>
    uv run --project core python tools/registry.py relate --from <key> --to <key> \
        --type improves_on --claim "<paraphrase, at most 400 characters>" [--evidence <id>]
    uv run --project core python tools/registry.py stats

One line per work in registry/entries.jsonl, sorted by key. The key comes from the
work's primary URL (tools/keys.py), never from a candidate id, because scans give one
paper different ids. An entry also lists `aliases` (other keys it has been found under,
and its title key) and `candidate_ids` (every slug a scan gave it).

status
  implemented_scored      has rows on a leaderboard
  implemented_not_scored  an adapter exists; the scored run has not been made
  judged                  at least one scorecard; not on a leaderboard
  rejected                every scorecard says REJECT
  seen_not_judged         a scan kept it; nobody judged it
  reference               known from our notes; not found by a scan, not implemented

`seed` rebuilds the file from registry/seed_manual.yaml, every candidates/*/scan_*.jsonl,
the scorecards and eval/items.yaml. It is repeatable: relations, queue marks and public
notes are carried over from the existing file by key.

`ingest` takes one merged scan and decides what the weekly run judges: works that are
already judged, rejected or implemented are known and skipped; works deferred by an
earlier run come first (oldest first), then this scan's unjudged works in the scan's
order, up to --cap. The chosen rows go to candidates/merged/queue_<date>.jsonl under
their canonical candidate id; the rest are marked deferred with the reason `cap`.
A work found under a repository-level key (a GitHub repository, a Hugging Face
repository, a PyPI project) with a different title from the known entry is treated as a
possible new version: it gets its own entry, related to the old one, and is queued.

`sync` re-reads the scorecards after judging, clears the queue mark of works that now
have a scorecard and marks the chosen works that still have none (--unfinished).

Stores URLs, titles and short paraphrases only (CLAUDE.md rule 9); no LinkedIn (rule 10).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.keys import is_linkedin, repo_level, stable_key, title_key, url_key  # noqa: E402
from tools.merge_candidates import scan_order  # noqa: E402

PROVIDERS = ("claude", "youcom")
KINDS = {
    "model_release": "model",
    "library_feature": "framework",
    "practitioner_backtest": "backtest",
    "paper": "paper",
    "benchmark": "benchmark",
    "vendor_claim": "post",
    "off_target": "other",
}
RELATIONS = (
    "improves_on",
    "new_version_of",
    "extends",
    "evaluates",
    "replicates",
    "compares_against",
)
KNOWN = ("implemented_scored", "implemented_not_scored", "judged", "rejected")
DEFERRED = ("cap", "usage_limit", "failed")
MAX_CLAIM = 400


def registry_path(root: Path = ROOT) -> Path:
    return root / "registry" / "entries.jsonl"


def load(root: Path = ROOT) -> dict[str, dict]:
    p = registry_path(root)
    if not p.exists():
        return {}
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return {r["key"]: r for r in rows}


def save(entries: dict[str, dict], root: Path = ROOT) -> None:
    p = registry_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "".join(json.dumps(entries[k], ensure_ascii=False) + "\n" for k in sorted(entries))
    )


def blank(key: str, title: str, kind: str, primary_url: str | None) -> dict:
    return {
        "key": key,
        "aliases": [],
        "kind": kind,
        "title": title,
        "primary_url": primary_url,
        "other_urls": [],
        "published_at": None,
        "first_seen": None,
        "last_seen": None,
        "candidate_ids": [],
        "canonical_candidate_id": None,
        "status": "seen_not_judged",
        "status_detail": {},
        "queue": None,
        "relations": [],
        "notes_public": "",
        "source": None,
    }


def add_unique(items: list, *new) -> None:
    for x in new:
        if x and x not in items:
            items.append(x)


class Registry:
    """The entries plus lookups by alias and by candidate id."""

    def __init__(self, entries: dict[str, dict] | None = None, root: Path = ROOT):
        self.root = root
        self.entries = entries if entries is not None else load(root)
        self.by_alias: dict[str, str] = {}
        self.by_cid: dict[str, str] = {}
        for e in self.entries.values():
            self.index(e)

    def index(self, e: dict) -> None:
        for a in [e["key"], *e["aliases"]]:
            self.by_alias.setdefault(a, e["key"])
        for c in e["candidate_ids"]:
            self.by_cid.setdefault(c, e["key"])

    def find(self, primary_url: str, title: str, cid: str = "") -> tuple[dict | None, str]:
        """The entry for a work and how it matched: url, title, id, or '' for none."""
        k = url_key(primary_url or "")
        if k and k in self.by_alias:
            return self.entries[self.by_alias[k]], "url"
        t = title_key(title)
        if t and t in self.by_alias:
            return self.entries[self.by_alias[t]], "title"
        if cid and cid in self.by_cid:
            return self.entries[self.by_cid[cid]], "id"
        return None, ""

    def new(self, key: str, title: str, kind: str, primary_url: str | None) -> dict:
        if key in self.entries:
            raise ValueError(f"duplicate key {key}")
        e = blank(key, title, kind, primary_url)
        add_unique(e["aliases"], title_key(title))
        self.entries[key] = e
        self.index(e)
        return e

    def see(self, e: dict, row: dict, when: str, source: str) -> None:
        """Record that a scan row is this work."""
        add_unique(e["aliases"], url_key(row.get("primary_url") or ""), title_key(row["title"]))
        urls = [row.get("primary_url"), *(row.get("other_urls") or [])]
        add_unique(
            e["other_urls"],
            *(u for u in urls if u and u != e["primary_url"] and not is_linkedin(u)),
        )
        ids = [row.get("candidate_id"), *(row.get("ids") or {}).values()]
        add_unique(e["candidate_ids"], *ids)
        e["canonical_candidate_id"] = e["canonical_candidate_id"] or row.get("candidate_id")
        e["published_at"] = e["published_at"] or row.get("published_at")
        seen = {"date": when, "source": source}
        if not e["first_seen"] or when < e["first_seen"]["date"]:
            e["first_seen"] = seen
        if not e["last_seen"] or when >= e["last_seen"]["date"]:
            e["last_seen"] = seen
        self.index(e)

    def add_row(self, row: dict, when: str, source: str, by_id: bool = False) -> tuple[dict, str]:
        """Find or create the entry for a scan row. Returns it and the match kind
        ('new', 'url', 'title', 'id', or 'version' for a possible new version)."""
        e, how = self.find(
            row.get("primary_url") or "", row["title"], row["candidate_id"] if by_id else ""
        )
        kind = KINDS.get(row.get("candidate_type"), "other")
        if e is None:
            key = stable_key(row.get("primary_url") or "", row["title"])
            if key is None:
                raise ValueError(f"no key for {row.get('candidate_id')}")
            e, how = self.new(key, row["title"], kind, row.get("primary_url")), "new"
        elif (
            how == "url"
            and not by_id
            and e["status"] in KNOWN
            and repo_level(url_key(row["primary_url"]) or "")
            and title_key(row["title"]) not in e["aliases"]
        ):
            slug = re.sub(r"\W+", "-", row["title"].lower()).strip("-")[:60]
            old = e
            e = self.new(
                f"{url_key(row['primary_url'])}#{slug}", row["title"], kind, row["primary_url"]
            )
            e["relations"].append(
                {
                    "type": "new_version_of",
                    "target": old["key"],
                    "claim": "Found at the same repository under a different title; not checked.",
                    "evidence_id": None,
                    "asserted_by": "registry.ingest",
                }
            )
            how = "version"
        self.see(e, row, when, source)
        return e, how

    def refresh(self) -> None:
        """Set each entry's status from the scorecards on disk and its leaderboard rows."""
        for e in self.entries.values():
            cards, labels, verdicts = [], {}, {}
            for cid in e["candidate_ids"]:
                for p in PROVIDERS:
                    f = self.root / "scorecards" / p / f"{cid}.json"
                    if not f.exists():
                        continue
                    card = json.loads(f.read_text())
                    cards.append(str(f.relative_to(self.root)))
                    labels[p] = card.get("label")
                    if card.get("receipt"):
                        verdicts[p] = card["receipt"].get("verdict")
            d = e["status_detail"]
            d["scorecards"], d["labels"], d["receipt_verdicts"] = sorted(cards), labels, verdicts
            manual = d.get("manual_status")
            if d.get("leaderboard_models"):
                e["status"] = "implemented_scored"
            elif manual == "implemented_not_scored":
                e["status"] = manual
            elif cards:
                rejected = all(v == "REJECT" for v in labels.values())
                e["status"] = "rejected" if rejected else "judged"
            else:
                e["status"] = manual or "seen_not_judged"


def leaderboard_models(root: Path = ROOT) -> set[str]:
    out: set[str] = set()
    for f in (root / "results").glob("**/leaderboard.csv"):
        with f.open() as fh:
            out |= {r["model"] for r in csv.DictReader(fh)}
    return out


def scan_date(path: Path) -> str:
    return scan_order(path)[0]


def seed(root: Path = ROOT) -> Registry:
    old = load(root)
    reg = Registry({}, root)
    scored = leaderboard_models(root)
    manual = yaml.safe_load((root / "registry" / "seed_manual.yaml").read_text())["works"]
    for w in manual:
        key = w.get("key") or url_key(w["primary_url"])
        e = reg.new(key, w["title"], w["kind"], w.get("primary_url"))
        e["source"] = w["source"]
        add_unique(e["aliases"], *(url_key(u) for u in w.get("also") or []))
        reg.index(e)
        e["notes_public"] = w.get("note", "")
        d = e["status_detail"]
        d["manual_status"] = w["status"]
        d["leaderboard_models"] = w.get("leaderboard_models", [])
        missing = set(d["leaderboard_models"]) - scored
        if missing:
            raise SystemExit(f"{key}: not on any leaderboard: {sorted(missing)}")
    files = sorted(
        (f for f in (root / "candidates").glob("*/scan_*.jsonl") if f.parent.name != "feeds"),
        key=lambda f: (scan_order(f), f.parent.name),
    )
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                reg.add_row(json.loads(line), scan_date(f), str(f.relative_to(root)), by_id=True)
    items = yaml.safe_load((root / "eval" / "items.yaml").read_text())["items"]
    for it in items:
        urls = [u for u in it.get("primary_sources") or [] if not is_linkedin(u)]
        row = {
            "candidate_id": it["id"],
            "title": it["title"],
            "primary_url": urls[0] if urls else "",
            "other_urls": urls[1:],
            "candidate_type": it.get("candidate_type"),
        }
        reg.add_row(row, "2026-11-12", "eval/items.yaml", by_id=True)
    for p in PROVIDERS:
        for f in sorted((root / "scorecards" / p).glob("*.json")):
            card = json.loads(f.read_text())
            if card["candidate_id"] in reg.by_cid:
                continue
            via = (card.get("discovered_via") or {}).get("url") or ""
            sources = [s["url"] for s in card.get("primary_sources") or []]
            first = via if via and not is_linkedin(via) else (sources[0] if sources else "")
            row = {
                "candidate_id": card["candidate_id"],
                "title": card["title"],
                "primary_url": first,
                "other_urls": sources,
                "candidate_type": card.get("candidate_type"),
            }
            when = ((card.get("discovered_via") or {}).get("retrieved_at") or "")[:10]
            reg.add_row(row, when or "2026-11-14", str(f.relative_to(root)), by_id=True)
    reg.refresh()
    for key, e in reg.entries.items():  # what a seed cannot derive is carried over
        if key in old:
            for field in ("relations", "queue"):
                e[field] = old[key][field]
            if not e["source"]:
                e["notes_public"] = old[key]["notes_public"]
    return reg


def candidate_row(root: Path, cid: str) -> dict | None:
    """The newest scan row with this candidate id, from any candidates file."""
    files = sorted(
        (f for f in (root / "candidates").glob("*/scan_*.jsonl") if f.parent.name != "feeds"),
        key=lambda f: (scan_order(f), f.parent.name),
        reverse=True,
    )
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("candidate_id") == cid or cid in (row.get("ids") or {}).values():
                    return row
    return None


def ingest(reg: Registry, rows: list[dict], when: str, source: str, cap: int) -> dict:
    """Classify one merged scan and choose what to judge. Returns the queue rows and
    the counts; marks the queue in the registry."""
    reg.refresh()
    carried = sorted(
        (e for e in reg.entries.values() if (e["queue"] or {}).get("reason") in DEFERRED),
        key=lambda e: (e["queue"]["since"], e["key"]),
    )
    report = {
        "new": [],
        "known": [],
        "unjudged_seen_before": [],
        "possible_new_version": [],
        "shares_url_with_known": [],
    }
    fresh: list[tuple[dict, dict]] = []
    for row in rows:
        e, how = reg.add_row(row, when, source)
        if how == "version":
            report["possible_new_version"].append(e["key"])
        if e["status"] in KNOWN:
            report["known"].append(e["key"])
            continue
        report["new" if how in ("new", "version") else "unjudged_seen_before"].append(e["key"])
        if how == "new":  # a new work that links to a known one: a person should look
            for u in row.get("other_urls") or []:
                k = url_key(u) or ""
                other = reg.by_alias.get(k)
                if other and other != e["key"] and (k.startswith("hf:") or not repo_level(k)):
                    report["shares_url_with_known"].append(f"{e['key']} ~ {other}")
        if e not in carried and all(e is not x for x, _ in fresh):
            fresh.append((e, row))
    carried = [e for e in carried if e["status"] not in KNOWN]
    order = [(e, None) for e in carried] + fresh
    queue = []
    for n, (e, row) in enumerate(order):
        since = (e["queue"] or {}).get("since") or when
        if n >= cap:
            e["queue"] = {"since": since, "reason": "cap"}
            continue
        e["queue"] = {"since": since, "reason": "selected"}
        cid = e["canonical_candidate_id"]
        row = (
            row
            or candidate_row(reg.root, cid)
            or {
                "title": e["title"],
                "primary_url": e["primary_url"],
                "other_urls": e["other_urls"],
                "published_at": e["published_at"],
            }
        )
        queue.append(
            dict(row)
            | {"candidate_id": cid, "registry_key": e["key"], "carried_over": e in carried}
        )
    report |= {
        "carried_over": [e["key"] for e in carried],
        "queued": [q["registry_key"] for q in queue],
        "deferred_by_cap": [e["key"] for e, _ in order[cap:]],
    }
    return {"queue": queue, "report": report}


def sync(reg: Registry, unfinished: str = "failed") -> dict:
    """After judging: refresh statuses, clear the queue of works that now have a
    scorecard, mark the chosen ones that have none."""
    reg.refresh()
    judged, left = [], []
    for e in reg.entries.values():
        if (e["queue"] or {}).get("reason") != "selected":
            continue
        if e["status"] in KNOWN:
            e["queue"] = None
            judged.append(e["key"])
        else:
            e["queue"]["reason"] = unfinished
            left.append(e["key"])
    return {"judged": judged, "unfinished": left}


def describe(e: dict) -> str:
    d = e["status_detail"]
    extra = d.get("labels") or d.get("leaderboard_models") or ""
    return f"{e['status']}  {e['key']}  {e['title'][:70]}  {extra}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("stats")
    sp = sub.add_parser("ingest")
    sp.add_argument("scan")
    sp.add_argument("--date", required=True)
    sp.add_argument("--cap", type=int, default=60)
    sp.add_argument("--out", default="")
    sp = sub.add_parser("sync")
    sp.add_argument("--unfinished", choices=["usage_limit", "failed"], default="failed")
    sp = sub.add_parser("check")
    sp.add_argument("urls", nargs="+")
    sp = sub.add_parser("related")
    sp.add_argument("key")
    sp = sub.add_parser("relate")
    sp.add_argument("--from", dest="src", required=True)
    sp.add_argument("--to", required=True)
    sp.add_argument("--type", required=True, choices=RELATIONS)
    sp.add_argument("--claim", required=True)
    sp.add_argument("--evidence", default=None)
    sp.add_argument("--by", default="interactive")
    a = ap.parse_args()

    if a.cmd == "seed":
        reg = seed()
        save(reg.entries)
        a.cmd = "stats"
    else:
        reg = Registry()
    if a.cmd == "stats":
        counts: dict[str, int] = {}
        for e in reg.entries.values():
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        merged = {
            e["key"]: e["candidate_ids"]
            for e in reg.entries.values()
            if len(e["candidate_ids"]) > 1
        }
        print(json.dumps({"entries": len(reg.entries), "by_status": counts}, indent=1))
        print(f"{len(merged)} works were found under more than one candidate id:")
        for k, ids in sorted(merged.items()):
            print(f"  {k}: {', '.join(ids)}")
    elif a.cmd == "ingest":
        src = Path(a.scan).resolve()
        rows = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
        res = ingest(reg, rows, a.date, str(src.relative_to(ROOT)), a.cap)
        out = Path(a.out) if a.out else ROOT / "candidates" / "merged" / f"queue_{a.date}.jsonl"
        out.write_text("".join(json.dumps(r) + "\n" for r in res["queue"]))
        save(reg.entries)
        print(json.dumps({k: len(v) for k, v in res["report"].items()} | {"queue_file": str(out)}))
    elif a.cmd == "sync":
        res = sync(reg, a.unfinished)
        save(reg.entries)
        print(json.dumps({k: len(v) for k, v in res.items()}))
    elif a.cmd == "check":
        for u in a.urls:
            e, _ = reg.find(u, "")
            print(f"KNOWN  {describe(e)}" if e else f"NEW    {url_key(u)}  {u}")
    elif a.cmd == "related":
        e = reg.entries.get(reg.by_alias.get(a.key, ""))
        if not e:
            sys.exit(f"not in the registry: {a.key}")
        print(describe(e))
        for r in e["relations"]:
            print(f"  {r['type']} -> {r['target']}: {r['claim']}")
        for o in reg.entries.values():
            for r in o["relations"]:
                if r["target"] == e["key"]:
                    print(f"  <- {r['type']} by {o['key']}: {r['claim']}")
    elif a.cmd == "relate":
        if len(a.claim) > MAX_CLAIM:
            sys.exit(f"claim is longer than {MAX_CLAIM} characters: paraphrase, do not copy")
        src, dst = (reg.entries.get(reg.by_alias.get(k, "")) for k in (a.src, a.to))
        if not src or not dst:
            sys.exit("both keys must be in the registry")
        rel = {
            "type": a.type,
            "target": dst["key"],
            "claim": a.claim,
            "evidence_id": a.evidence,
            "asserted_by": a.by,
        }
        if rel not in src["relations"]:
            src["relations"].append(rel)
        save(reg.entries)
        print(f"{src['key']} {a.type} {dst['key']}")


if __name__ == "__main__":
    main()
