"""Load and clean data-logger records (temperature, RH over time) and compute VPD.

Rows that cannot be used are dropped and counted in the returned report, never
silently discarded or clamped.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import vpd

TEMP_SUSPECT_RANGE = (-10.0, 60.0)


def guess_columns(columns) -> dict:
    """Best-guess column names for time, temperature, RH (None if not found)."""
    def find(*needles, exclude=()):
        for c in columns:
            name = str(c).lower()
            if any(n in name for n in needles) and not any(x in name for x in exclude):
                return c
        return None
    return {
        "time": find("time", "date", "stamp"),
        "temp": find("temp", "°c", "tair", exclude=("leaf",)),
        "rh": find("rh", "humid", "%rh"),
        "leaf": find("leaf"),
    }


def load_logger_data(df: pd.DataFrame, time_col, temp_col, rh_col, rh_unit: str = "%",
                     leaf_col=None, offset: float = 0.0):
    """Return (clean_df, report).

    time_col: column name, or None to use the row number.
    rh_unit : '%' or 'fraction' (0-1, multiplied by 100).
    leaf_col: column with measured leaf temperature, or None to use `offset`.
    """
    n_in = len(df)
    out = pd.DataFrame(index=df.index)
    time_dropped = 0
    if time_col is None:
        out["time"] = np.arange(n_in, dtype=float)
    elif pd.api.types.is_numeric_dtype(df[time_col]):
        out["time"] = df[time_col].astype(float)
    else:
        out["time"] = pd.to_datetime(df[time_col], errors="coerce")
    out["temperature_C"] = pd.to_numeric(df[temp_col], errors="coerce")
    rh = pd.to_numeric(df[rh_col], errors="coerce")
    out["RH_percent"] = rh * 100.0 if rh_unit == "fraction" else rh
    if leaf_col is not None:
        out["leaf_temperature_C"] = pd.to_numeric(df[leaf_col], errors="coerce")
    else:
        out["leaf_temperature_C"] = out["temperature_C"] + offset

    cols = ["time", "temperature_C", "RH_percent", "leaf_temperature_C"]
    bad_time = int(out["time"].isna().sum())
    missing = int(out[cols[1:]].isna().any(axis=1).sum())
    valid = out.dropna()
    rh_bad = (valid["RH_percent"] < 0) | (valid["RH_percent"] > 100)
    n_rh_bad = int(rh_bad.sum())
    valid = valid[~rh_bad].copy()
    suspect = int(((valid["temperature_C"] < TEMP_SUSPECT_RANGE[0]) |
                   (valid["temperature_C"] > TEMP_SUSPECT_RANGE[1])).sum())

    valid = valid.sort_values("time").reset_index(drop=True)
    es_a = vpd.saturation_vapour_pressure(valid["temperature_C"].to_numpy())
    ea = es_a * valid["RH_percent"].to_numpy() / 100.0
    valid["es_kPa"] = es_a
    valid["ea_kPa"] = ea
    valid["VPD_air_kPa"] = es_a - ea
    valid["VPD_leaf_kPa"] = vpd.saturation_vapour_pressure(valid["leaf_temperature_C"].to_numpy()) - ea

    report = {
        "rows_in": n_in,
        "rows_used": len(valid),
        "dropped_bad_time": bad_time,
        "dropped_missing_values": missing,
        "dropped_rh_out_of_range": n_rh_bad,
        "temperature_outside_-10_60_kept": suspect,
        "negative_leaf_vpd_rows": int((valid["VPD_leaf_kPa"] < 0).sum()),
    }
    return valid, report


def summarise(clean: pd.DataFrame, low: float, high: float, kind: str = vpd.AIR) -> dict:
    """Summary statistics and share of records inside / below / above [low, high]."""
    col = "VPD_air_kPa" if kind == vpd.AIR else "VPD_leaf_kPa"
    v = clean[col]
    n = len(v)
    if n == 0:
        return {"n": 0}
    return {
        "n": n, "mean": float(v.mean()), "min": float(v.min()), "max": float(v.max()),
        "pct_inside": float(100 * ((v >= low) & (v <= high)).mean()),
        "pct_below": float(100 * (v < low).mean()),
        "pct_above": float(100 * (v > high).mean()),
    }


def example_data(seed: int = 7316) -> pd.DataFrame:
    """Synthetic 48 h logger record (5-min steps, 22/17 degC day/night). Not real measurements."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-01-01 00:00", periods=48 * 12, freq="5min")
    hour = t.hour + t.minute / 60
    day = ((hour >= 6) & (hour < 18)).astype(float)
    temp = 17 + 5 * day + rng.normal(0, 0.2, len(t))
    rh = np.clip(75 - 12 * day + rng.normal(0, 1.5, len(t)), 0, 100)
    return pd.DataFrame({"timestamp": t, "air_temp_C": temp.round(2), "RH_percent": rh.round(1)})
