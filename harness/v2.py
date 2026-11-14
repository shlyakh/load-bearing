"""Run, export and score the protocol-v2 rows (protocol-v2.yaml).

    uv run --project core python -m harness.v2 export gate            # model_inputs/gate_v2.parquet
    uv run --project core python -m harness.v2 run gate [--limit 2]   # core rows, gate origins
    uv run --project models python models/chronos2.py gate --v2       # Chronos-2 rows
    uv run --project core python -m harness.v2 score gate
    (scored: the same with `scored`, refused unless the git tag protocol-v2 exists)

Zones: AEP and AE (primary), DOM and JC (development). Regimes: oracle_era5, forecast_gfs,
forecast_ifs, forecast_aifs (ERA5 history in all four, lead-matched horizon as in v1.2).
Origins: protocol.yaml's gate and scored lists, read from there.

Output goes only to results/v2/ (gate set: results/gate/v2/): forecasts/, windows.parquet,
leaderboard.csv, dropped_windows.csv, stats.csv, holiday_breakdown.csv, primary.md.
No earlier scorer reads that folder, and nothing here writes outside it.

Drop rule, per zone and regime (as protocol-v1.2): a window whose forecast or actuals are
incomplete for any v2 row run in that zone is dropped for every v2 row in that zone AND
THAT REGIME only, and listed in dropped_windows.csv.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch import verify_manifest  # noqa: E402

from harness.baselines import V2_MODELS  # noqa: E402
from harness.data import (  # noqa: E402
    ROOT,
    V2_DEVELOPMENT_ZONES,
    V2_PRIMARY_ZONES,
    V2_REGIMES,
    V2_ZONES,
    DataV2,
    calendar,
    load_protocol,
    origins,
)
from harness.run import git, git_commit, require_frozen  # noqa: E402
from harness.score import leaderboard, window_metrics  # noqa: E402
from harness.stats import DAY_COLS, ratio_ci, verdict  # noqa: E402

VERSION = "protocol-v2"
PROTOCOL_FILE = "protocol-v2.yaml"
FROZEN_FILES = [
    "protocol.yaml",
    "protocol-v1.1.yaml",
    "protocol-v1.2.yaml",
    "protocol-v1.3.yaml",
    PROTOCOL_FILE,
]
V2_DIR = "v2"
CONTEXT_HOURS = 4096  # rows of history exported per window (Chronos-2 uses the last 2,048)
CALENDAR_COLUMNS = ["hour", "dow", "hol", "yearend"]  # harness.data.calendar, unchanged

BASELINE = "vanilla_benchmark_trend"
CHALLENGER = "chronos2_temperature"
PRIMARY_REGIME = "forecast_aifs"
ORACLE = "oracle_era5"

# Every v2 row: where it runs, which zones, its weather and its calendar inputs (decision 30).
ROWS = {
    "vanilla_benchmark_trend": {
        "env": "core",
        "zones": V2_ZONES,
        "weather": "temperature",
        "calendar": "own: month, day of week x hour (no holidays)",
    },
    "chronos2_temperature": {
        "env": "models",
        "zones": V2_ZONES,
        "weather": "temperature",
        "calendar": "none",
    },
    "vanilla_benchmark_trend_holiday": {
        "env": "core",
        "zones": V2_ZONES,
        "weather": "temperature",
        "calendar": "harness: holiday x hour, year-end x hour; own: month, day of week x hour",
    },
    "chronos2_temperature_calendar": {
        "env": "models",
        "zones": V2_ZONES,
        "weather": "temperature",
        "calendar": "harness: hour, day of week (categorical), holiday, year-end (0/1)",
    },
    "lag_regression_temperature": {
        "env": "core",
        "zones": V2_PRIMARY_ZONES,
        "weather": "temperature",
        "calendar": "own: hour (per-hour fits), day of week, US federal holiday, year-end",
    },
    "lightgbm_competition": {
        "env": "core",
        "zones": V2_PRIMARY_ZONES,
        "weather": "temperature",
        "calendar": "own: 13 calendar features, US federal holidays included",
    },
    "chronos2": {
        "env": "models",
        "zones": V2_PRIMARY_ZONES,
        "weather": "none",
        "calendar": "none",
    },
}
CORE_ROWS = [m for m, r in ROWS.items() if r["env"] == "core"]
assert set(CORE_ROWS) == set(V2_MODELS)
CALENDAR_PAIRS = [
    ("chronos2_temperature_calendar", "chronos2_temperature"),
    ("vanilla_benchmark_trend_holiday", "vanilla_benchmark_trend"),
]
READING = {
    "worth_switching": "A_better_beyond_bar",
    "regression_clearly_better": "B_better_beyond_bar",
    "practical_tie": "practical_tie",
    "inconclusive": "inconclusive",
}
PRIMARY_VERDICT = {
    "worth_switching": "worth_switching",
    "regression_clearly_better": "baseline_clearly_better",
    "practical_tie": "practical_tie",
    "inconclusive": "inconclusive",
}


def out_dir(which: str) -> Path:
    return (ROOT / "results" if which == "scored" else ROOT / "results" / which) / V2_DIR


def load_v2_protocol() -> dict:
    return yaml.safe_load((ROOT / PROTOCOL_FILE).read_text())


def require_frozen_v2(proto: dict, out_file: Path | None = None) -> None:
    """Scored v2 runs only at the tag protocol-v2, against unchanged protocol files, from a
    clean tree, and only once (rules 5 and 12)."""
    require_frozen(proto)
    v2 = load_v2_protocol()
    if v2.get("version") != VERSION or v2.get("status") != "frozen":
        sys.exit(f"{PROTOCOL_FILE} is not marked frozen: scored origins must not be run yet")
    if not git("tag", "--list", VERSION):
        sys.exit(f"git tag {VERSION} does not exist: scored origins must not be run yet")
    if subprocess.run(
        ["git", "diff", "--quiet", VERSION, "--", *FROZEN_FILES], cwd=ROOT, check=False
    ).returncode:
        sys.exit(f"a protocol file differs from tag {VERSION}")
    if out_file is not None:
        if git_commit().endswith("-dirty"):
            sys.exit("commit the code before a scored run")
        if out_file.exists():
            sys.exit(f"{out_file} exists: the scored set is run once")


# ------------------------------------------------------------------ model inputs


def model_input_frame(
    data: DataV2, zone: str, regime: str, cutoff: pd.Timestamp, context_hours: int = CONTEXT_HOURS
) -> pd.DataFrame:
    """The exact rows a foundation model may see for one window: `context_hours` rows up to
    the cutoff (y, T, calendar) and the 168 horizon rows (T and calendar, y missing)."""
    temp = data.temperature(zone, cutoff, regime)  # ends at cutoff + 168 h
    idx = temp.index[-(context_hours + 168) :]
    y = data.history(zone, cutoff).reindex(idx)  # missing over the horizon
    cal = calendar(idx)
    df = pd.DataFrame(
        {
            "unique_id": zone,
            "regime": regime,
            "cutoff": cutoff,
            "ds": idx,
            "y": y.to_numpy(),
            "T": temp.reindex(idx).to_numpy(),
            "is_horizon": np.asarray(idx > cutoff),
        }
    )
    for c in CALENDAR_COLUMNS:
        df[c] = cal[c].to_numpy()
    return df


def export(which: str) -> None:
    proto = load_protocol()
    verify_manifest()
    if which == "scored":
        require_frozen_v2(proto)
    data = DataV2()
    frames = [
        model_input_frame(data, zone, regime, cutoff)
        for regime in V2_REGIMES
        for zone in V2_ZONES
        for cutoff in origins(proto, which)
    ]
    df = pd.concat(frames, ignore_index=True)
    assert df.loc[df["is_horizon"], "y"].isna().all()  # no load after the cutoff leaves here
    out = ROOT / "data" / "model_inputs"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / f"{which}_v2.parquet", index=False)
    n = df.groupby(["unique_id", "regime", "cutoff"]).ngroups
    print(f"{which}_v2: {n} windows, {len(df)} rows")


# ------------------------------------------------------------------ core rows


def run(which: str, limit: int | None) -> None:
    proto = load_protocol()
    verify_manifest()
    out = out_dir(which) / "forecasts"
    if which == "scored":
        if limit:
            sys.exit("--limit is for the gate set; the scored set is run whole, once")
        for name in CORE_ROWS:
            require_frozen_v2(proto, out / f"{name}.parquet")
    elif which != "gate":
        sys.exit("protocol-v2 runs on the gate or the scored origins only")
    cutoffs = origins(proto, which)[:limit]
    data = DataV2()
    commit = git_commit()
    out.mkdir(parents=True, exist_ok=True)
    for name in CORE_ROWS:
        fn = V2_MODELS[name]
        frames = []
        for regime in V2_REGIMES:
            for zone in ROWS[name]["zones"]:
                for cutoff in cutoffs:
                    hist = data.history(zone, cutoff)
                    temp = data.temperature(zone, cutoff, regime)
                    t0 = time.perf_counter()
                    y_hat = fn(hist, temp, cutoff)
                    runtime = time.perf_counter() - t0
                    assert len(y_hat) == proto["horizon_hours"]
                    frames.append(
                        pd.DataFrame(
                            {
                                "model": name,
                                "unique_id": zone,
                                "regime": regime,
                                "cutoff": cutoff,
                                "ds": y_hat.index,
                                "y_hat": y_hat.to_numpy(),
                                "runtime_s": runtime,
                            }
                        )
                    )
        df = pd.concat(frames, ignore_index=True)
        df["git_commit"] = commit
        df["protocol_version"] = VERSION
        df["weather"] = ROWS[name]["weather"]
        df["calendar"] = ROWS[name]["calendar"]
        df.to_parquet(out / f"{name}.parquet", index=False)
        print(f"{name}: {len(cutoffs)} origins x {len(ROWS[name]['zones'])} zones x 4 regimes")


# ------------------------------------------------------------------ scoring


def expected_windows(cutoffs: list[pd.Timestamp]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            (m, z, r, c)
            for m, spec in ROWS.items()
            for z in spec["zones"]
            for r in V2_REGIMES
            for c in cutoffs
        ],
        columns=["model", "unique_id", "regime", "cutoff"],
    )


def compare(wide: pd.DataFrame, zone, regime, a_model, b_model, proto, b_regime=None):
    """Ratio of mean window errors, paired on the weeks both arms keep."""
    draws, seed = proto["bootstrap"]["draws"], proto["bootstrap"]["seed"]
    try:
        a = wide.loc[(zone, regime, a_model)]
        b = wide.loc[(zone, b_regime or regime, b_model)]
    except KeyError:
        return []
    weeks = a.index.intersection(b.index)
    if not len(weeks):
        return []
    a, b = a.loc[weeks], b.loc[weeks]
    out = []
    for col in ["mae", *DAY_COLS]:
        r, lo, hi = ratio_ci(a[col].to_numpy(), b[col].to_numpy(), draws, seed)
        out.append(
            {
                "unique_id": zone,
                "regime": regime,
                "model_a": a_model,
                "model_b": b_model,
                "metric": col,
                "n_windows": len(weeks),
                "ratio": r,
                "ci90_low": lo,
                "ci90_high": hi,
            }
        )
    return out


def registered_comparisons(win: pd.DataFrame, proto: dict) -> pd.DataFrame:
    bar = proto["primary_comparison"]["bar"]
    wide = win.set_index(["unique_id", "regime", "model", "cutoff"]).sort_index()
    rows = []

    def add(kind, label, zone, regime, a, b, b_regime=None, read=True):
        for r in compare(wide, zone, regime, a, b, proto, b_regime):
            v = verdict(r["ci90_low"], r["ci90_high"], bar)
            if kind == "primary":
                reading = PRIMARY_VERDICT[v]
            else:
                reading = READING[v] if read else ""
            rows.append({"kind": kind} | r | {"reading_10pct_bar": reading, "label": label})

    for zone in V2_ZONES:
        dev = zone in V2_DEVELOPMENT_ZONES
        for regime in V2_REGIMES:
            if not dev and regime == PRIMARY_REGIME:
                add("primary", f"PRIMARY ({VERSION})", zone, regime, CHALLENGER, BASELINE)
            else:
                kind = "development_primary_pair" if dev else "primary_pair_other_regime"
                lab = f"{'development' if dev else 'secondary'} ({VERSION})"
                add(kind, lab, zone, regime, CHALLENGER, BASELINE)
            lab = f"{'development' if dev else 'secondary'} ({VERSION})"
            for a, b in CALENDAR_PAIRS:
                add("calendar_vs_temperature_only", lab, zone, regime, a, b)
            if dev:
                continue
            for m in ROWS:
                if m not in (CHALLENGER, BASELINE):
                    add("vs_" + BASELINE, lab, zone, regime, m, BASELINE)
            for m in ("lag_regression_temperature", "lightgbm_competition"):
                add("chronos2_temperature_vs_" + m, lab, zone, regime, CHALLENGER, m)
            add("weather_gain", lab, zone, regime, CHALLENGER, "chronos2")
        for m in ROWS:
            if ROWS[m]["weather"] == "temperature" and zone in ROWS[m]["zones"]:
                for regime in V2_REGIMES:
                    if regime != ORACLE:
                        lab = f"{'development' if dev else 'secondary'} ({VERSION})"
                        add("forecast_vs_oracle_era5", lab, zone, regime, m, m, ORACLE, read=False)
    return pd.DataFrame(rows)


def holiday_breakdown(fc: pd.DataFrame, win: pd.DataFrame, data: DataV2) -> pd.DataFrame:
    """Pre-registered, descriptive: MAE on US federal holiday hours and on other hours (the
    harness calendar), per row, zone and regime, over the kept windows."""
    kept = win[["model", "unique_id", "regime", "cutoff"]]
    f = fc.merge(kept, on=["model", "unique_id", "regime", "cutoff"])
    parts = []
    for zone, g in f.groupby("unique_id"):
        g = g.copy()
        g["y"] = data.y[zone].reindex(pd.DatetimeIndex(g["ds"])).to_numpy()
        g["hol"] = calendar(pd.DatetimeIndex(g["ds"]))["hol"].to_numpy()
        parts.append(g)
    f = pd.concat(parts, ignore_index=True)
    f["ae"] = (f["y_hat"] - f["y"]).abs()
    f["hours"] = np.where(f["hol"] == 1, "us_federal_holiday", "other")
    return (
        f.groupby(["unique_id", "regime", "model", "hours"])["ae"]
        .agg(n_hours="size", mae="mean")
        .reset_index()
    )


def primary_md(stats: pd.DataFrame, win: pd.DataFrame, which: str) -> str:
    v2 = load_v2_protocol()["primary_comparison"]
    prim = stats[(stats["kind"] == "primary") & (stats["metric"] == "mae")]
    lines = [f"# protocol-v2 primary comparison ({which} set)", ""]
    if which != "scored":
        lines += [
            "Gate set: a pipeline check on the gate origins, not a result. The sentences "
            "below are filled in only to test the template.",
            "",
        ]
    fc_dates = win.loc[win["model"] == CHALLENGER, "weights_date"].dropna()
    weights_date = pd.Timestamp(fc_dates.iloc[0]) if len(fc_dates) else None
    for r in prim.itertuples():
        text = " ".join(v2["outcome_sentences"][r.reading_10pct_bar].split()).format(
            zone=r.unique_id,
            ratio=f"{r.ratio:.3f}",
            low=f"{r.ci90_low:.3f}",
            high=f"{r.ci90_high:.3f}",
            n=r.n_windows,
        )
        cut = win.loc[
            (win["model"] == CHALLENGER)
            & (win["unique_id"] == r.unique_id)
            & (win["regime"] == r.regime),
            "cutoff",
        ]
        n_after = int((cut > weights_date).sum()) if weights_date is not None else 0
        leak = " ".join(v2["leakage_statement"].split()).format(n_after=n_after, n=r.n_windows)
        lines += [f"**{r.unique_id}: {r.reading_10pct_bar}.** {text} {leak}", ""]
    return "\n".join(lines)


def score(which: str) -> None:
    verify_manifest()
    proto = load_protocol()
    if which == "scored":
        require_frozen_v2(proto)
    elif which != "gate":
        sys.exit("protocol-v2 is scored on the gate or the scored origins only")
    out = out_dir(which)
    fc = pd.concat(pd.read_parquet(p) for p in sorted((out / "forecasts").glob("*.parquet")))
    assert set(fc["model"]) <= set(ROWS), "only v2 rows are scored here"
    assert set(fc["regime"]) <= set(V2_REGIMES)
    assert (fc["protocol_version"] == VERSION).all()
    for col in ("weights_revision", "weights_date"):
        if col not in fc:
            fc[col] = None
    data = DataV2()
    win = window_metrics(fc, data)
    # A window a row should have produced but did not is incomplete too.
    cutoffs = sorted(set(fc["cutoff"]))
    exp = expected_windows(cutoffs)
    exp = exp[exp["model"].isin(set(fc["model"]))]
    keys = ["model", "unique_id", "regime", "cutoff"]
    missing = exp.merge(win[keys], on=keys, how="left", indicator=True)
    missing = missing[missing["_merge"] == "left_only"].drop(columns="_merge")
    bad = pd.concat([win.loc[~win["complete"], keys], missing], ignore_index=True)
    bad = bad.sort_values(["unique_id", "regime", "cutoff", "model"])
    bad.to_csv(out / "dropped_windows.csv", index=False)
    drop = set(map(tuple, bad[["unique_id", "regime", "cutoff"]].drop_duplicates().to_numpy()))
    k3 = zip(win["unique_id"], win["regime"], win["cutoff"], strict=True)
    win = win[[k not in drop for k in k3]].drop(columns="complete")
    win.to_parquet(out / "windows.parquet", index=False)

    lb = leaderboard(win, BASELINE)
    lb["calendar"] = lb["model"].map(lambda m: ROWS[m]["calendar"])
    lb["zone_role"] = np.where(lb["unique_id"].isin(V2_PRIMARY_ZONES), "primary", "development")
    gate = ", gate only" if which != "scored" else ""
    lb["label"] = [
        f"PRIMARY {'baseline' if m == BASELINE else 'challenger'} ({VERSION}{gate})"
        if m in (BASELINE, CHALLENGER) and z in V2_PRIMARY_ZONES and r == PRIMARY_REGIME
        else f"{'development' if z in V2_DEVELOPMENT_ZONES else 'secondary'} ({VERSION}{gate})"
        for m, z, r in zip(lb["model"], lb["unique_id"], lb["regime"], strict=True)
    ]
    lb = lb.sort_values(["zone_role", "unique_id", "regime", "mae"], ascending=[False] + [True] * 3)
    lb.round(4).to_csv(out / "leaderboard.csv", index=False)
    show = ["model", "unique_id", "regime", "n_windows", "mae", "ratio_vs_baseline", "runtime_s"]
    print(lb[show].round(3).to_string(index=False))
    print(f"\ndropped (zone, regime, cutoff): {len(drop)}")
    for z, r, c in sorted(drop):
        print(f"  {z} {r} {c}")

    stats = registered_comparisons(win, proto)
    stats.round(4).to_csv(out / "stats.csv", index=False)
    head = stats[stats["metric"] == "mae"].drop(columns=["metric", "label"])
    print("\n" + head.round(3).to_string(index=False))

    holiday_breakdown(fc, win, data).round(3).to_csv(out / "holiday_breakdown.csv", index=False)
    md = primary_md(stats, win, which)
    (out / "primary.md").write_text(md)
    print("\n" + md)


def main() -> None:
    args = sys.argv[1:]
    if (
        len(args) < 2
        or args[0] not in ("export", "run", "score")
        or args[1] not in ("gate", "scored")
    ):
        sys.exit(__doc__)
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    if args[0] == "export":
        export(args[1])
    elif args[0] == "run":
        run(args[1], limit)
    else:
        score(args[1])


if __name__ == "__main__":
    main()
