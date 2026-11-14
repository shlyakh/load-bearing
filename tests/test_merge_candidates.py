"""Offline checks of tools/merge_candidates.py.

uv run --project core pytest tests/test_merge_candidates.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.merge_candidates import merge, norm_url, possible_duplicates  # noqa: E402


def row(cid, url, title, query="q", other=()):
    return {
        "candidate_id": cid,
        "primary_url": url,
        "title": title,
        "query": query,
        "other_urls": list(other),
    }


def test_norm_url_folds_arxiv_forms_and_www():
    assert norm_url("http://arxiv.org/pdf/2609.06656v2") == "arxiv.org/abs/2609.06656"
    assert norm_url("https://arxiv.org/abs/2609.06656") == "arxiv.org/abs/2609.06656"
    assert norm_url("https://www.zenodo.org/records/1/") == "zenodo.org/records/1"


def test_merge_folds_by_url_or_title_and_orders_by_best_rank(tmp_path):
    scans = {
        "claude": [
            row("a-claude", "https://arxiv.org/abs/2609.00001", "Paper A"),
            row("only-claude", "https://zenodo.org/records/5", "Record five", query="feed:zenodo"),
            row("c-claude", "https://example.org/c", "Same  Title, C"),
        ],
        "youcom": [
            row("only-youcom", "https://example.org/y", "Y"),
            row("a-youcom", "https://arxiv.org/pdf/2609.00001v3", "Paper A (preprint)"),
            row("c-youcom", "https://other.org/c", "same title c"),
        ],
    }
    out = merge(scans, root=tmp_path)
    ids = [r["candidate_id"] for r in out]
    assert ids == ["a-claude", "only-youcom", "only-claude", "c-claude"]
    a = out[0]
    assert a["found_by"] == ["claude", "youcom"] and a["ranks"] == {"claude": 1, "youcom": 2}
    assert a["ids"] == {"claude": "a-claude", "youcom": "a-youcom"}
    assert out[2]["from_listing"] is True and out[1]["from_listing"] is False
    assert out[3]["found_by"] == ["claude", "youcom"]  # matched on the title
    assert "https://other.org/c" in out[3]["other_urls"]


def test_merge_keeps_the_id_that_already_has_a_scorecard(tmp_path):
    card = tmp_path / "scorecards" / "youcom"
    card.mkdir(parents=True)
    (card / "a-youcom.json").write_text("{}")
    scans = {
        "claude": [row("a-claude", "https://arxiv.org/abs/2609.00001", "Paper A")],
        "youcom": [row("a-youcom", "https://arxiv.org/abs/2609.00001", "Paper A")],
    }
    assert merge(scans, root=tmp_path)[0]["candidate_id"] == "a-youcom"


def test_possible_duplicates_reports_a_shared_secondary_url(tmp_path):
    scans = {
        "claude": [row("m-paper", "https://arxiv.org/abs/2610.1", "Model, the paper")],
        "youcom": [
            row(
                "m-weights",
                "https://huggingface.co/x/m",
                "Model weights",
                other=["https://arxiv.org/abs/2610.1"],
            )
        ],
    }
    out = merge(scans, root=tmp_path)
    assert len(out) == 2
    assert possible_duplicates(out) == [("m-paper", "m-weights")]
