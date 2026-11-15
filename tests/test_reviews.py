"""The review sheets: hand-filled cells survive a sync. No network.

uv run --project core pytest tests/test_reviews.py -q
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.registry as rg  # noqa: E402
import tools.reviews as rv  # noqa: E402

REAL = rv.ROOT


@pytest.fixture
def repo(tmp_path):
    """Two scorecards of one real work, with the registry rows that point at them."""
    for p in ("claude", "youcom"):
        (tmp_path / "scorecards" / p).mkdir(parents=True)
        shutil.copy(
            REAL / "scorecards" / p / "gb-demand-weather-zero-shot-backtest.json",
            tmp_path / "scorecards" / p,
        )
    reg = rg.Registry({}, tmp_path)
    row = {
        "candidate_id": "gb-demand-weather-zero-shot-backtest",
        "title": "GB backtest",
        "candidate_type": "paper",
    }
    reg.add_row(row | {"primary_url": "https://zenodo.org/records/24161799"}, "2026-11-14", "x")
    reg.add_row(
        row
        | {
            "candidate_id": "other",
            "title": "Other",
            "primary_url": "https://arxiv.org/abs/2701.00001",
        },
        "2026-11-14",
        "x",
    )
    rg.save(reg.entries, tmp_path)
    return tmp_path


def fill(root: Path, name: str, n: int, **cells: str) -> None:
    rows = rv.read(name, root)
    rows[n] |= cells
    rv.write(name, rows, root)


def test_sync_twice_changes_nothing_and_counts_rows(repo):
    assert rv.sync(repo) == {"scan": 2, "judge": 2, "receipt": 2}
    before = {n: rv.sheet_path(n, repo).read_text() for n in rv.SHEETS}
    assert rv.sync(repo) == {"scan": 0, "judge": 0, "receipt": 0}
    assert before == {n: rv.sheet_path(n, repo).read_text() for n in rv.SHEETS}
    judge = rv.read("judge", repo)
    assert {r["provider"] for r in judge} == {"claude", "youcom"} and judge[0]["run_id"]


def test_hand_filled_cells_survive_and_a_changed_scorecard_goes_stale(repo):
    rv.sync(repo)
    fill(
        repo,
        "judge",
        0,
        verdict="disagree",
        corrected_label="PARTIAL",
        claim_ok="n",
        reason="wrong, claim",
    )
    fill(repo, "scan", 0, human_relevant="y", note_public='has "quotes", commas')
    path = repo / rv.read("judge", repo)[0]["scorecard"]
    card = json.loads(path.read_text())
    path.write_text(json.dumps(card | {"label": "REJECT"}))
    rv.sync(repo)
    row = rv.read("judge", repo)[0]
    assert (row["verdict"], row["corrected_label"], row["claim_ok"]) == ("disagree", "PARTIAL", "n")
    assert row["reason"] == "wrong, claim" and row["label"] == "REJECT" and row["stale"] == "yes"
    assert rv.read("judge", repo)[1]["stale"] == ""  # not reviewed, so nothing to go stale
    assert rv.read("scan", repo)[0]["note_public"] == 'has "quotes", commas'
    rv.sync(repo)
    assert rv.read("judge", repo)[0]["stale"] == "yes"  # stays until a person clears it


def test_a_row_whose_scorecard_is_gone_is_kept(repo):
    rv.sync(repo)
    fill(repo, "judge", 1, verdict="agree")
    (repo / rv.read("judge", repo)[1]["scorecard"]).unlink()
    rv.sync(repo)
    assert len(rv.read("judge", repo)) == 2 and rv.read("judge", repo)[1]["verdict"] == "agree"


def test_excel_style_file_is_read(repo):
    rv.sync(repo)
    p = rv.sheet_path("scan", repo)
    p.write_bytes(b"\xef\xbb\xbf" + p.read_text().replace("\n", "\r\n").encode())
    fill(repo, "scan", 1, human_relevant="n")
    rv.sync(repo)
    assert rv.read("scan", repo)[1]["human_relevant"] == "n" and "\r" not in p.read_text()


def test_check_names_the_bad_cells(repo):
    rv.sync(repo)
    assert rv.problems(repo) == []
    fill(repo, "judge", 0, verdict="yes", claim_ok="maybe", reviewed_at="15/11/2026")
    fill(repo, "scan", 0, human_duplicate_of="arxiv:0000.00000")
    bad = "\n".join(rv.problems(repo))
    assert "verdict is 'yes'" in bad and "claim_ok is 'maybe'" in bad
    assert "reviewed_at" in bad and "not a registry key" in bad


def test_blind_label_is_copied_once_and_never_overwrites(repo):
    (repo / "eval").mkdir()
    cid = "gb-demand-weather-zero-shot-backtest"
    (repo / "eval" / "items.yaml").write_text(f"items:\n- id: {cid}\n  label_yuri: PARTIAL\n")
    rv.sync(repo)
    rows = rv.read("judge", repo)
    assert all(r["verdict"] == "disagree" and r["corrected_label"] == "PARTIAL" for r in rows)
    fill(repo, "judge", 0, verdict="agree", corrected_label="")
    rv.sync(repo)
    assert rv.read("judge", repo)[0]["verdict"] == "agree"
