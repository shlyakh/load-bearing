"""Chronos-2 through the direct adapter, with and without temperature.

    uv run --project models python models/chronos2.py gate
    uv run --project models python models/chronos2.py scored
    uv run --project models python models/chronos2.py scored --gap48
    uv run --project models python models/chronos2.py gate --v12   # protocol-v1.2 regimes

Reads only data/model_inputs/<set>.parquet, which the harness writes. The harness owns
the cutoffs: this script loops over the cutoffs in that file and calls the model once
per cutoff (both zones in one call, no cross-learning).

Settings, fixed on 2026-11-13 before any scored run and not tuned:
  context 2,048 hours; temperature as past and known-future covariate; no cross-learning;
  point forecast = median; quantiles 0.1 / 0.5 / 0.9; CPU.
Rows written: chronos2_temperature (both regimes) and chronos2 (no weather, identical in
both regimes).

With --gap48 (pre-registered secondary, protocol.yaml): the load context ends 48 hours
before the cutoff, the model forecasts 216 hours and the last 168 are kept. Weather is
unchanged: reanalysis temperature up to the cutoff, the regime's series after it. Row
written: chronos2_temperature_gap48.

With --v12 (protocol-v1.2, secondary): reads data/model_inputs/<set>_weather_v12.parquet
(ERA5 history, the four v1.2 regimes) and writes only chronos2_temperature, to
results/<set>/weather_v12/forecasts/. Same pinned weights and settings. A zone-window
whose horizon temperature is incomplete is not forecast (y_hat missing), so the per-regime
drop rule removes it for every model in that regime.

With --v2 (protocol-v2.yaml): reads data/model_inputs/<set>_v2.parquet (zones AEP, AE, DOM,
JC; the four v1.2 regime names; the harness calendar table beside y and T) and writes to
results/<set>/v2/forecasts/ three rows, same pinned weights and settings:
  chronos2_temperature            all four zones (temperature only)
  chronos2_temperature_calendar   all four zones: temperature plus the harness calendar as
                                  known-future covariates, holiday and year-end numeric 0/1,
                                  day of week and hour categorical (strings). Not tuned.
  chronos2                        AEP and AE, no covariates (identical in every regime)
A zone-window with incomplete horizon temperature is not forecast by the temperature rows.
The scored set is refused unless the git tag protocol-v2 exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from chronos import Chronos2Pipeline

ROOT = Path(__file__).resolve().parent.parent
REPO_ID = "amazon/chronos-2"
CONTEXT_HOURS = 2048
QUANTILES = [0.1, 0.5, 0.9]
GAP_HOURS = 48


def git_commit() -> str:
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()

    dirty = "-dirty" if git("status", "--porcelain", "--untracked-files=no") else ""
    return git("rev-parse", "--short", "HEAD") + dirty


# ------------------------------------------------------------------ protocol-v2
V2_VERSION = "protocol-v2"
V2_NUMERIC = ["hol", "yearend"]  # harness calendar, 0/1
V2_CATEGORICAL = ["dow", "hour"]  # harness calendar, passed as strings (categorical)
V2_CALENDAR = ["hour", "dow", "hol", "yearend"]  # the columns of harness.data.calendar
V2_ROWS = {
    "chronos2_temperature": {"zones": ("AEP", "AE", "DOM", "JC"), "covariates": ["T"]},
    "chronos2_temperature_calendar": {
        "zones": ("AEP", "AE", "DOM", "JC"),
        "covariates": ["T", *V2_NUMERIC, *V2_CATEGORICAL],
    },
    "chronos2": {"zones": ("AEP", "AE"), "covariates": []},
}
V2_CALENDAR_LABEL = {
    "chronos2_temperature": "none",
    "chronos2_temperature_calendar": "harness: hour, day of week (categorical), holiday, "
    "year-end (0/1)",
    "chronos2": "none",
}


def encode_v2(win: pd.DataFrame) -> pd.DataFrame:
    """The harness calendar in the encoding registered for chronos2_temperature_calendar:
    holiday and year-end as numbers, day of week and hour as strings. Values unchanged."""
    win = win.copy()
    for c in V2_NUMERIC:
        win[c] = win[c].astype(float)
    for c in V2_CATEGORICAL:
        win[c] = win[c].astype(int).astype(str)
    return win


def predict_v2(pipe, win: pd.DataFrame, covariates: list[str]) -> tuple[pd.DataFrame, float]:
    """One call for the zones in `win` (no cross-learning). Context: the last CONTEXT_HOURS
    rows up to the cutoff (y and covariates); future: the 168 horizon rows (covariates only,
    never y)."""
    hist = win[~win["is_horizon"]].groupby("unique_id").tail(CONTEXT_HOURS)
    fut = win[win["is_horizon"]]
    t0 = time.perf_counter()
    pred = pipe.predict_df(
        hist[["unique_id", "ds_naive", "y", *covariates]],
        future_df=fut[["unique_id", "ds_naive", *covariates]] if covariates else None,
        id_column="unique_id",
        timestamp_column="ds_naive",
        target="y",
        prediction_length=168,
        quantile_levels=QUANTILES,
        cross_learning=False,
    )
    runtime = (time.perf_counter() - t0) / win["unique_id"].nunique()
    out = fut[["unique_id", "ds", "ds_naive"]].merge(pred, on=["unique_id", "ds_naive"])
    assert len(out) == len(fut), "forecast timestamps do not match the horizon"
    return out, runtime


def forecast_v2(pipe, inputs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """All v2 Chronos-2 rows for the windows in `inputs` (the exported v2 model inputs)."""
    inputs = encode_v2(inputs)
    if "ds_naive" not in inputs:
        inputs["ds_naive"] = inputs["ds"].dt.tz_localize(None)
    nan_q = {"0.1": float("nan"), "0.5": float("nan"), "0.9": float("nan")}
    rows = {name: [] for name in V2_ROWS}
    for cutoff in sorted(inputs["cutoff"].unique()):
        at = inputs[inputs["cutoff"] == cutoff]
        for regime, win in at.groupby("regime"):
            hz_t = win.loc[win["is_horizon"]].groupby("unique_id")["T"]
            ok = set(hz_t.apply(lambda t: bool(t.notna().all())).loc[lambda x: x].index)
            for name in ("chronos2_temperature", "chronos2_temperature_calendar"):
                spec = V2_ROWS[name]
                zw = win[win["unique_id"].isin(spec["zones"])]
                full = zw[zw["unique_id"].isin(ok)]
                if len(full):
                    out, rt = predict_v2(pipe, full, spec["covariates"])
                    rows[name].append(out.assign(regime=regime, cutoff=cutoff, runtime_s=rt))
                gap = zw[~zw["unique_id"].isin(ok) & zw["is_horizon"]]
                if len(gap):  # incomplete horizon temperature: not forecast
                    rows[name].append(
                        gap[["unique_id", "ds", "ds_naive"]].assign(
                            **nan_q, regime=regime, cutoff=cutoff, runtime_s=float("nan")
                        )
                    )
        # Univariate: the load context is the same in every regime, so predict once.
        uni = at[at["unique_id"].isin(V2_ROWS["chronos2"]["zones"])]
        ref = uni[uni["regime"] == "oracle_era5"]
        for _, other in uni.groupby("regime"):
            assert other["y"].reset_index(drop=True).equals(ref["y"].reset_index(drop=True))
        out, rt = predict_v2(pipe, ref, [])
        for regime in sorted(uni["regime"].unique()):
            rows["chronos2"].append(out.assign(regime=regime, cutoff=cutoff, runtime_s=rt))
    return {name: pd.concat(parts, ignore_index=True) for name, parts in rows.items()}


def run_v2(which: str) -> None:
    base = (ROOT / "results" if which == "scored" else ROOT / "results" / which) / "v2"
    if which == "scored":
        tag = subprocess.run(
            ["git", "tag", "--list", V2_VERSION], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        if not tag:
            sys.exit("git tag protocol-v2 does not exist: scored origins must not be run yet")
        if git_commit().endswith("-dirty"):
            sys.exit("commit the code before a scored run")
        for name in V2_ROWS:
            if (base / "forecasts" / f"{name}.parquet").exists():
                sys.exit(f"scored v2 {name} forecasts exist: the scored set is run once")
    elif which != "gate":
        sys.exit("protocol-v2 runs on the gate or the scored origins only")
    pin = json.loads((ROOT / "models" / "pins.json").read_text())[REPO_ID]
    pipe = Chronos2Pipeline.from_pretrained(
        REPO_ID, revision=pin["revision"], cache_dir=ROOT / "models_cache", device_map="cpu"
    )
    inputs = pd.read_parquet(ROOT / "data" / "model_inputs" / f"{which}_v2.parquet")
    commit = git_commit()
    rows = forecast_v2(pipe, inputs)
    (base / "forecasts").mkdir(parents=True, exist_ok=True)
    for name, df in rows.items():
        df = df.rename(columns={"0.5": "y_hat", "0.1": "q10", "0.9": "q90"})
        df["model"] = name
        df["weather"] = "temperature" if "temperature" in name else "none"
        df["calendar"] = V2_CALENDAR_LABEL[name]
        df["git_commit"] = commit
        df["protocol_version"] = V2_VERSION
        df["weights_revision"] = pin["revision"]
        df["weights_date"] = pin["weights_date"]
        df["context_hours"] = CONTEXT_HOURS
        keep = [
            "model",
            "unique_id",
            "regime",
            "cutoff",
            "ds",
            "y_hat",
            "q10",
            "q90",
            "runtime_s",
            "git_commit",
            "protocol_version",
            "weather",
            "calendar",
            "weights_revision",
            "weights_date",
            "context_hours",
        ]
        df[keep].to_parquet(base / "forecasts" / f"{name}.parquet", index=False)
        print(name, len(df), "rows")


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if sys.argv[2:] == ["--v2"]:
        run_v2(which)
        return
    gap48 = sys.argv[2:] == ["--gap48"]
    v12 = sys.argv[2:] == ["--v12"]
    if which not in ("gate", "ordering_gate", "scored") or (sys.argv[2:] and not (gap48 or v12)):
        sys.exit(__doc__)
    base = ROOT / "results" if which == "scored" else ROOT / "results" / which
    if v12:
        base = base / "weather_v12"
        if which == "scored":
            tag = subprocess.run(
                ["git", "tag", "--list", "protocol-v1.2"], cwd=ROOT, capture_output=True, text=True
            ).stdout.strip()
            if not tag:
                sys.exit("git tag protocol-v1.2 does not exist: scored origins must not be run yet")
            if (base / "forecasts" / "chronos2_temperature.parquet").exists():
                sys.exit("scored v1.2 Chronos-2 forecasts exist: the scored set is run once")
    pin = json.loads((ROOT / "models" / "pins.json").read_text())[REPO_ID]
    pipe = Chronos2Pipeline.from_pretrained(
        REPO_ID, revision=pin["revision"], cache_dir=ROOT / "models_cache", device_map="cpu"
    )
    suffix = "_weather_v12" if v12 else ""
    inputs = pd.read_parquet(ROOT / "data" / "model_inputs" / f"{which}{suffix}.parquet")
    inputs["ds_naive"] = inputs["ds"].dt.tz_localize(None)  # UTC wall time for the library
    commit = git_commit()

    def predict(win: pd.DataFrame, use_temperature: bool) -> tuple[pd.DataFrame, float]:
        hist = win[~win["is_horizon"]].groupby("unique_id").tail(CONTEXT_HOURS)
        fut = win[win["is_horizon"]]
        cols = ["unique_id", "ds_naive", "y"] + (["T"] if use_temperature else [])
        t0 = time.perf_counter()
        pred = pipe.predict_df(
            hist[cols],
            future_df=fut[["unique_id", "ds_naive", "T"]] if use_temperature else None,
            id_column="unique_id",
            timestamp_column="ds_naive",
            target="y",
            prediction_length=168,
            quantile_levels=QUANTILES,
            cross_learning=False,
        )
        runtime = (time.perf_counter() - t0) / win["unique_id"].nunique()
        out = fut[["unique_id", "ds", "ds_naive"]].merge(pred, on=["unique_id", "ds_naive"])
        assert len(out) == len(fut), "forecast timestamps do not match the horizon"
        return out, runtime

    def predict_gap48(win: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        cutoff = win["cutoff"].iloc[0]
        seen = win["ds"] <= cutoff - pd.Timedelta(hours=GAP_HOURS)
        hist = win[seen].groupby("unique_id").tail(CONTEXT_HOURS)
        ahead = win[~seen]  # 48 gap hours (reanalysis temperature) + 168 horizon hours
        assert ahead.groupby("unique_id").size().eq(GAP_HOURS + 168).all()
        t0 = time.perf_counter()
        pred = pipe.predict_df(
            hist[["unique_id", "ds_naive", "y", "T"]],
            future_df=ahead[["unique_id", "ds_naive", "T"]],
            id_column="unique_id",
            timestamp_column="ds_naive",
            target="y",
            prediction_length=GAP_HOURS + 168,
            quantile_levels=QUANTILES,
            cross_learning=False,
        )
        runtime = (time.perf_counter() - t0) / win["unique_id"].nunique()
        fut = win[win["is_horizon"]]
        out = fut[["unique_id", "ds", "ds_naive"]].merge(pred, on=["unique_id", "ds_naive"])
        assert len(out) == len(fut), "forecast timestamps do not match the horizon"
        return out, runtime

    rows = (
        {"chronos2_temperature_gap48": []}
        if gap48
        else {"chronos2_temperature": []}
        if v12
        else {"chronos2_temperature": [], "chronos2": []}
    )
    cutoffs = sorted(inputs["cutoff"].unique())
    for i, cutoff in enumerate(cutoffs):
        at = inputs[inputs["cutoff"] == cutoff]
        if gap48:
            for regime, win in at.groupby("regime"):
                out, rt = predict_gap48(win)
                rows["chronos2_temperature_gap48"].append(
                    out.assign(regime=regime, cutoff=cutoff, runtime_s=rt)
                )
            continue
        if v12:
            for regime, win in at.groupby("regime"):
                hz_t = win.loc[win["is_horizon"]].groupby("unique_id")["T"]
                ok = hz_t.apply(lambda t: bool(t.notna().all())).loc[lambda x: x].index
                full = win[win["unique_id"].isin(ok)]
                if len(full):
                    out, rt = predict(full, use_temperature=True)
                    rows["chronos2_temperature"].append(
                        out.assign(regime=regime, cutoff=cutoff, runtime_s=rt)
                    )
                gap = win[~win["unique_id"].isin(ok) & win["is_horizon"]]
                if len(gap):  # incomplete horizon temperature: not forecast
                    rows["chronos2_temperature"].append(
                        gap[["unique_id", "ds", "ds_naive"]].assign(
                            **{"0.1": float("nan"), "0.5": float("nan"), "0.9": float("nan")},
                            regime=regime,
                            cutoff=cutoff,
                            runtime_s=float("nan"),
                        )
                    )
            if (i + 1) % 10 == 0 or i + 1 == len(cutoffs):
                print(f"{i + 1}/{len(cutoffs)} cutoffs", flush=True)
            continue
        for regime, win in at.groupby("regime"):
            out, rt = predict(win, use_temperature=True)
            rows["chronos2_temperature"].append(
                out.assign(regime=regime, cutoff=cutoff, runtime_s=rt)
            )
        # No weather: the inputs are the same in both regimes, so predict once.
        out, rt = predict(at[at["regime"] == "oracle"], use_temperature=False)
        for regime in sorted(at["regime"].unique()):
            rows["chronos2"].append(out.assign(regime=regime, cutoff=cutoff, runtime_s=rt))
        if (i + 1) % 10 == 0 or i + 1 == len(cutoffs):
            print(f"{i + 1}/{len(cutoffs)} cutoffs", flush=True)

    (base / "forecasts").mkdir(parents=True, exist_ok=True)
    for name, parts in rows.items():
        df = pd.concat(parts, ignore_index=True)
        df = df.rename(columns={"0.5": "y_hat", "0.1": "q10", "0.9": "q90"})
        df["model"] = name
        df["weather"] = "temperature" if "temperature" in name else "none"
        df["git_commit"] = commit
        df["protocol_version"] = "protocol-v1.2" if v12 else "protocol-v1"
        df["weights_revision"] = pin["revision"]
        df["weights_date"] = pin["weights_date"]
        df["context_hours"] = CONTEXT_HOURS
        keep = [
            "model",
            "unique_id",
            "regime",
            "cutoff",
            "ds",
            "y_hat",
            "q10",
            "q90",
            "runtime_s",
            "git_commit",
            "protocol_version",
            "weather",
            "weights_revision",
            "weights_date",
            "context_hours",
        ]
        df[keep].to_parquet(base / "forecasts" / f"{name}.parquet", index=False)
        print(name, len(df), "rows")


if __name__ == "__main__":
    main()
