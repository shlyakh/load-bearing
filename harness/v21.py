"""Score the protocol-v2.1 rows (protocol-v2.1.yaml): Chronos-2 with temperature and the
harness calendar in four more encodings. All rows are secondary.

    uv run --project models python models/chronos2.py gate --v21      # the four rows
    uv run --project core python -m harness.v21 score gate
    (scored: the same with `scored`, refused unless the git tag protocol-v2.1 exists)

The rows read the protocol-v2 model inputs (data/model_inputs/<set>_v2.parquet), so zones,
regimes, origins, weather and calendar values are those of protocol-v2. Output goes only to
results/v21/ (gate set: results/gate/v21/). No earlier scorer reads that folder.

Windows: a v2.1 row is scored on exactly the (zone, regime, cutoff) windows protocol-v2
kept (results/v2/windows.parquet, read, never written). A kept window that a v2.1 row did
not complete is dropped for that row's comparisons only and listed in dropped_windows.csv.

Registered comparisons (fixed before scoring), per zone and regime, ratio of mean window
MAE with the protocol's paired whole-week bootstrap, read against the 10% bar:
  each v2.1 row vs chronos2_temperature            does the calendar help in this encoding
  each v2.1 row vs chronos2_temperature_calendar   does the encoding matter
Descriptive: MAE on US federal holiday hours and on other hours for the six rows
(holiday_breakdown.csv), and the gap between the best and worst of the five calendar
encodings (encoding_gap.csv).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch import verify_manifest  # noqa: E402

from harness.data import ROOT, V2_REGIMES, V2_ZONES, DataV2, load_protocol  # noqa: E402
from harness.run import git, git_commit  # noqa: E402
from harness.score import leaderboard, window_metrics  # noqa: E402
from harness.stats import DAY_COLS, ratio_ci, verdict  # noqa: E402
from harness.v2 import V2_DIR, holiday_breakdown, require_frozen_v2  # noqa: E402

VERSION = "protocol-v2.1"
PROTOCOL_FILE = "protocol-v2.1.yaml"
V21_DIR = "v21"
TEMPERATURE_ONLY = "chronos2_temperature"
CATEGORICAL = "chronos2_temperature_calendar"
NEW_ROWS = [
    "chronos2_temperature_calendar_ordinal",
    "chronos2_temperature_calendar_cyclic",
    "chronos2_temperature_calendar_target1",
    "chronos2_temperature_calendar_target2",
]
CALENDAR_ROWS = [CATEGORICAL, *NEW_ROWS]
BASELINE = "vanilla_benchmark_trend"  # the leaderboard's ratio column, as in protocol-v2
READING = {
    "worth_switching": "A_better_beyond_bar",
    "regression_clearly_better": "B_better_beyond_bar",
    "practical_tie": "practical_tie",
    "inconclusive": "inconclusive",
}


def base_dir(which: str) -> Path:
    return ROOT / "results" if which == "scored" else ROOT / "results" / which


def require_frozen_v21(proto: dict) -> None:
    """Scored v2.1 rows are scored only at the tag protocol-v2.1, against an unchanged
    addendum (rules 5 and 12). protocol-v2's own conditions must hold as well."""
    require_frozen_v2(proto)
    v21 = yaml.safe_load((ROOT / PROTOCOL_FILE).read_text())
    if v21.get("version") != VERSION or v21.get("status") != "frozen":
        sys.exit(f"{PROTOCOL_FILE} is not marked frozen: scored origins must not be run yet")
    if not git("tag", "--list", VERSION):
        sys.exit(f"git tag {VERSION} does not exist: scored origins must not be run yet")
    if subprocess.run(
        ["git", "diff", "--quiet", VERSION, "--", PROTOCOL_FILE], cwd=ROOT, check=False
    ).returncode:
        sys.exit(f"{PROTOCOL_FILE} differs from tag {VERSION}")


def registered_comparisons(win: pd.DataFrame, proto: dict, rows: list[str]) -> pd.DataFrame:
    draws, seed = proto["bootstrap"]["draws"], proto["bootstrap"]["seed"]
    bar = proto["primary_comparison"]["bar"]
    wide = win.set_index(["unique_id", "regime", "model", "cutoff"]).sort_index()
    out = []
    for zone in V2_ZONES:
        for regime in V2_REGIMES:
            for a_model in rows:
                for kind, b_model in (
                    ("encoding_vs_temperature_only", TEMPERATURE_ONLY),
                    ("encoding_vs_categorical", CATEGORICAL),
                ):
                    try:
                        a = wide.loc[(zone, regime, a_model)]
                        b = wide.loc[(zone, regime, b_model)]
                    except KeyError:
                        continue
                    weeks = a.index.intersection(b.index)  # paired: the weeks both arms keep
                    if not len(weeks):
                        continue
                    a, b = a.loc[weeks], b.loc[weeks]
                    for col in ["mae", *DAY_COLS]:
                        r, lo, hi = ratio_ci(a[col].to_numpy(), b[col].to_numpy(), draws, seed)
                        out.append(
                            {
                                "kind": kind,
                                "unique_id": zone,
                                "regime": regime,
                                "model_a": a_model,
                                "model_b": b_model,
                                "metric": col,
                                "n_windows": len(weeks),
                                "ratio": r,
                                "ci90_low": lo,
                                "ci90_high": hi,
                                "reading_10pct_bar": READING[verdict(lo, hi, bar)],
                                "label": f"secondary ({VERSION})",
                            }
                        )
    return pd.DataFrame(out)


