"""Streamlit AppTest interaction tests (no browser). Widgets are addressed by stable keys."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import presets
import share
import vpd

pytestmark = pytest.mark.apptest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
ONE_DECIMAL = re.compile(r"^-?\d+\.\d( - -?\d+\.\d)? (kPa|%)$")


def new_app():
    return AppTest.from_file(APP, default_timeout=90)


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def metric_starting(at, prefix):
    return next(m for m in at.metric if m.label.startswith(prefix))


def set_num(at, key, value):
    at.number_input(key=f"{key}__num").set_value(value).run()


def tables(at):
    return {tuple(df.value.columns): df.value for df in at.dataframe}


# ---- tabs, defaults and modes -------------------------------------------------------------
def test_default_run_has_no_exceptions_and_known_values():
    at = new_app().run()
    assert not at.exception
    assert at.radio(key="mode").value == share.MODE_A
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(22, 60):.1f} kPa" == "1.1 kPa"


def test_exactly_three_tabs():
    at = new_app().run()
    assert [t.label for t in at.tabs] == ["Calculator", "VPD Heatmap", "Methods & References"]


def test_interface_values_use_one_decimal_place():
    at = new_app().run()
    assert at.metric and all(ONE_DECIMAL.match(m.value) for m in at.metric), [m.value for m in at.metric]
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert all(ONE_DECIMAL.match(m.value) for m in at.metric), [m.value for m in at.metric]


def test_switch_to_required_rh_mode_matches_spec_example():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert not at.exception
    assert metric(at, "Required relative humidity") == "62.2 %"


def test_temperature_preserved_across_modes():
    at = new_app().run()
    set_num(at, "t_air", 30.5)
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="mode").set_value(share.MODE_A).run()
    assert at.session_state["t_air"] == 30.5 and at.session_state["t_air__sld"] == 30.5
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(30.5, 60):.1f} kPa"


def test_full_precision_input_is_kept_internally():
    at = new_app().run()
    set_num(at, "t_air", 22.34)
    assert at.session_state["t_air"] == 22.34


# ---- editing inputs -------------------------------------------------------------------
def test_edit_temperature_and_rh_forward():
    at = new_app().run()
    set_num(at, "t_air", 25.0)
    set_num(at, "rh", 40.5)
    assert not at.exception
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(25, 40.5):.1f} kPa"


def test_edit_target_vpd_reverse():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 0.8)
    assert metric(at, "Required relative humidity") == f"{vpd.rh_for_air_vpd(22, 0.8):.1f} %"


def test_slider_updates_number_input():
    at = new_app().run()
    at.slider(key="t_air__sld").set_value(18.0).run()
    assert at.session_state["t_air"] == 18.0 and at.session_state["t_air__num"] == 18.0


# ---- air vs leaf and leaf offset ---------------------------------------------------------
def test_leaf_offset_changes_leaf_vpd_only():
    at = new_app().run()
    set_num(at, "calc_offset", -2.0)
    assert metric(at, "Air VPD") == "1.1 kPa"
    assert metric(at, "Leaf VPD") == f"{vpd.vpd_leaf(22, 60, 20):.1f} kPa"


def test_leaf_offset_presets():
    at = new_app().run()
    for label, value in zip(presets.LEAF_OFFSET_NAMES[:-1], presets.LEAF_OFFSET_PRESETS):
        at.selectbox(key="calc_offset_preset").set_value(label).run()
        assert at.session_state["calc_offset"] == value, label
        assert metric(at, "Leaf VPD") == f"{vpd.vpd_leaf(22, 60, 22 + value):.1f} kPa"
    assert not at.exception


def test_leaf_offset_custom_value_switches_preset_to_custom():
    at = new_app().run()
    at.selectbox(key="calc_offset_preset").set_value("-2 °C").run()
    set_num(at, "calc_offset", -1.5)
    assert at.session_state["calc_offset_preset"] == "Custom"
    set_num(at, "calc_offset", 2.0)
    assert at.session_state["calc_offset_preset"] == "+2 °C"


def test_leaf_offset_disclaimer_and_explanation_present():
    at = new_app().run()
    text = " ".join(c.value for c in at.caption) + " ".join(m.value for m in at.markdown)
    assert "not universal correction factors" in text
    assert "VPD_{leaf}" in text and "condensation" in text


def test_target_leaf_vpd_with_offset():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="target_kind").set_value(share.LEAF_LABEL).run()
    set_num(at, "calc_offset", -2.0)
    expected = vpd.rh_for_leaf_vpd(22, 1.0, 20)
    assert metric(at, "Required relative humidity") == f"{expected:.1f} %"
    assert metric(at, "Resulting leaf VPD") == "1.0 kPa"


def test_measured_leaf_temperature_input():
    at = new_app().run()
    at.radio(key="calc_leaf_method").set_value(share.MEASURED_METHOD).run()
    set_num(at, "calc_leaf_meas", 20.0)
    assert not at.exception
    assert metric(at, "Leaf VPD") == f"{vpd.vpd_leaf(22, 60, 20):.1f} kPa"


# ---- target VPD range and presets ------------------------------------------------------------
def test_range_section_is_named_range_not_interval():
    at = new_app().run()
    headers = [s.value for s in at.subheader]
    assert "Target VPD range" in headers
    assert not any("interval" in (s.value or "").lower() for s in at.subheader)


@pytest.mark.parametrize("stage", list(presets.GROWTH_STAGES))
def test_growth_stage_presets_set_the_range(stage):
    at = new_app().run()
    at.selectbox(key="vpd_preset").set_value(stage).run()
    lo, hi = presets.stage_range(stage, "day")
    assert (at.session_state["vpd_lo"], at.session_state["vpd_hi"]) == (lo, hi)
    assert not at.exception
    assert any("not scientifically validated" in c.value for c in at.caption)


def test_custom_preset_keeps_values_and_edit_switches_to_custom():
    at = new_app().run()
    at.selectbox(key="vpd_preset").set_value("Flowering").run()
    at.selectbox(key="vpd_preset").set_value("Custom").run()
    assert (at.session_state["vpd_lo"], at.session_state["vpd_hi"]) == (1.2, 1.5)
    at.selectbox(key="vpd_preset").set_value("Vegetative").run()
    set_num(at, "vpd_lo", 0.9)
    assert at.session_state["vpd_preset"] == "Custom"


def test_custom_range_rh_range_and_status():
    at = new_app().run()
    label = metric_starting(at, "RH range").label
    assert "0.8-1.2" in label
    rr = vpd.rh_range_for_vpd_range(22, 0.8, 1.2)
    assert metric(at, label) == f"{rr['rh_min']:.1f} - {rr['rh_max']:.1f} %"
    assert any("inside" in s.value for s in at.success)
    set_num(at, "vpd_hi", 1.0)
    assert any("above" in w.value for w in at.warning)


def test_range_limits_validation_message():
    at = new_app().run()
    set_num(at, "vpd_lo", 2.0)
    set_num(at, "vpd_hi", 1.0)
    assert any("Lower limit must not exceed" in e.value for e in at.error)
    assert not at.exception


# ---- day and night sections --------------------------------------------------------------------
def test_day_and_night_sections_are_stacked_and_independent():
    at = new_app().run()
    day = metric_starting(at, "Day RH range")
    night = metric_starting(at, "Night RH range")
    assert "22.0 °C" in day.label and "17.0 °C" in night.label
    rr_n = vpd.rh_range_for_vpd_range(17, 0.8, 1.2)
    assert night.value == f"{rr_n['rh_min']:.1f} - {rr_n['rh_max']:.1f} %"
    set_num(at, "dn_t_night", 15.0)
    set_num(at, "dn_off_night", -2.0)
    at.selectbox(key="dn_preset_night").set_value("Flowering").run()
    assert (at.session_state["dn_lo_night"], at.session_state["dn_hi_night"]) == (1.0, 1.5)
    assert at.session_state["dn_t_day"] == 22.0 and (at.session_state["dn_lo_day"], at.session_state["dn_hi_day"]) == (0.8, 1.2)
    rr_n = vpd.rh_range_for_vpd_range(15, 1.0, 1.5, vpd.AIR, -2.0)
    assert metric_starting(at, "Night RH range").value == f"{rr_n['rh_min']:.1f} - {rr_n['rh_max']:.1f} %"
    assert metric_starting(at, "Day RH range").value == f"{vpd.rh_range_for_vpd_range(22, 0.8, 1.2)['rh_min']:.1f} - " \
                                                         f"{vpd.rh_range_for_vpd_range(22, 0.8, 1.2)['rh_max']:.1f} %"
    assert not at.exception


def test_day_night_presets_use_period_specific_ranges():
    at = new_app().run()
    at.selectbox(key="dn_preset_day").set_value("Seedlings / propagation").run()
    at.selectbox(key="dn_preset_night").set_value("Seedlings / propagation").run()
    assert (at.session_state["dn_lo_day"], at.session_state["dn_hi_day"]) == (0.8, 0.8)
    assert (at.session_state["dn_lo_night"], at.session_state["dn_hi_night"]) == (0.6, 1.0)


def test_condensation_guidance_depends_on_leaf_offset():
    at = new_app().run()
    texts = [e.value for e in list(at.info) + list(at.warning)]
    assert any("Condensation guidance" in t and "not cooler" in t for t in texts)
    set_num(at, "dn_off_night", -3.0)
    rh_c = float(vpd.condensation_rh(17, 14))
    texts = [e.value for e in list(at.info) + list(at.warning)]
    assert any("Condensation guidance" in t and f"{rh_c:.1f} % RH" in t for t in texts)


def test_day_night_unattainable_range_shows_error():
    at = new_app().run()
    set_num(at, "dn_hi_day", 4.0)
    set_num(at, "dn_lo_day", 3.5)           # both exceed es(22) ~ 2.6 kPa
    assert any(e.value.startswith("Day: no RH") for e in at.error)


def test_day_night_inverted_range_shows_error():
    at = new_app().run()
    set_num(at, "dn_lo_night", 2.0)
    assert any("Night: lower limit must not exceed" in e.value for e in at.error)


# ---- validation messages ------------------------------------------------------------------------
def test_unattainable_target_shows_error_and_does_not_clamp():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 5.0)
    assert any("Unattainable" in e.value for e in at.error)
    shown = metric_starting(at, "Required relative humidity (not").value
    assert float(shown.split()[0]) < 0          # raw, unclamped value is displayed


def test_unattainable_below_minimum_leaf_target():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="target_kind").set_value(share.LEAF_LABEL).run()
    set_num(at, "calc_offset", -3.0)
    set_num(at, "target_vpd", -1.0)
    assert any("Unattainable" in e.value for e in at.error)


def test_negative_leaf_vpd_warning():
    at = new_app().run()
    set_num(at, "rh", 98.0)
    set_num(at, "calc_offset", -3.0)
    assert any("condensation" in w.value for w in at.warning)


# ---- share links and query parameters --------------------------------------------------------------
def test_share_link_restores_settings():
    at = new_app()
    at.query_params["t"] = "30"
    at.query_params["rh"] = "50"
    at.run()
    assert not at.exception
    assert at.session_state["t_air"] == 30.0
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(30, 50):.1f} kPa"


def test_legacy_share_url_still_works_and_selects_matching_preset():
    at = new_app()
    for k, v in {"m": "b", "t": "25", "rh": "60", "tv": "1.1", "k": "leaf", "lo": "1.2", "hi": "1.5",
                 "ik": "leaf", "off": "-2"}.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception
    s = at.session_state
    assert (s["t_air"], s["target_vpd"], s["target_kind"], s["interval_kind"], s["calc_offset"]) == (
        25.0, 1.1, share.LEAF_LABEL, share.LEAF_LABEL, -2.0)
    assert s["vpd_preset"] == "Flowering" and s["calc_offset_preset"] == "-2 °C"
    assert metric(at, "Required relative humidity") == f"{vpd.rh_for_leaf_vpd(25, 1.1, 23):.1f} %"


def test_invalid_share_link_falls_back_to_defaults():
    at = new_app()
    at.query_params["t"] = "banana"
    at.query_params["rh"] = "999"
    at.run()
    assert not at.exception
    assert at.session_state["t_air"] == 22.0 and at.session_state["rh"] == 60.0


def test_query_params_follow_state():
    at = new_app().run()
    set_num(at, "t_air", 18.0)
    assert at.query_params["t"] in ("18", ["18"])


# ---- heatmap and methods tabs ---------------------------------------------------------------------------
def test_heatmap_tab_controls_and_validation():
    at = new_app().run()
    at.radio(key="hm_kind").set_value("Leaf VPD").run()
    at.selectbox(key="hm_cs").set_value("Viridis").run()
    at.number_input(key="hm_tmin").set_value(35.0).run()
    assert not at.exception
    at.number_input(key="hm_tmin").set_value(45.0).run()          # min > default max (40)
    assert any("Minimum values must be smaller" in e.value for e in at.error)


def test_methods_tab_has_citations_and_references():
    at = new_app().run()
    codes = [c.value for c in at.code]
    assert any(c.startswith("Smits, M. A. (2026).") for c in codes)
    assert any(c.startswith("@misc{") for c in codes)
    assert any(c.startswith("M. A. Smits, ") for c in codes)
    md = " ".join(m.value for m in at.markdown)
    for needle in ("kiag575", "nph.16485", "e2024JG008146", "Koverda, P. (2020, February 12)",
                   "It is not the source of the equations"):
        assert needle in md, needle


def test_validation_tables_render_with_computed_outcomes():
    at = new_app().run()
    assert not at.exception
    t = tables(at)
    vpd_table = next(v for k, v in t.items() if "Validation outcome" in k)
    assert len(vpd_table) == 5 and (vpd_table["Validation outcome"] == "Within tolerance").all()
    es_table = next(v for k, v in t.items() if "Published es (kPa)" in k)
    assert len(es_table) == 7 and (es_table["Outcome"] == "Within tolerance").all()


def test_validation_plot_controls():
    at = new_app().run()
    at.multiselect(key="val_temps").set_value([10, 20, 30, 40]).run()
    at.checkbox(key="val_johnston").set_value(True).run()
    assert not at.exception
    at.multiselect(key="val_temps").set_value([]).run()
    assert any("at least one temperature" in i.value for i in at.info)
    at.number_input(key="val_extra_t").set_value(10.0).run()
    assert not at.exception


def test_every_tab_renders_after_a_full_interaction_sequence():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "t_air", 33.0)
    at.selectbox(key="dn_preset_day").set_value("Flowering").run()
    at.checkbox(key="val_johnston").set_value(True).run()
    assert not at.exception
