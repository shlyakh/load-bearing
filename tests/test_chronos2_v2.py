"""Lookahead and calendar checks for the protocol-v2 Chronos-2 rows (models/chronos2.py
--v2). Gate origins only. Runs in the models environment; skipped in core:

    uv run --project models --with pytest pytest tests/test_chronos2_v2.py -q

The pipeline is replaced by a recorder, so the test sees exactly what the adapter hands
Chronos-2 and does not run the model.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("chronos")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models"))

import chronos2 as adapter  # noqa: E402
from harness.data import calendar  # noqa: E402

INPUTS = ROOT / "data" / "model_inputs" / "gate_v2.parquet"
pytestmark = pytest.mark.skipif(not INPUTS.exists(), reason="run harness.v2 export gate first")


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def predict_df(self, df, future_df=None, prediction_length=168, **kw):
        self.calls.append(
            {"df": df.copy(), "future_df": None if future_df is None else future_df.copy()}
        )
        ids = df["unique_id"].unique()
        rows = []
        for uid in ids:
            last = df.loc[df["unique_id"] == uid, "ds_naive"].max()
            ds = pd.date_range(last + pd.Timedelta(hours=1), periods=prediction_length, freq="h")
            rows.append(pd.DataFrame({"unique_id": uid, "ds_naive": ds}))
        out = pd.concat(rows, ignore_index=True)
        for q in ("0.1", "0.5", "0.9"):
            out[q] = 1.0
        return out


@pytest.fixture(scope="module")
def inputs() -> pd.DataFrame:
    df = pd.read_parquet(INPUTS)
    first = sorted(df["cutoff"].unique())[:2]
    return df[df["cutoff"].isin(first)].reset_index(drop=True)


def test_calendar_handed_to_chronos_is_the_harness_calendar(inputs):
    rec = Recorder()
    rows = adapter.forecast_v2(rec, inputs)
    assert set(rows) == {"chronos2_temperature", "chronos2_temperature_calendar", "chronos2"}
    cal_calls = [c for c in rec.calls if "hol" in c["df"].columns]
    assert cal_calls
    for call in cal_calls:
        for frame in (call["df"], call["future_df"]):
            ds = pd.DatetimeIndex(frame["ds_naive"]).tz_localize("UTC")
            cal = calendar(ds)
            # numeric 0/1 for holiday and year-end, strings for day of week and hour
            assert frame["hol"].dtype == float and frame["yearend"].dtype == float
            assert frame["dow"].map(type).eq(str).all() and frame["hour"].map(type).eq(str).all()
            assert np.array_equal(frame["hol"].to_numpy(), cal["hol"].to_numpy())
            assert np.array_equal(frame["yearend"].to_numpy(), cal["yearend"].to_numpy())
            assert np.array_equal(frame["dow"].astype(int).to_numpy(), cal["dow"].to_numpy())
            assert np.array_equal(frame["hour"].astype(int).to_numpy(), cal["hour"].to_numpy())
        assert set(call["df"].columns) == {
            "unique_id",
            "ds_naive",
            "y",
            "T",
            "hol",
            "yearend",
            "dow",
            "hour",
        }
        assert "y" not in call["future_df"].columns


def test_context_stops_at_cutoff_and_future_has_no_load(inputs):
    rec = Recorder()
    adapter.forecast_v2(rec, inputs)
    cut = set(pd.to_datetime(inputs["cutoff"]).dt.tz_convert("UTC").dt.tz_localize(None))
    for call in rec.calls:
        df, fut = call["df"], call["future_df"]
        for _, g in df.groupby("unique_id"):
            assert len(g) == adapter.CONTEXT_HOURS
            assert g["ds_naive"].max() in cut
        if fut is None:  # univariate row: no covariates at all
            assert set(df.columns) == {"unique_id", "ds_naive", "y"}
            assert set(df["unique_id"]) <= {"AEP", "AE"}
            continue
        assert "y" not in fut.columns
        assert fut.groupby("unique_id").size().eq(168).all()


def test_corrupting_horizon_load_changes_nothing(inputs):
    a, b = Recorder(), Recorder()
    adapter.forecast_v2(a, inputs)
    bad = inputs.copy()
    bad.loc[bad["is_horizon"], "y"] = -9999.0
    adapter.forecast_v2(b, bad)
    assert len(a.calls) == len(b.calls)
    for x, y in zip(a.calls, b.calls, strict=True):
        pd.testing.assert_frame_equal(x["df"], y["df"])


def test_incomplete_horizon_temperature_is_not_forecast(inputs):
    df = inputs.copy()
    c0 = sorted(df["cutoff"].unique())[0]
    hit = (df["cutoff"] == c0) & (df["unique_id"] == "AE") & (df["regime"] == "forecast_aifs")
    hz = hit & df["is_horizon"]
    df.loc[df.index[hz][40], "T"] = np.nan
    rows = adapter.forecast_v2(Recorder(), df)
    for name in ("chronos2_temperature", "chronos2_temperature_calendar"):
        out = rows[name]
        sel = (
            (out["cutoff"] == c0) & (out["unique_id"] == "AE") & (out["regime"] == "forecast_aifs")
        )
        assert sel.sum() == 168 and out.loc[sel, "0.5"].isna().all()
        other = (
            (out["cutoff"] == c0) & (out["unique_id"] == "AEP") & (out["regime"] == "forecast_aifs")
        )
        assert out.loc[other, "0.5"].notna().all()


def test_scored_set_is_refused_without_the_tag():
    if subprocess.run(
        ["git", "tag", "--list", "protocol-v2"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip():
        pytest.skip("tag protocol-v2 exists")
    r = subprocess.run(
        [sys.executable, str(ROOT / "models" / "chronos2.py"), "scored", "--v2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and "must not be run yet" in r.stderr