def encoding_gap(lb: pd.DataFrame) -> pd.DataFrame:
    """Descriptive: per zone and regime, the best and worst of the five calendar encodings
    by mean window MAE, and the gap between them as a share of the best."""
    cal = lb[lb["model"].isin(CALENDAR_ROWS)]
    rows = []
    for (zone, regime), g in cal.groupby(["unique_id", "regime"]):
        g = g.sort_values("mae")
        best, worst = g.iloc[0], g.iloc[-1]
        rows.append(
            {
                "unique_id": zone,
                "regime": regime,
                "n_encodings": len(g),
                "best": best["model"],
                "best_mae": best["mae"],
                "worst": worst["model"],
                "worst_mae": worst["mae"],
                "gap_share_of_best": worst["mae"] / best["mae"] - 1,
            }
        )
    return pd.DataFrame(rows)


def score(which: str) -> None:
    verify_manifest()
    proto = load_protocol()
    if which == "scored":
        require_frozen_v21(proto)
    elif which != "gate":
        sys.exit("protocol-v2.1 is scored on the gate or the scored origins only")
    out = base_dir(which) / V21_DIR
    fc = pd.concat(pd.read_parquet(p) for p in sorted((out / "forecasts").glob("*.parquet")))
    assert set(fc["model"]) <= set(NEW_ROWS), "only v2.1 rows are scored here"
    assert set(fc["regime"]) <= set(V2_REGIMES)
    assert (fc["protocol_version"] == VERSION).all()
    data = DataV2()
    new = window_metrics(fc, data)

    v2 = base_dir(which) / V2_DIR
    ref_all = pd.read_parquet(v2 / "windows.parquet")  # what protocol-v2 kept; read only
    kept = set(zip(ref_all["unique_id"], ref_all["regime"], ref_all["cutoff"], strict=True))
    keys = list(zip(new["unique_id"], new["regime"], new["cutoff"], strict=True))
    in_kept = pd.Series([k in kept for k in keys], index=new.index)
    bad = new[in_kept & ~new["complete"]]
    bad[["unique_id", "regime", "cutoff", "model"]].to_csv(out / "dropped_windows.csv", index=False)
    new = new[in_kept & new["complete"]].drop(columns="complete")
    new.to_parquet(out / "windows.parquet", index=False)

    ref = ref_all[ref_all["model"].isin([TEMPERATURE_ONLY, CATEGORICAL, BASELINE])]
    both = pd.concat([new, ref], ignore_index=True)
    lb = leaderboard(both, BASELINE).sort_values(["unique_id", "regime", "mae"])
    lb["label"] = f"secondary ({VERSION}{', gate only' if which != 'scored' else ''})"
    lb.round(4).to_csv(out / "leaderboard.csv", index=False)
    show = ["model", "unique_id", "regime", "n_windows", "mae", "ratio_vs_baseline", "runtime_s"]
    print(lb[show].round(3).to_string(index=False))
    print(f"\nkept windows not completed by a v2.1 row: {len(bad)}")

    rows = sorted(set(new["model"]), key=NEW_ROWS.index)
    stats = registered_comparisons(both, proto, rows)
    stats.round(4).to_csv(out / "stats.csv", index=False)
    head = stats[stats["metric"] == "mae"].drop(columns=["metric", "label"])
    print("\n" + head.round(3).to_string(index=False))

    gap = encoding_gap(lb)
    gap.round(4).to_csv(out / "encoding_gap.csv", index=False)
    print("\n" + gap.round(3).to_string(index=False))

    # Holiday hours against other hours for the six rows, on the windows each row kept.
    ref_fc = pd.concat(
        pd.read_parquet(v2 / "forecasts" / f"{m}.parquet") for m in (TEMPERATURE_ONLY, CATEGORICAL)
    )
    six = pd.concat([fc, ref_fc], ignore_index=True)
    hb = holiday_breakdown(six, both[both["model"] != BASELINE], data)
    hb.round(3).to_csv(out / "holiday_breakdown.csv", index=False)


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 2 or args[0] != "score" or args[1] not in ("gate", "scored"):
        sys.exit(__doc__)
    if args[1] == "scored" and git_commit().endswith("-dirty"):
        sys.exit("commit the code before scoring the scored set")
    score(args[1])


if __name__ == "__main__":
    main()
