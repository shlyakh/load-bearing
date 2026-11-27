"""Decide whether a scheduled firing of the weekly workflow should start a run.

    gh pr list --state all --limit 50 --json headRefName,state,createdAt \
        | python3 tools/schedule_gate.py thu

GitHub starts scheduled workflows late (10.5 hours on 2026-11-26) and may drop one. So the
workflow fires every three hours from Thursday to Saturday UTC, and this gate keeps the
first firing that falls inside the week's window, once (decision 53):

  thu  from the subscription's weekly reset (Friday 03:00 UTC) for 48 hours: the new week
  wed  Thursday 05:00 to 23:30 UTC: what is left of the week, ending before the reset
  off  never

Inside the window a run is due only when no agent pull request (`agent/weekly-*`) is open
and none was opened since the window began. A run started by hand counts too, so there is
one run per window whoever started it. A run that opened no pull request (nothing to
judge, or the budget was used) is tried again at the next firing; that costs nothing.

Standard library only: the preflight job runs it with the runner's own Python. The reset
is fixed in UTC here; when the clocks change it moves by an hour in Eastern time.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta

WEEK_ANCHOR = "2026-11-20T03:00:00+00:00"  # the subscription's weekly reset (Fridays 03:00 UTC)
WEEK = timedelta(days=7)
AGENT_BRANCH = "agent/weekly-"


def week_start(now: datetime, anchor: str = WEEK_ANCHOR) -> datetime:
    """The start of the 7-day budget period that holds `now`."""
    a = datetime.fromisoformat(anchor)
    return a + WEEK * ((now - a) // WEEK)


def window(now: datetime, run_night: str) -> tuple[datetime, datetime] | None:
    """The window of the budget week that holds `now`, or None for `off` or an unknown value."""
    start = week_start(now)
    if run_night == "thu":
        return start, start + timedelta(hours=48)
    if run_night == "wed":
        reset = start + WEEK
        return reset - timedelta(hours=22), reset - timedelta(hours=3, minutes=30)
    return None


def due(now: datetime, run_night: str, prs: list[dict]) -> tuple[bool, str]:
    """Whether a scheduled firing at `now` should start the run, and why. `prs` are rows
    of `gh pr list --json headRefName,state,createdAt`."""
    w = window(now, run_night)
    if w is None:
        return False, f"RUN_NIGHT is {run_night}; no scheduled run"
    opens, closes = w
    if not opens <= now < closes:
        return False, f"outside the {run_night} window ({opens:%a %H:%M} to {closes:%a %H:%M} UTC)"
    agent = [p for p in prs if p["headRefName"].startswith(AGENT_BRANCH)]
    still_open = sum(1 for p in agent if p["state"].upper() == "OPEN")
    if still_open:
        return False, f"{still_open} agent pull request(s) still open; the run was not started"
    created = {p["headRefName"]: p["createdAt"].replace("Z", "+00:00") for p in agent}
    ran = [b for b, t in created.items() if datetime.fromisoformat(t) >= opens]
    if ran:
        return False, f"this week's run already happened ({ran[0]})"
    return True, f"inside the {run_night} window and no run yet this week"


def main() -> None:
    run_night = sys.argv[1] if len(sys.argv) > 1 else "thu"
    go, why = due(datetime.now(UTC), run_night, json.load(sys.stdin))
    print(f"::notice::{why}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"go={'true' if go else 'false'}\n")


if __name__ == "__main__":
    main()
