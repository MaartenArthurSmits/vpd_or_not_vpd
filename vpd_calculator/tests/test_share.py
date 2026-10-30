import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plots  # noqa: E402
import presets  # noqa: E402
import share  # noqa: E402

pytestmark = pytest.mark.unit


# ---- share ---------------------------------------------------------------
STATE = {"mode": share.MODE_B, "t_air": 25.5, "rh": 55.0, "target_vpd": 1.25,
         "vpd_lo": 0.8, "vpd_hi": 1.2,
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


# ---- acceptable range (day/night limits and one preset) --------------------------------------
DN_STATE = STATE | {
    "dn_lo_day": 1.0, "dn_hi_day": 1.0,
    "dn_lo_night": 0.6, "dn_hi_night": 1.0, "range_preset": presets.CUSTOM,
}


def test_range_round_trip_including_equal_limits_and_identity():
    params = share.build_params(DN_STATE)
    assert {k: params[k] for k in ("dlo", "dhi", "nlo", "nhi", "rp")} == {
        "dlo": "1", "dhi": "1", "nlo": "0.6", "nhi": "1", "rp": "custom"}
    assert not {"dt", "doff", "nt", "noff", "dp", "np", "dk", "nk"} & set(params)        # limits are canopy targets
    parsed = share.parse_params(params)
    for k, v in DN_STATE.items():
        if k != "calc_leaf_meas":
            assert parsed[k] == v, k


def test_every_preset_has_a_share_id_and_round_trips():
    for name in presets.PRESET_NAMES:
        assert share.parse_params(share.build_params(DN_STATE | {"range_preset": name}))["range_preset"] == name


def test_legacy_and_partial_links_leave_the_range_untouched_and_old_condition_parameters_are_ignored():
    legacy = share.parse_params({"m": "b", "t": "25", "rh": "60", "tv": "1.1", "lo": "1.2", "hi": "1.5"})
    assert not any(k.startswith("dn_") for k in legacy)
    assert share.parse_params({"dt": "30", "doff": "-2", "nt": "10", "noff": "1", "dp": "veg", "np": "seed",
                               "dk": "air", "nk": "leaf"}) == {}


def test_build_params_omits_range_when_state_has_none():
    assert not {"dlo", "dhi", "nlo", "nhi", "rp"} & set(share.build_params(STATE))


@pytest.mark.parametrize("bad", [
    {"dlo": "-0.1"}, {"dhi": "10.1"}, {"nlo": "1e999"}, {"nhi": "nan"}, {"dlo": "abc"}, {"dhi": ""},
    {"rp": "unknown"}, {"rp": "Vegetative"}, {"rp": "1"},
])
def test_invalid_range_parameters_are_ignored(bad):
    assert share.parse_params(bad) == {}


def test_range_bounds_are_inclusive_and_not_clamped():
    assert share.parse_params({"dlo": "0", "nhi": "10"}) == {"dn_lo_day": 0.0, "dn_hi_night": 10.0}


def test_resolve_preset_keeps_identity_when_it_still_fits_and_never_changes_limits():
    first, second = presets.PRESET_NAMES[0], presets.PRESET_NAMES[1]
    (lo, hi) = presets.preset_range(first)
    assert presets.resolve_preset(first, (lo, hi), (lo, hi)) == first
    assert presets.resolve_preset(presets.CUSTOM, (lo, hi), (lo, hi)) == presets.CUSTOM
    assert presets.resolve_preset(second, (lo, hi), (lo, hi)) == first            # inconsistent identity
    assert presets.resolve_preset(first, (lo, hi), (lo, hi + 0.1)) == presets.CUSTOM
    assert presets.resolve_preset(None, (0.7, 1.3), (0.7, 1.3)) == presets.DEFAULT_PRESET


# ---- heatmap settings ----------------------------------------------------------------------
HM_STATE = DN_STATE | {
    "hm_tmin": 12.5, "hm_tmax": 38.0, "hm_rhmin": 25.0, "hm_rhmax": 95.0,
    "hm_cs": "Viridis", "hm_zmax": 3.5, "hm_step": 0.2, "hm_target": False, "hm_point": False,
}
HM_KEYS = ("htmin", "htmax", "hrmin", "hrmax", "hz", "hcs", "hst", "hg", "hp")


def test_heatmap_round_trip_alongside_calculator_and_day_night():
    params = share.build_params(HM_STATE)
    assert {k: params[k] for k in HM_KEYS} == {
        "htmin": "12.5", "htmax": "38", "hrmin": "25", "hrmax": "95", "hz": "3.5",
        "hcs": "Viridis", "hst": "0.2", "hg": "0", "hp": "0"}
    parsed = share.parse_params(params)
    for k, v in HM_STATE.items():
        if k != "calc_leaf_meas":
            assert parsed[k] == v, k


def test_heatmap_colorscales_match_the_app_options():
    assert share._COLORSCALES == plots.COLORSCALES
    for name in plots.COLORSCALES:
        assert share.parse_params({"hcs": name}) == {"hm_cs": name}


@pytest.mark.parametrize("step", [0.1, 0.2, 0.5, 1.0])
@pytest.mark.parametrize("flag", [True, False])
def test_heatmap_step_and_toggle_round_trip(step, flag):
    parsed = share.parse_params(share.build_params(HM_STATE | {"hm_step": step, "hm_target": flag, "hm_point": not flag}))
    assert parsed["hm_step"] == step and parsed["hm_target"] is flag and parsed["hm_point"] is (not flag)


def test_older_links_do_not_touch_heatmap_settings():
    assert share.parse_params({"t": "25", "dt": "30"}).keys() == {"t_air"}


def test_build_params_before_heatmap_widgets_exist_uses_control_defaults():
    """On a fresh session the URL is built before the heatmap widgets are created (and partial links set only some)."""
    params = share.build_params(DN_STATE)
    assert {k: params[k] for k in HM_KEYS} == {
        "htmin": "10", "htmax": "40", "hrmin": "10", "hrmax": "100", "hz": "0",
        "hcs": "Blue–green–red", "hst": "0.5", "hg": "1", "hp": "1"}
    partial = share.build_params(DN_STATE | {"hm_tmin": 15.0})        # only one heatmap key present: no KeyError
    assert partial["htmin"] == "15" and partial["htmax"] == "40"
    parsed = share.parse_params(params)
    for key, default in share.HEATMAP_DEFAULTS.items():
        assert parsed[key] == default



@pytest.mark.parametrize("bad", [
    {"htmin": "abc"}, {"htmin": "nan"}, {"htmax": "inf"}, {"htmin": "-10.1"}, {"htmax": "60.1"},
    {"hrmin": "-1"}, {"hrmin": "99.5"}, {"hrmax": "0.5"}, {"hrmax": "101"}, {"hz": "-1"}, {"hz": "21"},
    {"hz": "1e999"}, {"hcs": "rainbow"}, {"hcs": "viridis"}, {"hcs": ""},
    {"hst": "0.3"}, {"hst": "nan"}, {"hst": "x"}, {"hst": ""}, {"hg": "true"}, {"hg": "2"}, {"hp": ""},
])
def test_invalid_heatmap_parameters_are_ignored(bad):
    assert share.parse_params(bad) == {}


def test_heatmap_bounds_are_inclusive_and_not_clamped():
    ok = share.parse_params({"htmin": "-10", "htmax": "60", "hrmin": "0", "hrmax": "100", "hz": "0"})
    assert ok == {"hm_tmin": -10.0, "hm_tmax": 60.0, "hm_rhmin": 0.0, "hm_rhmax": 100.0, "hm_zmax": 0.0}


def test_old_air_heatmap_parameter_is_ignored_and_not_written():
    assert share.parse_params({"hk": "air", "t": "25"}) == {"t_air": 25.0}
    assert "hk" not in share.build_params(HM_STATE)
    assert share.parse_params({"hcs": "Blue–green–red"}) == {"hm_cs": "Blue–green–red"} and share.HEATMAP_DEFAULTS["hm_cs"] == "Blue–green–red"
