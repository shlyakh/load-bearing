"""Gate checks for protocol-v2 (protocol-v2.yaml). Gate origins only, never the scored ones.

uv run --project core pytest tests -q

Covered here (core environment): the weather points and weights, the weighted zone mean,
what DataV2 hands a model in the four regimes for the four zones, lookahead for every core
v2 row (corrupting load after the cutoff and every disallowed weather value changes no
forecast), incomplete horizon temperature, the v2 model-inputs export (its calendar is
harness.data.calendar), and the scored-set guards. The Chronos-2 adapter is checked in
tests/test_chronos2_v2.py (models environment).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch  # noqa: E402
from harness import v2  # noqa: E402
from harness.baselines import MODELS, V2_MODELS, vanilla_benchmark_trend_holiday  # noqa: E402
from harness.data import (  # noqa: E402
    PROCESSED,
    ROOT,
    V2_PARQUET,
    V2_PRIMARY_ZONES,
    V2_REGIMES,
    V2_ZONES,
    Data,
    DataV2,
    calendar,
    horizon_index,
    load_protocol,
    origins,
)

PROTO = load_protocol()
GATE = origins(PROTO, "gate")
H = pd.Timedelta(hours=1)
FORECAST = ("forecast_gfs", "forecast_ifs", "forecast_aifs")

needs_v2_data = pytest.mark.skipif(
    not (PROCESSED / V2_PARQUET["load"]).exists(), reason="run fetch.py process-v2 first"
)


@pytest.fixture(scope="module")
def data() -> DataV2:
    return DataV2()


def source_tables(data: DataV2, zone: str) -> dict[str, pd.DataFrame]:
    return {"forecast_gfs": data.forecast[zone]} | {
        r: data.forecast_v12[r][zone] for r in ("forecast_ifs", "forecast_aifs")
    }


# ------------------------------------------------------------------ definitions


def test_weather_points_and_weights_match_the_draft_and_sum_to_one():
    pts = fetch.weather_points_v2()
    draft = yaml.safe_load((ROOT / "protocol-v2-draft.yaml").read_text())["zones"]["selected"]
    assert set(pts) == {"AEP", "AE"}
    for zone, points in pts.items():
        assert points == draft[zone]["weather_points"]
        assert abs(sum(p["weight"] for p in points) - 1.0) < 1e-12
    assert [p["weight"] for p in pts["AEP"]] == [0.234, 0.227, 0.226, 0.162, 0.151]
    assert [p["weight"] for p in pts["AE"]] == [1.0]


def test_fetch_and_harness_agree_on_files_and_regimes():
    assert fetch.V2_PARQUET == V2_PARQUET
    assert set(fetch.V2_FORECAST_MODELS) | {"oracle_era5"} == set(V2_REGIMES)
    assert fetch.V2_FORECAST_MODELS["forecast_aifs"] == "ecmwf_aifs025_single"


def test_rows_and_zones_are_as_registered():
    assert set(v2.ROWS) == {
        "vanilla_benchmark_trend",
        "chronos2_temperature",
        "vanilla_benchmark_trend_holiday",
        "chronos2_temperature_calendar",
        "lag_regression_temperature",
        "lightgbm_competition",
        "chronos2",
    }
    for m in ("vanilla_benchmark_trend_holiday", "chronos2_temperature_calendar"):
        assert v2.ROWS[m]["zones"] == V2_ZONES  # also on the development zones
    assert (v2.BASELINE, v2.CHALLENGER, v2.PRIMARY_REGIME) == (
        "vanilla_benchmark_trend",
        "chronos2_temperature",
        "forecast_aifs",
    )
    # The v1 model list (harness.run default) is unchanged by v2.
    assert "vanilla_benchmark_trend_holiday" not in MODELS


def test_weighted_zone_mean_unit():
    idx = pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC")
    a = pd.DataFrame({"temperature_2m": [0.0, 10.0, np.nan]}, index=idx)
    b = pd.DataFrame({"temperature_2m": [10.0, 20.0, 5.0]}, index=idx)
    m = fetch.weighted_zone_mean([a, b], [0.25, 0.75])
    assert np.allclose(m["temperature_2m"].to_numpy()[:2], [7.5, 17.5])
    assert np.isnan(m["temperature_2m"].iloc[2])  # a zone value needs every point
    with pytest.raises(ValueError):
        fetch.weighted_zone_mean([a, b], [0.5, 0.6])


@needs_v2_data
@pytest.mark.parametrize("zone", ["AEP", "AE"])
def test_weighted_mean_uses_protocol_weights(data, zone):
    """Recompute the zone series from the raw point files with the protocol weights."""
    pts = fetch.weather_points_v2()[zone]
    w = np.array([p["weight"] for p in pts])
    era5 = [
        fetch._station_frame(fetch.RAW_MODELS / "era5" / f"archive_{zone}_{p['name']}.json")
        for p in pts
    ]
    stacked = np.column_stack([f["temperature_2m"].to_numpy(float) for f in era5])
    expected = pd.Series(stacked @ w, index=era5[0].index)
    got = data.era5[zone].reindex(expected.index)
    ok = expected.notna()
    assert ok.mean() > 0.99
    assert np.allclose(got[ok].to_numpy(), expected[ok].to_numpy(), atol=1e-9)
    # And for a forecast source at one lead day.
    model = fetch.V2_FORECAST_MODELS["forecast_aifs"]
    prev = [
        pd.concat(
            fetch._station_frame(f)
            for f in sorted(
                (fetch.RAW_MODELS / model).glob(f"previous_runs_{zone}_{p['name']}_*.json")
            )
        ).astype(float)
        for p in pts
    ]
    col = "temperature_2m_previous_day3"
    stacked = np.column_stack([f[col].to_numpy() for f in prev])
    expected = pd.Series(stacked @ w, index=prev[0].index).dropna()
    tab = data.forecast_v12["forecast_aifs"][zone][3].reindex(expected.index)
    assert np.allclose(tab.to_numpy(), expected.to_numpy(), atol=1e-9)


# ------------------------------------------------------------------ what a model sees


@needs_v2_data
@pytest.mark.parametrize("regime", V2_REGIMES)
def test_v2_inputs_stop_at_cutoff_and_history_is_era5(data, regime):
    for zone in V2_ZONES:
        for c in GATE:
            assert data.history(zone, c).index.max() <= c
            temp = data.temperature(zone, c, regime)
            assert temp.index.max() == c + 168 * H
            assert temp.index.is_unique and temp.index.is_monotonic_increasing
            assert temp.loc[:c].equals(data.era5[zone].loc[:c])
            assert temp.loc[c + H :].notna().all()  # gate horizons are complete


@needs_v2_data
def test_v2_refuses_v1_regimes_and_unknown_zones(data):
    with pytest.raises(ValueError):
        data.temperature("AEP", GATE[0], "forecast")
    with pytest.raises(ValueError):
        data.temperature("PE", GATE[0], "oracle_era5")


@needs_v2_data
def test_development_zones_are_unchanged_from_v12(data):
    """DOM and JC keep their v1 points, unweighted mean and v1.2 files."""
    old = Data()
    old._load_v12()
    for zone in ("DOM", "JC"):
        for regime in V2_REGIMES:
            for c in GATE:
                pd.testing.assert_series_equal(
                    data.temperature(zone, c, regime), old.temperature(zone, c, regime)
                )
                pd.testing.assert_series_equal(data.history(zone, c), old.history(zone, c))


@needs_v2_data
@pytest.mark.parametrize("regime", FORECAST)
def test_v2_forecast_regimes_use_lead_matched_values(data, regime):
    for zone in V2_PRIMARY_ZONES:
        c = GATE[0]
        hz = horizon_index(c)
        temp = data.temperature(zone, c, regime).reindex(hz)
        tab = source_tables(data, zone)[regime]
        for k in range(1, 8):
            hours = hz[24 * (k - 1) : 24 * k]
            assert np.allclose(temp.loc[hours].to_numpy(), tab.loc[hours, k].to_numpy())
        assert not np.allclose(temp.to_numpy(), data.era5[zone].reindex(hz).to_numpy())


def _corrupt(data: DataV2, zone: str, c: pd.Timestamp, regime: str) -> None:
    """Corrupt everything a model in `regime` may not see: load after the cutoff, ERA5 after
    the cutoff (after the horizon for oracle_era5), every value of the other sources, and
    every value of the regime's source except the lead-matched horizon values."""
    hz = horizon_index(c)
    data.y[zone].loc[c + H :] = -9999.0
    if regime == "oracle_era5":
        data.era5[zone].loc[hz[-1] + H :] = 99.0
    else:
        data.era5[zone].loc[c + H :] = 99.0
    for r, tab in source_tables(data, zone).items():
        if r != regime:
            tab.loc[:] = 99.0
            continue
        for k in range(1, 8):
            other = hz.delete(slice(24 * (k - 1), 24 * k))
            tab.loc[tab.index.intersection(other), k] = 99.0
        tab.loc[tab.index.difference(hz)] = 99.0


