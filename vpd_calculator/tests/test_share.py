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


# ---- day/night settings --------------------------------------------------------------------
DN_STATE = STATE | {
    "dn_t_day": 33.0, "dn_off_day": -2.0, "dn_lo_day": 1.0, "dn_hi_day": 1.0,
    "dn_kind_day": share.LEAF_LABEL, "dn_preset_day": "Vegetative",
    "dn_t_night": 17.0, "dn_off_night": 1.0, "dn_lo_night": 0.6, "dn_hi_night": 1.0,
    "dn_kind_night": share.AIR_LABEL, "dn_preset_night": presets.CUSTOM,
}


def test_day_night_round_trip_including_equal_limits_and_identity():
    params = share.build_params(DN_STATE)
    assert {k: params[k] for k in ("dt", "doff", "dlo", "dhi", "dk", "dp", "nt", "noff", "nlo", "nhi", "nk", "np")} == {
        "dt": "33", "doff": "-2", "dlo": "1", "dhi": "1", "dk": "leaf", "dp": "veg",
        "nt": "17", "noff": "1", "nlo": "0.6", "nhi": "1", "nk": "air", "np": "custom"}
    parsed = share.parse_params(params)
    for k, v in DN_STATE.items():
        if k != "calc_leaf_meas":
            assert parsed[k] == v, k


def test_every_preset_has_a_share_id_and_round_trips():
    for name in presets.PRESET_NAMES:
        for period in ("day", "night"):
            parsed = share.parse_params(share.build_params(DN_STATE | {f"dn_preset_{period}": name}))
            assert parsed[f"dn_preset_{period}"] == name


def test_legacy_and_partial_links_leave_day_night_untouched():
    legacy = share.parse_params({"m": "b", "t": "25", "rh": "60", "tv": "1.1", "lo": "1.2", "hi": "1.5"})
    assert not any(k.startswith("dn_") for k in legacy)
    partial = share.parse_params({"dt": "30", "nk": "leaf"})
    assert partial == {"dn_t_day": 30.0, "dn_kind_night": share.LEAF_LABEL}


def test_build_params_omits_day_night_when_state_has_none():
    day_night_keys = {"dt", "doff", "dlo", "dhi", "dk", "dp", "nt", "noff", "nlo", "nhi", "nk", "np"}
    assert not day_night_keys & set(share.build_params(STATE))


@pytest.mark.parametrize("bad", [
    {"dt": "abc"}, {"dt": "nan"}, {"dt": "inf"}, {"dt": "-inf"}, {"dt": "61"}, {"dt": "-10.1"}, {"dt": ""},
    {"doff": "10.5"}, {"noff": "-11"}, {"noff": "NaN"}, {"dlo": "-0.1"}, {"dhi": "10.1"}, {"nlo": "1e999"},
    {"dk": "water"}, {"nk": "AIR"}, {"dk": ""}, {"dp": "unknown"}, {"np": "Vegetative"}, {"dp": "1"},
])
def test_invalid_day_night_parameters_are_ignored(bad):
    assert share.parse_params(bad) == {}


def test_day_night_bounds_are_inclusive_and_not_clamped():
    ok = share.parse_params({"dt": "60", "nt": "-10", "doff": "10", "noff": "-10", "dlo": "0", "nhi": "10"})
    assert ok == {"dn_t_day": 60.0, "dn_t_night": -10.0, "dn_off_day": 10.0, "dn_off_night": -10.0,
                  "dn_lo_day": 0.0, "dn_hi_night": 10.0}


def test_resolve_stage_keeps_identity_for_identical_ranges_and_never_changes_limits():
    # Vegetative night and General horticulture night are both 0.8-1.2
    assert presets.resolve_stage("Vegetative", 0.8, 1.2, "night") == "Vegetative"
    assert presets.resolve_stage("General horticulture", 0.8, 1.2, "night") == "General horticulture"
    assert presets.resolve_stage(None, 0.8, 1.2, "night") == "General horticulture"      # derived
    assert presets.resolve_stage(presets.CUSTOM, 1.0, 1.0, "day") == presets.CUSTOM
    assert presets.resolve_stage("Flowering", 0.8, 1.2, "day") == "General horticulture"  # inconsistent id
    assert presets.resolve_stage("Flowering", 0.7, 1.1, "day") == presets.CUSTOM


