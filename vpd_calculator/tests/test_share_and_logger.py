import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logger_data  # noqa: E402
import share  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit


# ---- share ---------------------------------------------------------------
STATE = {"mode": share.MODE_B, "t_air": 25.5, "rh": 55.0, "target_vpd": 1.25,
         "target_kind": share.LEAF_LABEL, "vpd_lo": 0.8, "vpd_hi": 1.2,
         "interval_kind": share.AIR_LABEL, "calc_leaf_method": share.OFFSET_METHOD,
         "calc_offset": -1.5, "calc_leaf_meas": 24.0}


def test_share_round_trip():
    parsed = share.parse_params(share.build_params(STATE))
    for k, v in STATE.items():
        if k == "calc_leaf_meas":  # not encoded when offset method is used
            continue
        assert parsed[k] == v


def test_share_round_trip_measured_leaf():
    s = STATE | {"calc_leaf_method": share.MEASURED_METHOD}
    parsed = share.parse_params(share.build_params(s))
    assert parsed["calc_leaf_method"] == share.MEASURED_METHOD
    assert parsed["calc_leaf_meas"] == 24.0
    assert "calc_offset" not in parsed


def test_share_ignores_invalid_values():
    parsed = share.parse_params({"t": "abc", "rh": "150", "tv": "nan", "m": "z", "k": "x", "off": "2"})
    assert parsed == {"calc_offset": 2.0, "calc_leaf_method": share.OFFSET_METHOD}


def test_share_url_contains_query():
    url = share.share_url(STATE, base="http://x/")
    assert url.startswith("http://x/?") and "t=25.5" in url


# ---- logger_data ---------------------------------------------------------
def test_example_data_is_deterministic():
    assert logger_data.example_data().equals(logger_data.example_data())


def test_load_matches_vpd_functions():
    df = pd.DataFrame({"time": ["2026-01-01 00:00", "2026-01-01 00:05"],
                       "T": [22.0, 22.0], "RH": [60.0, 100.0]})
    clean, rep = logger_data.load_logger_data(df, "time", "T", "RH", offset=-2)
    assert rep["rows_used"] == 2
    assert clean["VPD_air_kPa"].iloc[0] == pytest.approx(vpd.vpd_air(22, 60))
    assert clean["VPD_air_kPa"].iloc[1] == pytest.approx(0, abs=1e-12)
    assert clean["VPD_leaf_kPa"].iloc[0] == pytest.approx(vpd.vpd_leaf(22, 60, 20))
    assert rep["negative_leaf_vpd_rows"] == 1  # 100 % RH with cooler leaf


def test_bad_rows_are_dropped_and_counted():
    df = pd.DataFrame({"time": ["2026-01-01 00:00", "not a time", "2026-01-01 00:10", "2026-01-01 00:15"],
                       "T": [22, 22, "x", 22], "RH": [60, 60, 60, 140]})
    clean, rep = logger_data.load_logger_data(df, "time", "T", "RH")
    assert len(clean) == 1
    assert rep["dropped_bad_time"] == 1
    assert rep["dropped_missing_values"] == 1
    assert rep["dropped_rh_out_of_range"] == 1
    assert rep["rows_in"] == 4


def test_rh_fraction_and_measured_leaf_column():
    df = pd.DataFrame({"T": [22.0], "RH": [0.6], "leaf": [20.0]})
    clean, _ = logger_data.load_logger_data(df, None, "T", "RH", "fraction", leaf_col="leaf")
    assert clean["RH_percent"].iloc[0] == pytest.approx(60)
    assert clean["VPD_leaf_kPa"].iloc[0] == pytest.approx(vpd.vpd_leaf(22, 60, 20))


def test_summarise_percentages_add_up():
    clean, _ = logger_data.load_logger_data(
        logger_data.example_data(), "timestamp", "air_temp_C", "RH_percent")
    s = logger_data.summarise(clean, 0.5, 0.9)
    assert s["pct_inside"] + s["pct_below"] + s["pct_above"] == pytest.approx(100)
    assert s["n"] == len(clean) == 576


def test_guess_columns():
    g = logger_data.guess_columns(["Timestamp", "Air Temp (°C)", "RH (%)", "Leaf temp"])
    assert g == {"time": "Timestamp", "temp": "Air Temp (°C)", "rh": "RH (%)", "leaf": "Leaf temp"}