def _saved(data: DataV2, zone: str):
    return (
        data.y[zone].copy(),
        data.era5[zone].copy(),
        data.forecast[zone].copy(),
        {r: data.forecast_v12[r][zone].copy() for r in ("forecast_ifs", "forecast_aifs")},
    )


def _restore(data: DataV2, zone: str, saved) -> None:
    y0, e0, f0, v0 = saved
    data.y[zone], data.era5[zone], data.forecast[zone] = y0, e0, f0
    for r, t in v0.items():
        data.forecast_v12[r][zone] = t


@needs_v2_data
@pytest.mark.parametrize("regime", V2_REGIMES)
@pytest.mark.parametrize("zone", V2_ZONES)
def test_v2_core_rows_ignore_everything_after_the_cutoff(data, zone, regime):
    c = GATE[1]
    rows = [m for m in v2.CORE_ROWS if zone in v2.ROWS[m]["zones"]]
    before = {
        m: V2_MODELS[m](data.history(zone, c), data.temperature(zone, c, regime), c) for m in rows
    }
    frame = v2.model_input_frame(data, zone, regime, c)
    saved = _saved(data, zone)
    try:
        _corrupt(data, zone, c, regime)
        for m in rows:
            after = V2_MODELS[m](data.history(zone, c), data.temperature(zone, c, regime), c)
            pd.testing.assert_series_equal(before[m], after)
        # The exported model inputs (Chronos-2 reads only these) do not change either.
        pd.testing.assert_frame_equal(frame, v2.model_input_frame(data, zone, regime, c))
    finally:
        _restore(data, zone, saved)


