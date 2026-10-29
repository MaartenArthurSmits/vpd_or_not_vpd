import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import share  # noqa: E402

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
