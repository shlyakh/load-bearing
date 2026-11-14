"""Collect what the dashboard page shows into dashboard/data.js.

    uv run --project core python dashboard/build_data.py

Reads results/ and data/processed/ only; computes nothing new except display rounding.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.data import Data, load_protocol  # noqa: E402

LABELS = {
    "seasonal_naive": ("Same hour last week", "simple", ""),
    "lag_regression": ("Regression, no weather", "simple", ""),
    "lag_regression_temperature": ("Regression + temperature", "baseline", "the baseline"),
    "lightgbm_temperature": ("LightGBM + temperature", "simple", ""),
    "vanilla_benchmark": ("Vanilla benchmark", "simple", ""),
    "vanilla_benchmark_trend": ("Vanilla benchmark with trend", "standard", "field standard"),
    "chronos2": ("Chronos-2, no weather", "fm", ""),
    "chronos2_temperature": ("Chronos-2 + temperature", "primary", "primary comparison"),
    "chronos2_temperature_gap48": ("Chronos-2 + temperature, 2-day data delay", "fm", ""),
    "timesfm25": ("TimesFM 2.5, no weather", "fm", "univariate"),
    "timesfm25_temperature": ("TimesFM 2.5 + temperature", "fm", ""),
    "timestral_temperature": ("Timestral + temperature", "flagged", "not out-of-sample"),
    "timesfm3_temperature": (
        "TimesFM 3.0 + temperature",
        "flagged",
        "not out-of-sample; non-commercial weights",
    ),
}


# You.com list prices used for the estimate on the providers tab (notes/hackathon_tools.md).
YOUCOM_PRICE = {"search": 0.005, "page": 0.001, "research_task": 0.05}
SEARCH_TOOLS = {"WebSearch", "mcp__you-com__you-search"}
FETCH_TOOLS = {"WebFetch", "mcp__you-com__you-contents"}


def stream_counts(run_id: str) -> dict | None:
    """Pages fetched and research tasks started in one run, from its saved stream
    (git-ignored, so present only on the machine that ran it). A research task is one
    start call; the later calls with a task id are polls of the same task."""
    path = ROOT / "runs" / f"{run_id}.jsonl"
    if not path.exists():
        return None
    pages = tasks = 0
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use":
                continue
            name, args = block["name"], block.get("input") or {}
            if name == "mcp__you-com__you-contents":
                pages += len(args.get("urls") or [])
            elif name == "WebFetch":
                pages += 1
            elif name == "mcp__you-com__you-research" and "task_id" not in args:
                tasks += 1
    return {"pages": pages, "research_tasks": tasks}


def calls(meta: dict, names: set[str]) -> int:
    return sum(v for k, v in (meta.get("tool_calls") or {}).items() if k in names)


def provider_usage() -> dict:
    """What each search provider did, from the run records: the latest finished scan and
    every finished judge run. Model cost is the client's estimate; You.com charges are an
    estimate at list prices from the counted calls, not read from the account."""
    metas = []
    for path in sorted((ROOT / "runs").glob("*.meta.json")):
        m = json.loads(path.read_text())
        if m.get("exit_code") == 0 and m.get("skill") in ("scan", "judge", "run-candidate"):
            metas.append(m)
    merged = sorted((ROOT / "candidates" / "merged").glob("scan_*.jsonl"))
    rows = [json.loads(x) for x in merged[-1].read_text().splitlines()] if merged else []
    out = {"merged_total": len(rows), "both": sum(len(r["found_by"]) > 1 for r in rows)}
    for prov in ("claude", "youcom"):
        scans = [m for m in metas if m["skill"] == "scan" and m["provider"] == prov]
        files = sorted((ROOT / "candidates" / prov).glob("scan_*.jsonl"))
        scan = None
        if scans and files:
            m = scans[-1]
            stem = files[-1].stem.replace("scan_", "scan-").replace("_run", "-run")
            ledger = ROOT / "evidence" / prov / f"{stem}.jsonl"
            counted = stream_counts(m["run_id"]) or {}
            scan = {
                "searches": calls(m, SEARCH_TOOLS),
                "fetch_calls": calls(m, FETCH_TOOLS),
                "pages": counted.get("pages"),
                "pages_logged": len(ledger.read_text().splitlines()) if ledger.exists() else None,
                "kept": len(files[-1].read_text().splitlines()),
                "only": sum(r["found_by"] == [prov] for r in rows),
                "minutes": round(m["wall_seconds"] / 60, 1),
                "model_cost": round(m["total_cost_usd"], 2),
            }
        latest = {}
        for m in metas:
            if m["skill"] == "judge" and m["provider"] == prov and m.get("args"):
                latest[m["args"][0]] = m
        judges = [
            m for cid, m in latest.items() if (ROOT / "scorecards" / prov / f"{cid}.json").exists()
        ]
        counted = [stream_counts(m["run_id"]) for m in judges]
        have = [c for c in counted if c]
        cards = [json.loads(p.read_text()) for p in (ROOT / "scorecards" / prov).glob("*.json")]
        verdicts: dict[str, int] = {}
        for c in cards:
            v = (c.get("receipt") or {}).get("verdict")
            if v:
                verdicts[v] = verdicts.get(v, 0) + 1
        n = len(judges)
        judge = {
            "claims": len(cards),
            "runs_with_record": n,
            "searches": calls({"tool_calls": _sum_calls(judges)}, SEARCH_TOOLS),
            "pages": sum(c["pages"] for c in have) if len(have) == n and n else None,
            "research_tasks": sum(c["research_tasks"] for c in have)
            if len(have) == n and n
            else None,
            "minutes_each": round(sum(m["wall_seconds"] for m in judges) / n / 60, 1)
            if n
            else None,
            "model_cost_each": round(sum(m["total_cost_usd"] for m in judges) / n, 2)
            if n
            else None,
            "model_cost": round(sum(m["total_cost_usd"] for m in judges), 2),
            "receipts": verdicts,
        }
        out[prov] = {"scan": scan, "judge": judge}
    y = out["youcom"]
    if y["scan"] and y["judge"]["pages"] is not None:
        searches = y["scan"]["searches"] + y["judge"]["searches"]
        pages = (y["scan"]["pages"] or 0) + y["judge"]["pages"]
        tasks = y["judge"]["research_tasks"]
        out["youcom_charges"] = {
            "searches": searches,
            "pages": pages,
            "research_tasks": tasks,
            "usd": round(
                searches * YOUCOM_PRICE["search"]
                + pages * YOUCOM_PRICE["page"]
                + tasks * YOUCOM_PRICE["research_task"],
                2,
            ),
        }
    return out


def _sum_calls(metas: list[dict]) -> dict:
    total: dict[str, int] = {}
    for m in metas:
        for k, v in (m.get("tool_calls") or {}).items():
            total[k] = total.get(k, 0) + v
    return total


def main() -> None:
    proto = load_protocol()
    res = ROOT / "results"
    lb = pd.read_parquet(res / "leaderboard.parquet")
    st = pd.read_parquet(res / "stats.parquet")
    win = pd.read_parquet(res / "windows.parquet")
    base = proto["baseline_model"]

    vs = st[(st["kind"] == "vs_baseline") & (st["metric"] == "mae")].set_index(
        ["model_a", "unique_id", "regime"]
    )
    board = []
    for r in lb.itertuples():
        label, group, note = LABELS[r.model]
        key = (r.model, r.unique_id, r.regime)
        board.append(
            {
                "model": r.model,
                "label": label,
                "group": group,
                "note": note,
                "zone": r.unique_id,
                "regime": r.regime,
                "mae": round(r.mae, 1),
                "mape": round(r.mape, 2),
                "ratio": round(r.ratio_vs_baseline, 3),
                "lo": round(vs.loc[key, "ci90_low"], 3) if key in vs.index else None,
                "hi": round(vs.loc[key, "ci90_high"], 3) if key in vs.index else None,
                "n": int(r.n_windows),
                "n_after": None
                if pd.isna(r.n_windows_after_weights)
                else int(r.n_windows_after_weights),
                "weights_date": None if pd.isna(r.weights_date) else str(r.weights_date)[:10],
                "protocol": r.protocol_version,
            }
        )

    days = st[
        (st["kind"] == "vs_baseline")
        & (st["model_a"] == "chronos2_temperature")
        & (st["regime"] == "forecast")
        & (st["metric"] != "mae")
    ]
    per_day = {
        z: [
            {
                "day": int(r.metric[-1]),
                "ratio": round(r.ratio, 3),
                "lo": round(r.ci90_low, 3),
                "hi": round(r.ci90_high, 3),
            }
            for r in g.sort_values("metric").itertuples()
        ]
        for z, g in days.groupby("unique_id")
    }

    data = Data()
    fc = {
        m: pd.read_parquet(res / "forecasts" / f"{m}.parquet")
        for m in (base, "chronos2_temperature")
    }
    kept = sorted(win["cutoff"].unique())
    weeks = []
    for cutoff in kept[::4]:
        entry = {"start": str(pd.Timestamp(cutoff).tz_convert(proto["timezone"]).date())}
        for zone in proto["zones"]:
            entry[zone] = {"actual": [round(v) for v in data.actuals(zone, cutoff)]}
            for m, df in fc.items():
                g = df[
                    (df["unique_id"] == zone)
                    & (df["cutoff"] == cutoff)
                    & (df["regime"] == "forecast")
                ].sort_values("ds")
                entry[zone][m] = [round(v) for v in g["y_hat"]]
        weeks.append(entry)

    zones = {}
    last = pd.Timestamp(max(kept)) + pd.Timedelta(hours=168)
    for zone in proto["zones"]:
        y = data.y[zone].loc[last - pd.Timedelta(days=365) : last]
        zones[zone] = {
            "mean_mw": round(float(y.mean())),
            "peak_mw": round(float(y.max())),
            "stations": proto["weather"]["stations"][zone],
        }

    # Zones chosen for protocol-v2 (decision 33): display only, nothing has been run on them.
    draft = yaml.safe_load((ROOT / "protocol-v2-draft.yaml").read_text())
    zstats = pd.read_csv(ROOT / "results" / "zone_selection" / "zone_stats.csv", index_col=0)
    next_zones = {
        z: {
            "name": v["name"],
            "matches": v["matches"],
            "mean_mw": round(float(zstats.loc[z, "mean_y2"])),  # Nov 2024 to Oct 2025
            "peak_mw": round(
                float(max(zstats.loc[z, "peak_summer"], zstats.loc[z, "peak_winter"]))
            ),
            "summer_winter_peak": round(float(zstats.loc[z, "sw_peak_ratio"]), 2),
            "stations": v["weather_points"],
        }
        for z, v in draft["zones"]["selected"].items()
    }

    # What the scan found: the latest candidates file per provider, and every hit with
    # the reason it was kept or dropped (paraphrased notes only).
    scan = {}
    for prov_dir in sorted((ROOT / "candidates").iterdir()):
        files = sorted(prov_dir.glob("scan_*.jsonl"))
        if not files:
            continue
        latest = files[-1]
        stem = latest.stem.replace("scan_", "scan-").replace("_run", "-run")
        ledger = ROOT / "evidence" / prov_dir.name / f"{stem}.jsonl"
        hits = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        scan[prov_dir.name] = {
            "file": str(latest.relative_to(ROOT)),
            "candidates": [json.loads(x) for x in latest.read_text().splitlines()],
            "hits": [
                {
                    "url": h["url"],
                    "title": h["title"],
                    "published_at": h["published_at"],
                    "status": h["note"].split(".")[0].split(":")[0].split(" ")[0].upper(),
                    "note": h["note"],
                }
                for h in hits
            ],
        }
    feeds_files = sorted((ROOT / "candidates" / "feeds").glob("feeds_*.jsonl"))
    feed_counts = {}
    if feeds_files:
        for x in feeds_files[-1].read_text().splitlines():
            src = json.loads(x)["source"]
            feed_counts[src] = feed_counts.get(src, 0) + 1
    spec = yaml.safe_load((ROOT / "spec.yaml").read_text())
    # The judge under two search providers on the same claims
    # (tools/compare_providers.py writes the file; absent until both have run).
    pc_file = ROOT / "results" / "provider_comparison.csv"
    provider_comparison = (
        json.loads(pd.read_csv(pc_file).to_json(orient="records")) if pc_file.exists() else []
    )

    out = {
        "scan": scan,
        "provider_comparison": provider_comparison,
        "provider_usage": provider_usage(),
        "feed_counts": feed_counts,
        "scan_window_days": spec["scan"]["window_days"],
        "built_from_commit": lb["git_commit"].dropna().unique().tolist(),
        "protocol": sorted(lb["protocol_version"].dropna().unique().tolist()),
        "bar": proto["primary_comparison"]["bar"],
        "n_windows": int(lb["n_windows"].max()),
        "first_week": str(pd.Timestamp(min(kept)).tz_convert(proto["timezone"]).date()),
        "last_week": str(pd.Timestamp(max(kept)).tz_convert(proto["timezone"]).date()),
        "board": board,
        "per_day": per_day,
        "weeks": weeks,
        "zones": zones,
        "next_zones": next_zones,
        "primary_text": (res / "primary.md").read_text(),
        # Chronos-2 with temperature against the field's standard benchmark (protocol-v1.1)
        "vs_standard": {
            r.unique_id: {
                "ratio": round(r.ratio, 3),
                "lo": round(r.ci90_low, 3),
                "hi": round(r.ci90_high, 3),
            }
            for r in st[
                (st["kind"] == "vs_vanilla_trend")
                & (st["model_a"] == "chronos2_temperature")
                & (st["regime"] == "forecast")
                & (st["metric"] == "mae")
            ].itertuples()
        },
        # GB study, weather_study/RESULTS.md in Zenodo record 24161799 (notes/moran.md)
        "claim": {
            "ratio": 0.966,
            "lo": 0.931,
            "hi": 1.001,
            "level": 0.90,
            "n_days": 960,
            "horizon": "day-ahead",
            "url": "https://zenodo.org/records/24161799",
        },
    }
    out["weather_v12"] = weather_v12(res / "weather_v12")
    out["protocol"] = sorted(set(out["protocol"]) | set(out["weather_v12"]["protocol"]))
    out["v2"] = protocol_v2(res / "v2")
    out["protocol"] = sorted(set(out["protocol"]) | {"protocol-v2"})
    v21_stats = res / "v21" / "stats.csv"
    if v21_stats.exists():  # protocol-v2.1: Chronos-2 calendar encodings (secondary)
        st = pd.read_csv(v21_stats)
        st = st[(st["metric"] == "mae") & (st["kind"] == "encoding_vs_temperature_only")]
        out["v21"] = {
            "n_ratios": len(st),
            "n_above_1": int((st["ratio"] > 1).sum()),
            "n_range_above_1": int((st["ci90_low"] > 1).sum()),
            "min": round(float(st["ratio"].min()), 2),
            "max": round(float(st["ratio"].max()), 2),
            "aifs": [
                {
                    "zone": r.unique_id,
                    "encoding": r.model_a.replace("chronos2_temperature_calendar_", ""),
                    "ratio": round(r.ratio, 3),
                    "lo": round(r.ci90_low, 3),
                    "hi": round(r.ci90_high, 3),
                }
                for r in st[st["regime"] == "forecast_aifs"].itertuples()
            ],
        }
        out["protocol"] = sorted(set(out["protocol"]) | {"protocol-v2.1"})
    (ROOT / "dashboard" / "data.js").write_text("window.DATA = " + json.dumps(out) + ";\n")
    print("data.js:", len(board), "leaderboard rows,", len(weeks), "sample weeks")


def weather_v12(d: Path) -> dict:
    """protocol-v1.2 (secondary): three models under four weather sources, ERA5 truth."""
    lb = pd.read_csv(d / "leaderboard.csv")
    st = pd.read_csv(d / "stats.csv")
    te = pd.read_csv(d / "temperature_error_by_lead.csv")
    rows = [
        {
            "model": r.model,
            "zone": r.unique_id,
            "regime": r.regime,
            "n": int(r.n_windows),
            "mae": round(r.mae, 1),
            "protocol": r.protocol_version,
        }
        for r in lb.itertuples()
    ]
    pairs = [
        {
            "kind": r.kind,
            "zone": r.unique_id,
            "regime": r.regime,
            "n": int(r.n_windows),
            "ratio": round(r.ratio, 3),
            "lo": round(r.ci90_low, 3),
            "hi": round(r.ci90_high, 3),
            "reading": r.reading_10pct_bar,
        }
        for r in st[
            st["kind"].isin(
                [
                    "chronos2_vs_vanilla_benchmark_trend",
                    "chronos2_vs_lag_regression_temperature",
                ]
            )
            & (st["metric"] == "mae")
        ].itertuples()
    ]
    temp = [
        {
            "zone": r.unique_id,
            "source": r.source.split(" ")[0] if r.source.startswith("forecast_") else "v1_oracle",
            "day": int(r.day),
            "n": int(r.n),
            "rmse": round(r.rmse, 2),
        }
        for r in te.itertuples()
    ]
    return {
        "protocol": sorted(lb["protocol_version"].dropna().unique().tolist()),
        "rows": rows,
        "pairs": pairs,
        "temp_rmse": temp,
    }


def protocol_v2(d: Path) -> dict:
    """protocol-v2: the primary pair on the new zones AEP and AE, DOM and JC as development
    zones, and the calendar rows. Mean absolute error only."""
    lb = pd.read_csv(d / "leaderboard.csv")
    st = pd.read_csv(d / "stats.csv")
    st = st[(st["metric"] == "mae") & (st["kind"] != "forecast_vs_oracle_era5")]
    return {
        "rows": [
            {
                "model": r.model,
                "zone": r.unique_id,
                "regime": r.regime,
                "n": int(r.n_windows),
                "mae": round(r.mae, 1),
            }
            for r in lb.itertuples()
        ],
        "pairs": [
            {
                "kind": r.kind,
                "zone": r.unique_id,
                "regime": r.regime,
                "a": r.model_a,
                "b": r.model_b,
                "n": int(r.n_windows),
                "ratio": round(r.ratio, 3),
                "lo": round(r.ci90_low, 3),
                "hi": round(r.ci90_high, 3),
                "reading": r.reading_10pct_bar,
            }
            for r in st.itertuples()
        ],
        "primary_text": (d / "primary.md").read_text(),
    }


if __name__ == "__main__":
    main()