@needs_v2_data
def test_incomplete_horizon_temperature_is_not_forecast(data):
    for zone in ("AEP", "DOM"):
        c = GATE[0]
        temp = data.temperature(zone, c, "forecast_aifs").copy()
        temp.loc[c + 30 * H] = np.nan
        hist = data.history(zone, c)
        out = vanilla_benchmark_trend_holiday(hist, temp, c)
        assert len(out) == 168 and out.isna().all()
        assert V2_MODELS["lightgbm_competition"](hist, temp, c).isna().all()
        for m in ("vanilla_benchmark_trend", "lag_regression_temperature"):
            assert V2_MODELS[m](hist, temp, c).isna().any()  # incomplete, so dropped


@needs_v2_data
def test_holiday_row_is_complete_and_differs_from_vanilla_trend(data):
    """Sanity: the holiday terms change the fit (Columbus Day week, 2025-10-13)."""
    zone, c = "AEP", GATE[2]
    hist, temp = data.history(zone, c), data.temperature(zone, c, "oracle_era5")
    a = V2_MODELS["vanilla_benchmark_trend"](hist, temp, c)
    b = vanilla_benchmark_trend_holiday(hist, temp, c)
    assert b.notna().all() and not np.allclose(a, b)
    assert calendar(horizon_index(c))["hol"].sum() == 24  # one whole local day


# ------------------------------------------------------------------ export


INPUTS = ROOT / "data" / "model_inputs" / "gate_v2.parquet"


@pytest.mark.skipif(not INPUTS.exists(), reason="run harness.v2 export gate first")
def test_exported_calendar_is_the_harness_calendar(data):
    df = pd.read_parquet(INPUTS)
    assert set(df["unique_id"]) == set(V2_ZONES) and set(df["regime"]) == set(V2_REGIMES)
    cal = calendar(pd.DatetimeIndex(df["ds"]))
    for col in v2.CALENDAR_COLUMNS:
        assert np.array_equal(df[col].to_numpy(), cal[col].to_numpy())
    assert df.loc[df["is_horizon"], "y"].isna().all()
    assert (df.loc[df["is_horizon"], "ds"] > df.loc[df["is_horizon"], "cutoff"]).all()
    for (zone, regime, c), g in df.groupby(["unique_id", "regime", "cutoff"]):
        assert len(g) == v2.CONTEXT_HOURS + 168 and g["is_horizon"].sum() == 168
        if regime == "forecast_aifs" and c == GATE[2]:
            temp = data.temperature(zone, c, regime).reindex(pd.DatetimeIndex(g["ds"]))
            assert np.allclose(g["T"].to_numpy(), temp.to_numpy(), equal_nan=True)


# ------------------------------------------------------------------ guards


@pytest.mark.parametrize(
    "cmd",
    [
        ["-m", "harness.v2", "run", "scored"],
        ["-m", "harness.v2", "export", "scored"],
        ["-m", "harness.v2", "score", "scored"],
        ["-m", "harness.export_inputs", "scored", "--v2"],
    ],
)
def test_scored_set_is_refused_without_the_tag(cmd):
    if subprocess.run(
        ["git", "tag", "--list", "protocol-v2"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip():
        pytest.skip("tag protocol-v2 exists")
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0
    assert "must not be run yet" in r.stderr
    assert not (ROOT / "results" / "v2").exists()
