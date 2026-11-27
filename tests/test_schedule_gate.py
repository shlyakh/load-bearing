"""The gate that keeps one scheduled weekly run per window.

uv run --project core pytest tests/test_schedule_gate.py -q
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.schedule_gate as sg  # noqa: E402
import tools.weekly as wk  # noqa: E402


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def pr(created: str, state: str = "MERGED", branch: str = "agent/weekly-2026-11-26-9") -> dict:
    return {"headRefName": branch, "state": state, "createdAt": created}


# Pull request #6: opened on Thursday evening Eastern, before the reset at Friday 03:00 UTC.
BEFORE_RESET = pr("2026-11-26T22:55:39Z")


def test_thu_on_time_and_late():
    assert sg.due(at("2026-11-27T06:17"), "thu", [BEFORE_RESET])[0]
    assert sg.due(at("2026-11-27T16:52"), "thu", [BEFORE_RESET])[0]  # 10.5 hours late
    assert sg.due(at("2026-11-28T09:17"), "thu", [BEFORE_RESET])[0]  # a day late


def test_thu_outside_the_window():
    assert not sg.due(at("2026-11-29T03:17"), "thu", [])[0]  # 48 hours after the reset
    assert not sg.due(at("2026-11-26T16:52"), "thu", [])[0]  # Thursday: the week before, day 6
    assert not sg.due(at("2026-11-27T02:59"), "thu", [])[0]  # a minute before the reset


def test_one_run_a_week():
    ran = pr("2026-11-27T08:50:00Z", branch="agent/weekly-2026-11-27-10")
    go, why = sg.due(at("2026-11-27T09:17"), "thu", [BEFORE_RESET, ran])
    assert not go and "already happened" in why
    assert not sg.due(at("2026-11-27T09:17"), "thu", [ran | {"state": "CLOSED"}])[0]
    # the week after, the same pull request no longer counts
    assert sg.due(at("2026-12-04T06:17"), "thu", [BEFORE_RESET, ran])[0]


def test_an_open_agent_pull_request_blocks_even_an_old_one():
    go, why = sg.due(at("2026-11-27T06:17"), "thu", [BEFORE_RESET | {"state": "OPEN"}])
    assert not go and "still open" in why


def test_other_pull_requests_do_not_count():
    other = pr("2026-11-27T05:00:00Z", state="OPEN", branch="suggest/something")
    assert sg.due(at("2026-11-27T06:17"), "thu", [other])[0]


def test_wed_window_ends_before_the_reset():
    assert sg.due(at("2026-12-03T06:17"), "wed", [BEFORE_RESET])[0]
    assert sg.due(at("2026-12-03T21:17"), "wed", [BEFORE_RESET])[0]
    assert not sg.due(at("2026-12-03T03:17"), "wed", [])[0]  # before Thursday 05:00
    assert not sg.due(at("2026-12-04T00:17"), "wed", [])[0]  # too close to the reset
    assert not sg.due(at("2026-12-04T06:17"), "wed", [])[0]  # the new week
    ran = pr("2026-12-03T06:40:00Z", branch="agent/weekly-2026-12-03-12")
    assert not sg.due(at("2026-12-03T09:17"), "wed", [ran])[0]


def test_off_and_unknown():
    assert not sg.due(at("2026-11-27T06:17"), "off", [])[0]
    assert not sg.due(at("2026-11-27T06:17"), "friday", [])[0]


def test_the_budget_week_and_the_gate_share_one_anchor():
    assert wk.WEEK_ANCHOR is sg.WEEK_ANCHOR
    now = at("2026-11-27T06:17")
    assert wk.week_start(now) == sg.week_start(now) == at("2026-11-27T03:00")
