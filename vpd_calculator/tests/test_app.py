"""Streamlit AppTest interaction tests (no browser). Widgets are addressed by stable keys."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import share
import vpd

pytestmark = pytest.mark.apptest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def new_app():
    return AppTest.from_file(APP, default_timeout=90)


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def set_num(at, key, value):
    at.number_input(key=f"{key}__num").set_value(value).run()


def tables(at):
    return {tuple(df.value.columns): df.value for df in at.dataframe}


# ---- defaults and modes -------------------------------------------------------------
def test_default_run_has_no_exceptions_and_known_values():
    at = new_app().run()
    assert not at.exception
    assert at.radio(key="mode").value == share.MODE_A
    assert metric(at, "Air VPD") == "1.058 kPa"


def test_five_tabs_present():
    at = new_app().run()
    assert [t.label for t in at.tabs] == [
        "Calculator", "VPD Heatmap", "Day/Night Experiments", "Measured Data", "Methods & References"]


def test_switch_to_required_rh_mode_matches_spec_example():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert not at.exception
    assert metric(at, "Required relative humidity") == "62.18 %"


def test_temperature_preserved_across_modes():
    at = new_app().run()
    set_num(at, "t_air", 30.5)
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="mode").set_value(share.MODE_A).run()
    assert at.session_state["t_air"] == 30.5 and at.session_state["t_air__sld"] == 30.5
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(30.5, 60):.3f} kPa"


# ---- editing inputs -------------------------------------------------------------------
def test_edit_temperature_and_rh_forward():
    at = new_app().run()
    set_num(at, "t_air", 25.0)
    set_num(at, "rh", 40.5)
    assert not at.exception
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(25, 40.5):.3f} kPa"


def test_edit_target_vpd_reverse():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 0.8)
    assert metric(at, "Required relative humidity") == f"{vpd.rh_for_air_vpd(22, 0.8):.2f} %"


def test_slider_updates_number_input():
    at = new_app().run()
    at.slider(key="t_air__sld").set_value(18.0).run()
    assert at.session_state["t_air"] == 18.0 and at.session_state["t_air__num"] == 18.0


# ---- air vs leaf and leaf offset ---------------------------------------------------------
def test_leaf_offset_changes_leaf_vpd_only():
    at = new_app().run()
    set_num(at, "calc_offset", -2.0)
    assert metric(at, "Air VPD") == "1.058 kPa"
    assert metric(at, "Leaf VPD") == "0.752 kPa"


def test_target_leaf_vpd_with_offset():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="target_kind").set_value(share.LEAF_LABEL).run()
    set_num(at, "calc_offset", -2.0)
    expected = vpd.rh_for_leaf_vpd(22, 1.0, 20)
    assert metric(at, "Required relative humidity") == f"{expected:.2f} %"
    assert metric(at, "Resulting leaf VPD") == "1.000 kPa"


def test_measured_leaf_temperature_input():
    at = new_app().run()
    at.radio(key="calc_leaf_method").set_value(share.MEASURED_METHOD).run()
    set_num(at, "calc_leaf_meas", 20.0)
    assert not at.exception
    assert metric(at, "Leaf VPD") == f"{vpd.vpd_leaf(22, 60, 20):.3f} kPa"


# ---- target ranges (custom, day, night) ---------------------------------------------------
def test_custom_target_interval_rh_range_and_status():
    at = new_app().run()
    label = next(m.label for m in at.metric if m.label.startswith("RH range"))
    assert "0.80-1.20" in label
    rr = vpd.rh_range_for_vpd_range(22, 0.8, 1.2)
    assert next(m.value for m in at.metric if m.label == label) == f"{rr['rh_min']:.2f} - {rr['rh_max']:.2f} %"
    assert any("inside" in s.value for s in at.success)
    set_num(at, "vpd_hi", 1.0)
    assert any("above" in w.value for w in at.warning)


def test_interval_limits_validation_message():
    at = new_app().run()
    set_num(at, "vpd_lo", 2.0)
    set_num(at, "vpd_hi", 1.0)
    assert any("Lower limit must not exceed" in e.value for e in at.error)
    assert not at.exception


def test_day_and_night_target_vpd_required_rh():
    at = new_app().run()
    at.radio(key="dn_workflow").set_value("Enter target VPD, calculate RH").run()
    at.selectbox(key="dn_preset").set_value("Control 2").run()
    set_num(at, "dn_vpd_day", 1.0)
    set_num(at, "dn_vpd_night", 0.6)
    assert not at.exception
    assert at.session_state["dn_t_day"] == 22.0 and at.session_state["dn_t_night"] == 17.0
    values = [m.value for m in at.metric if m.label in ("Day required RH", "Night required RH")]
    assert values == [f"{vpd.rh_for_air_vpd(22, 1.0):.2f} %", f"{vpd.rh_for_air_vpd(17, 0.6):.2f} %"]


def test_day_night_unattainable_target_shows_error():
    at = new_app().run()
    at.radio(key="dn_workflow").set_value("Enter target VPD, calculate RH").run()
    set_num(at, "dn_vpd_day", 4.0)           # exceeds es(22) ~ 2.64 kPa
    assert any(e.value.startswith("Day: Unattainable") for e in at.error)


def test_treatment_presets_all_apply():
    at = new_app().run()
    for name, (day, night) in vpd.TREATMENTS.items():
        at.selectbox(key="dn_preset").set_value(name).run()
        assert (at.session_state["dn_t_day"], at.session_state["dn_t_night"]) == (day, night)
        assert not at.exception


# ---- validation messages ------------------------------------------------------------------------
def test_unattainable_target_shows_error_and_does_not_clamp():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 5.0)
    assert any("Unattainable" in e.value for e in at.error)
    shown = next(m.value for m in at.metric if m.label.startswith("Required relative humidity (not"))
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
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(30, 50):.3f} kPa"


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


# ---- other tabs ---------------------------------------------------------------------------------------
def test_heatmap_tab_controls_and_validation():
    at = new_app().run()
    at.radio(key="hm_kind").set_value("Leaf VPD").run()
    at.selectbox(key="hm_cs").set_value("Viridis").run()
    at.number_input(key="hm_tmin").set_value(35.0).run()
    assert not at.exception
    at.number_input(key="hm_tmin").set_value(45.0).run()          # min > default max (40)
    assert any("Minimum values must be smaller" in e.value for e in at.error)


def test_measured_data_tab_with_example_data():
    at = new_app().run()
    at.checkbox(key="data_example").set_value(True).run()
    assert not at.exception
    assert metric(at, "Mean air VPD").endswith("kPa")
    assert any("rows used" in c.value for c in at.caption)


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
    at.radio(key="dn_workflow").set_value("Enter target VPD, calculate RH").run()
    at.checkbox(key="data_example").set_value(True).run()
    at.checkbox(key="val_johnston").set_value(True).run()
    assert not at.exception
