from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import share
import vpd

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def new_app():
    return AppTest.from_file(APP, default_timeout=90)


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def test_default_run_has_no_exceptions_and_known_values():
    at = new_app().run()
    assert not at.exception
    assert metric(at, "Air VPD") == "1.058 kPa"


def test_switch_to_required_rh_mode_matches_spec_example():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert not at.exception
    assert metric(at, "Required relative humidity") == "62.18 %"


def test_temperature_preserved_across_modes():
    at = new_app().run()
    at.number_input(key="t_air__num").set_value(30.5).run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="mode").set_value(share.MODE_A).run()
    assert at.session_state["t_air"] == 30.5
    assert at.session_state["t_air__sld"] == 30.5
    assert metric(at, "Air VPD") == f"{vpd.vpd_air(30.5, 60):.3f} kPa"


def test_unattainable_target_shows_error():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.number_input(key="target_vpd__num").set_value(5.0).run()
    assert any("Unattainable" in e.value for e in at.error)


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
    at.number_input(key="t_air__num").set_value(18.0).run()
    assert at.query_params["t"] == ["18"] or at.query_params["t"] == "18"


def test_measured_data_tab_with_example_data():
    at = new_app().run()
    at.checkbox(key="data_example").set_value(True).run()
    assert not at.exception
    assert metric(at, "Mean air VPD").endswith("kPa")
    assert any("rows used" in c.value for c in at.caption)


def test_day_night_tab_runs_in_both_workflows():
    at = new_app().run()
    at.radio(key="dn_workflow").set_value("Enter target VPD, calculate RH").run()
    at.selectbox(key="dn_preset").set_value("Warming 2").run()
    assert not at.exception
    assert at.session_state["dn_t_day"] == 33.0 and at.session_state["dn_t_night"] == 28.0