# ---- heatmap settings ----------------------------------------------------------------------
HM_STATE = DN_STATE | {
    "hm_kind": share.LEAF_LABEL, "hm_tmin": 12.5, "hm_tmax": 38.0, "hm_rhmin": 25.0, "hm_rhmax": 95.0,
    "hm_cs": "Viridis", "hm_zmax": 3.5, "hm_step": 0.2, "hm_target": False, "hm_point": False,
}
HM_KEYS = ("htmin", "htmax", "hrmin", "hrmax", "hz", "hk", "hcs", "hst", "hg", "hp")


def test_heatmap_round_trip_alongside_calculator_and_day_night():
    params = share.build_params(HM_STATE)
    assert {k: params[k] for k in HM_KEYS} == {
        "htmin": "12.5", "htmax": "38", "hrmin": "25", "hrmax": "95", "hz": "3.5", "hk": "leaf",
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
    assert share.parse_params({"t": "25", "dt": "30"}).keys() == {"t_air", "dn_t_day"}


def test_build_params_before_heatmap_widgets_exist_uses_control_defaults():
    """On a fresh session the URL is built before the heatmap widgets are created (and partial links set only some)."""
    params = share.build_params(DN_STATE)
    assert {k: params[k] for k in HM_KEYS} == {
        "htmin": "10", "htmax": "40", "hrmin": "10", "hrmax": "100", "hz": "0", "hk": "air",
        "hcs": "RdYlBu_r", "hst": "0.5", "hg": "1", "hp": "1"}
    partial = share.build_params(DN_STATE | {"hm_tmin": 15.0})        # only one heatmap key present: no KeyError
    assert partial["htmin"] == "15" and partial["htmax"] == "40"
    parsed = share.parse_params(params)
    for key, default in share.HEATMAP_DEFAULTS.items():
        assert parsed[key] == default



@pytest.mark.parametrize("bad", [
    {"htmin": "abc"}, {"htmin": "nan"}, {"htmax": "inf"}, {"htmin": "-10.1"}, {"htmax": "60.1"},
    {"hrmin": "-1"}, {"hrmin": "99.5"}, {"hrmax": "0.5"}, {"hrmax": "101"}, {"hz": "-1"}, {"hz": "21"},
    {"hz": "1e999"}, {"hk": "water"}, {"hk": "AIR"}, {"hcs": "rainbow"}, {"hcs": "viridis"}, {"hcs": ""},
    {"hst": "0.3"}, {"hst": "nan"}, {"hst": "x"}, {"hst": ""}, {"hg": "true"}, {"hg": "2"}, {"hp": ""},
])
def test_invalid_heatmap_parameters_are_ignored(bad):
    assert share.parse_params(bad) == {}


def test_heatmap_bounds_are_inclusive_and_not_clamped():
    ok = share.parse_params({"htmin": "-10", "htmax": "60", "hrmin": "0", "hrmax": "100", "hz": "0"})
    assert ok == {"hm_tmin": -10.0, "hm_tmax": 60.0, "hm_rhmin": 0.0, "hm_rhmax": 100.0, "hm_zmax": 0.0}


# ---- setup (JSON) document ---------------------------------------------------------------------
def test_setup_document_structure_and_parameters_are_the_share_serialization():
    import json
    doc = json.loads(share.setup_json(HM_STATE))
    assert doc["format"] == "vpd-calculator-setup" and doc["schema_version"] == 1
    assert set(doc) == {"format", "schema_version", "parameters"}
    assert doc["parameters"] == share.build_params(HM_STATE)             # one canonical list of settings
    assert share.SETUP_FILENAME == "vpd-setup.json"
    assert {"t", "dt", "nt", "htmin", "hk"} <= set(doc["parameters"])


def test_setup_document_contains_no_session_internals():
    state = HM_STATE | {"png": ("sig", b"\x89PNG"), "val_png": ("sig", b"x"), "_share_loaded": True}
    text = share.setup_json(state)
    assert "png" not in text.lower() and "_share_loaded" not in text and "sig" not in text
