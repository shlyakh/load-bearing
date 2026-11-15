"""Stable keys, the registry seed and the weekly queue. No network, no claude run.

uv run --project core pytest tests/test_registry.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.registry as rg  # noqa: E402
from tools.keys import stable_key, url_key  # noqa: E402

ROOT = rg.ROOT


def test_url_forms_of_one_work_give_one_key():
    forms = ["https://arxiv.org/abs/2611.07784", "http://www.arxiv.org/pdf/2611.07784v3"]
    forms += ["https://arxiv.org/html/2611.07784v1", "https://doi.org/10.48550/arXiv.2611.07784"]
    assert {url_key(u) for u in forms} == {"arxiv:2611.07784"}
    assert url_key("https://doi.org/10.5281/zenodo.24161799") == "zenodo:24161799"
    assert url_key("https://zenodo.org/records/24161799/") == "zenodo:24161799"
    assert url_key("https://huggingface.co/Amazon/Chronos-2/tree/main") == "hf:amazon/chronos-2"
    assert url_key("https://github.com/a/b/releases/tag/v2") == "gh:a/b@v2"
    assert url_key("https://github.com/a/b/issues/3") == "gh:a/b"


def test_linkedin_is_never_a_key():
    assert url_key("https://www.linkedin.com/posts/someone_x") is None
    assert stable_key("https://linkedin.com/posts/x", "A title") == "t:a title"


def test_seed_is_repeatable_and_folds_the_three_energybench_slugs():
    a = rg.seed(ROOT).entries
    b = rg.seed(ROOT).entries
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    ids = set(a["arxiv:2611.07784"]["candidate_ids"])
    assert {"energybench-live-day-ahead", "energybench", "foretec-energybench"} <= ids
    assert a["arxiv:2611.07784"]["status"] == "judged"
    assert a["hf:amazon/chronos-2"]["status"] == "implemented_scored"


def test_committed_registry_matches_a_fresh_seed_for_seeded_fields():
    """Statuses in the committed file are what the scorecards on disk imply."""
    reg = rg.Registry(root=ROOT)
    before = {k: e["status"] for k, e in reg.entries.items()}
    reg.refresh()
    assert before == {k: e["status"] for k, e in reg.entries.items()}


def test_rescanning_the_last_merged_scan_finds_nothing_new():
    reg = rg.seed(ROOT)
    f = ROOT / "candidates" / "merged" / "scan_2026-11-14.jsonl"
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    res = rg.ingest(reg, rows, "2026-11-14", "x", cap=60)
    assert res["report"]["new"] == []
    assert len(res["report"]["known"]) >= 20  # judged at the hackathon: not judged again
    assert all(reg.entries[k]["status"] == "seen_not_judged" for k in res["report"]["queued"])


def rows(n: int, start: int = 0) -> list[dict]:
    return [
        {
            "candidate_id": f"work-{i}",
            "title": f"Synthetic work number {i}",
            "primary_url": f"https://arxiv.org/abs/2701.{i:05d}",
            "other_urls": [],
            "published_at": "2027-01-01",
            "candidate_type": "paper",
        }
        for i in range(start, start + n)
    ]


def test_cap_defers_the_overflow_and_serves_it_first_next_week(tmp_path):
    (tmp_path / "scorecards" / "claude").mkdir(parents=True)
    reg = rg.Registry({}, tmp_path)
    week1 = rg.ingest(reg, rows(70), "2027-01-04", "w1", cap=60)
    assert len(week1["queue"]) == 60 and len(week1["report"]["deferred_by_cap"]) == 10
    deferred = week1["report"]["deferred_by_cap"]
    assert all(reg.entries[k]["queue"]["reason"] == "cap" for k in deferred)

    for q in week1["queue"][:58]:  # 58 judged; two runs died
        card = {"candidate_id": q["candidate_id"], "label": "PARTIAL"}
        (tmp_path / "scorecards" / "claude" / f"{q['candidate_id']}.json").write_text(
            json.dumps(card)
        )
    out = rg.sync(reg, "usage_limit")
    assert len(out["judged"]) == 58 and len(out["unfinished"]) == 2

    week2 = rg.ingest(reg, rows(5, start=100), "2027-01-11", "w2", cap=60)
    queued = week2["report"]["queued"]
    assert len(queued) == 17  # 12 carried over (10 capped, 2 unfinished) + 5 new
    assert set(queued[:12]) == set(deferred) | set(out["unfinished"])
    assert all(q["carried_over"] for q in week2["queue"][:12])
    assert week2["queue"][0]["candidate_id"].startswith("work-")


def test_known_work_is_not_queued_again_under_a_new_slug(tmp_path):
    (tmp_path / "scorecards" / "claude").mkdir(parents=True)
    reg = rg.Registry({}, tmp_path)
    first = rg.ingest(reg, rows(1), "2027-01-04", "w1", cap=60)
    cid = first["queue"][0]["candidate_id"]
    (tmp_path / "scorecards" / "claude" / f"{cid}.json").write_text(json.dumps({"label": "REJECT"}))
    rg.sync(reg)
    again = rows(1)[0] | {
        "candidate_id": "a-different-slug",
        "primary_url": "https://arxiv.org/pdf/2701.00000v2",
    }
    res = rg.ingest(reg, [again], "2027-01-11", "w2", cap=60)
    assert res["queue"] == [] and res["report"]["known"] == ["arxiv:2701.00000"]
    assert reg.entries["arxiv:2701.00000"]["status"] == "rejected"
    assert "a-different-slug" in reg.entries["arxiv:2701.00000"]["candidate_ids"]


def test_same_repository_with_a_new_title_is_queued_as_a_possible_new_version(tmp_path):
    (tmp_path / "scorecards" / "claude").mkdir(parents=True)
    reg = rg.Registry({}, tmp_path)
    v1 = rows(1)[0] | {"title": "Model 1.0", "primary_url": "https://github.com/lab/model"}
    cid = rg.ingest(reg, [v1], "2027-01-04", "w1", cap=60)["queue"][0]["candidate_id"]
    (tmp_path / "scorecards" / "claude" / f"{cid}.json").write_text(
        json.dumps({"label": "PARTIAL"})
    )
    rg.sync(reg)
    v2 = v1 | {"title": "Model 2.0", "candidate_id": "model-2"}
    res = rg.ingest(reg, [v2], "2027-01-11", "w2", cap=60)
    assert len(res["queue"]) == 1 and len(res["report"]["possible_new_version"]) == 1
    new = reg.entries[res["report"]["possible_new_version"][0]]
    assert new["relations"][0]["type"] == "new_version_of"
    assert new["relations"][0]["target"] == "gh:lab/model"
