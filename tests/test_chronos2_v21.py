"""Lookahead and encoding checks for the protocol-v2.1 Chronos-2 rows (models/chronos2.py
--v21). Gate origins only. Runs in the models environment; skipped in core:

    uv run --project models --with pytest pytest tests/test_chronos2_v21.py -q

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
from test_chronos2_v2 import Recorder  # noqa: E402

INPUTS = ROOT / "data" / "model_inputs" / "gate_v2.parquet"
pytestmark = pytest.mark.skipif(not INPUTS.exists(), reason="run harness.v2 export gate first")


@pytest.fixture(scope="module")
def inputs() -> pd.DataFrame:
    df = pd.read_parquet(INPUTS)
    first = sorted(df["cutoff"].unique())[:2]
    return df[df["cutoff"].isin(first) & (df["regime"] == "forecast_aifs")].reset_index(drop=True)


def calls_by_row(rec: Recorder) -> dict[str, list[dict]]:
    """The recorder sees one call per row, regime and cutoff, in V21_ROWS order."""
    names = list(adapter.V21_ROWS)
    return {n: rec.calls[i :: len(names)] for i, n in enumerate(names)}


def test_each_row_gets_exactly_its_registered_columns(inputs):
    rec = Recorder()
    rows = adapter.forecast_v21(rec, inputs)
    assert set(rows) == set(adapter.V21_ROWS)
    for name, calls in calls_by_row(rec).items():
        cov = adapter.V21_ROWS[name]["covariates"]
        for call in calls:
            assert set(call["df"].columns) == {"unique_id", "ds_naive", "y", *cov}
            assert set(call["future_df"].columns) == {"unique_id", "ds_naive", *cov}
            for _, g in call["df"].groupby("unique_id"):
                assert len(g) == adapter.CONTEXT_HOURS
            assert call["future_df"].groupby("unique_id").size().eq(168).all()
            assert call["future_df"][cov].notna().all().all()


def test_ordinal_and_cyclic_are_the_harness_calendar(inputs):
    rec = Recorder()
    adapter.forecast_v21(rec, inputs)
    by = calls_by_row(rec)
    for call in by["chronos2_temperature_calendar_ordinal"]:
        for frame in (call["df"], call["future_df"]):
            cal = calendar(pd.DatetimeIndex(frame["ds_naive"]).tz_localize("UTC"))
            assert np.array_equal(frame["cal_hour"].to_numpy(), cal["hour"].to_numpy())
            assert np.array_equal(frame["cal_dow"].to_numpy(), cal["dow"].to_numpy())
            assert np.array_equal(frame["hol"].to_numpy(), cal["hol"].to_numpy())
            assert np.array_equal(frame["yearend"].to_numpy(), cal["yearend"].to_numpy())
    for call in by["chronos2_temperature_calendar_cyclic"]:
        for frame in (call["df"], call["future_df"]):
            cal = calendar(pd.DatetimeIndex(frame["ds_naive"]).tz_localize("UTC"))
            assert np.allclose(frame["hour_sin"], np.sin(2 * np.pi * cal["hour"].to_numpy() / 24))
            assert np.allclose(frame["dow_cos"], np.cos(2 * np.pi * cal["dow"].to_numpy() / 7))


def test_target_encodings_are_context_means(inputs):
    rec = Recorder()
    adapter.forecast_v21(rec, inputs)
    call = calls_by_row(rec)["chronos2_temperature_calendar_target2"][0]
    zone = call["df"]["unique_id"].iloc[0]
    ctx = call["df"][call["df"]["unique_id"] == zone]
    fut = call["future_df"][call["future_df"]["unique_id"] == zone]
    cal_c = calendar(pd.DatetimeIndex(ctx["ds_naive"]).tz_localize("UTC"))
    cal_f = calendar(pd.DatetimeIndex(fut["ds_naive"]).tz_localize("UTC"))
    means = ctx["y"].groupby([cal_c["hour"].to_numpy(), cal_c["dow"].to_numpy()]).mean()
    want = [means[(h, d)] for h, d in zip(cal_f["hour"], cal_f["dow"], strict=True)]
    assert np.allclose(fut["te_hour_dow"].to_numpy(), want)
    # the context rows carry the same cell means
    want_c = [means[(h, d)] for h, d in zip(cal_c["hour"], cal_c["dow"], strict=True)]
    assert np.allclose(ctx["te_hour_dow"].to_numpy(), want_c)


def test_holiday_counts_as_sunday_and_missing_cells_fall_back():
    ds = pd.date_range("2025-07-07 05:00", periods=24 * 21 + 24, freq="h", tz="UTC")  # no holiday
    cal = calendar(ds)
    win = pd.DataFrame(
        {"unique_id": "Z", "ds": ds, "y": np.arange(len(ds), dtype=float), "T": 0.0}
    ).join(cal.reset_index(drop=True))
    win["is_horizon"] = np.arange(len(ds)) >= 24 * 21
    win.loc[win["is_horizon"], "hol"] = 1.0  # a holiday in the horizon, none in the context
    enc = adapter.encode_v21(win)
    ctx = win[~win["is_horizon"]]
    sunday = ctx[ctx["dow"] == 6].groupby("hour")["y"].mean()
    hz = enc[enc["is_horizon"]]
    want = sunday.reindex(hz["hour"].astype(int)).to_numpy()
    assert np.allclose(hz["te_hour_daytype"].to_numpy(), want)  # holiday read as a Sunday
    assert np.allclose(hz["te_hour_hol"].to_numpy(), want)  # no holiday in context: Sunday mean


def test_corrupting_horizon_load_changes_nothing(inputs):
    a, b = Recorder(), Recorder()
    adapter.forecast_v21(a, inputs)
    bad = inputs.copy()
    bad.loc[bad["is_horizon"], "y"] = -9999.0
    adapter.forecast_v21(b, bad)
    assert len(a.calls) == len(b.calls)
    for x, y in zip(a.calls, b.calls, strict=True):
        pd.testing.assert_frame_equal(x["df"], y["df"])
        pd.testing.assert_frame_equal(x["future_df"], y["future_df"])


def test_scored_set_is_refused_without_the_tag():
    if subprocess.run(
        ["git", "tag", "--list", "protocol-v2.1"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip():
        pytest.skip("tag protocol-v2.1 exists")
    r = subprocess.run(
        [sys.executable, str(ROOT / "models" / "chronos2.py"), "scored", "--v21"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and "must not be run yet" in r.stderr
