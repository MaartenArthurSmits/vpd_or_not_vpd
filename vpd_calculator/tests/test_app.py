"""Streamlit AppTest interaction tests (no browser). Widgets are addressed by stable keys."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import mpl_export
import presets
import share
import validation
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
    vpd_table = next(v for k, v in t.items() if "Outcome (vs calculated benchmark)" in k)
    assert len(vpd_table) == 5 and (vpd_table["Outcome (vs calculated benchmark)"] == "Within tolerance").all()
    es_table = next(v for k, v in t.items() if "Published es (kPa)" in k)
    assert len(es_table) == 7 and (es_table["Outcome"] == "Within tolerance").all()


def test_validation_labels_separate_published_from_calculated_benchmarks():
    at = new_app().run()
    cols = [c for df in at.dataframe for c in df.value.columns]
    assert "Published es (kPa)" in cols                                       # only Table 2.3 is "published"
    assert "FAO-56 calculated benchmark VPD (kPa)" in cols
    assert "Johnston calculated benchmark VPD (kPa)" in cols
    assert not any("reference VPD" in c or "published reference" in c for c in cols), cols
    body = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "calculated benchmarks" in body and "not** printed in FAO-56 Table 2.3" in body
    assert "calculated benchmark" in body and "published reference" not in body


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


# ---- single-value (point) targets: equal lower and upper limits -----------------------------------
def point_target_app(value=1.0):
    at = new_app().run()
    set_num(at, "vpd_hi", max(value, at.session_state["vpd_hi"]))
    set_num(at, "vpd_lo", value)
    set_num(at, "vpd_hi", value)
    assert at.session_state["vpd_lo"] == at.session_state["vpd_hi"] == value
    return at


def texts(elements):
    return [e.value for e in elements]


def test_point_target_labels_and_single_rh_value():
    at = point_target_app(1.0)
    assert not at.exception
    assert any("Target air VPD: 1.0 kPa" in v for v in texts(at.markdown))
    m = metric_starting(at, "Required RH for air VPD 1.0 kPa")
    assert m.label == "Required RH for air VPD 1.0 kPa at 22.0 °C"
    assert m.value == f"{vpd.rh_for_air_vpd(22, 1.0):.1f} %" and " - " not in m.value
    assert not any(x.label.startswith("RH range for") for x in at.metric)
    assert not any("1.0-1.0" in v for v in texts(at.markdown) + texts(at.success) + texts(at.warning))


def test_point_target_uses_leaf_wording_for_leaf_basis():
    at = point_target_app(1.0)
    at.radio(key="interval_kind").set_value("Leaf VPD").run()
    assert any("Target leaf VPD: 1.0 kPa" in v for v in texts(at.markdown))
    assert metric_starting(at, "Required RH for leaf VPD 1.0 kPa").value.endswith(" %")


@pytest.mark.parametrize("rh,word", [(60.0, "above target"), (80.0, "below target")])
def test_point_target_below_and_above_wording(rh, word):
    at = point_target_app(1.0)
    set_num(at, "rh", rh)
    assert any(word in v for v in texts(at.warning)), texts(at.warning)
    assert not any("the range" in v for v in texts(at.warning) + texts(at.success))


def test_point_target_at_25c_reverse_calculation_is_at_target():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "t_air", 25.0)
    set_num(at, "target_vpd", 1.0)
    set_num(at, "vpd_hi", 1.0)
    set_num(at, "vpd_lo", 1.0)
    assert not at.exception
    assert vpd.calculate_required_rh(25, 1.0, vpd.AIR).vpd_air > 1.0          # floating-point overshoot
    assert any("at target" in v for v in texts(at.success)), (texts(at.success), texts(at.warning))
    assert not any("above target" in v for v in texts(at.warning))


def test_unequal_range_wording_is_unchanged():
    at = new_app().run()
    set_num(at, "vpd_lo", 0.8)
    set_num(at, "vpd_hi", 1.2)
    assert any("inside the range 0.8-1.2 kPa" in v for v in texts(at.success))
    m = metric_starting(at, "RH range for air VPD 0.8-1.2 kPa")
    assert " - " in m.value and m.value.endswith(" %")
    assert not any("Target air VPD:" in v for v in texts(at.markdown))
    assert not any("at target" in v for v in texts(at.success) + texts(at.warning))


def test_unattainable_point_target_shows_single_value_error():
    at = point_target_app(5.0)
    errors = texts(at.error)
    assert any("No RH between 0 and 100 % gives a air VPD of 5.0 kPa" in e and " to " not in e for e in errors), errors
    assert not any(m.label.startswith(("Required RH for", "RH range for")) for m in at.metric)


def test_day_and_night_point_targets_use_single_value_display():
    at = new_app().run()
    at.selectbox(key="dn_preset_day").set_value("Vegetative").run()      # day 1.0-1.0 kPa
    assert not at.exception
    m = metric_starting(at, "Day required RH for air VPD 1.0 kPa")
    assert " - " not in m.value and m.value.endswith(" %")
    assert any("Day target air VPD: 1.0 kPa" in v for v in texts(at.markdown))
    # night preset for Vegetative is a genuine range and keeps the range display
    at.selectbox(key="dn_preset_night").set_value("Vegetative").run()
    n = metric_starting(at, "Night RH range for air VPD 0.8-1.2 kPa")
    assert " - " in n.value


def test_day_point_target_unattainable():
    at = new_app().run()
    set_num(at, "dn_hi_day", 5.0)
    set_num(at, "dn_lo_day", 5.0)
    assert any("Day: no RH between 0 and 100 % gives a air VPD of 5.0 kPa" in e for e in texts(at.error))


# ---- validation-plot PNG cache: a download must match the displayed graph --------------------------
VAL_DL_LABEL = "Download VPD-vs-RH graph (PNG)"


def val_png_offered(at):
    return any(getattr(b.proto, "label", "") == VAL_DL_LABEL for b in at.get("download_button"))


def val_png_expected(temps, johnston):
    curves = validation.reference_curves(sorted(temps))
    return mpl_export.to_bytes(mpl_export.reference_mpl(curves, johnston), "png", 200)


def prepare_val_png(at):
    at.button(key="val_png_prepare").click().run()
    assert not at.exception
    return at.session_state["val_png"][1]


def test_val_png_expected_render_is_deterministic():
    assert val_png_expected([20, 25], False) == val_png_expected([20, 25], False)
    assert val_png_expected([20, 25], False) != val_png_expected([20, 25], True)
    assert val_png_expected([20, 25], False) != val_png_expected([20, 30], False)


def test_val_png_not_offered_until_prepared_then_kept_on_unchanged_rerun():
    at = new_app().run()
    assert not val_png_offered(at)
    png = prepare_val_png(at)
    assert val_png_offered(at) and png == val_png_expected([20, 25, 30], False)
    at.run()                                                                      # ordinary rerun
    set_num(at, "t_air", 24.0)                                                    # unrelated input
    assert val_png_offered(at) and at.session_state["val_png"][1] == png


def test_val_png_invalidated_when_temperatures_change_and_regenerated_with_new_inputs():
    at = new_app().run()
    old = prepare_val_png(at)
    at.multiselect(key="val_temps").set_value([10, 35]).run()
    assert not at.exception and not val_png_offered(at)
    new = prepare_val_png(at)
    assert val_png_offered(at)
    assert new == val_png_expected([10, 35], False) and new != old
    assert at.session_state["val_png"][0] == ((10, 35), False)


def test_val_png_invalidated_when_johnston_overlay_changes_and_regenerated():
    at = new_app().run()
    old = prepare_val_png(at)
    at.checkbox(key="val_johnston").set_value(True).run()
    assert not at.exception and not val_png_offered(at)
    new = prepare_val_png(at)
    assert val_png_offered(at)
    assert new == val_png_expected([20, 25, 30], True) and new != old
    at.checkbox(key="val_johnston").set_value(False).run()                        # back to the old setting
    assert not val_png_offered(at)                                                # cache holds the Johnston image


def test_val_png_temperature_order_does_not_invalidate():
    at = new_app().run()
    png = prepare_val_png(at)
    at.multiselect(key="val_temps").set_value([30, 20, 25]).run()
    assert val_png_offered(at) and at.session_state["val_png"][1] == png


def test_val_png_clearing_temperatures_hides_download_without_error():
    at = new_app().run()
    prepare_val_png(at)
    at.multiselect(key="val_temps").set_value([]).run()
    assert not at.exception and not val_png_offered(at)
    assert any("at least one temperature" in i.value for i in at.info)
    at.multiselect(key="val_temps").set_value([15]).run()                          # a different selection
    assert not at.exception and not val_png_offered(at)
    assert prepare_val_png(at) == val_png_expected([15], False)


# ---- day/night settings in shareable links ---------------------------------------------------------
def es_hand(t):                                  # stand-alone FAO-56 Eq. 11, independent of production code
    import math
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


ACCEPTANCE = {"dt": "33", "doff": "-2", "dlo": "1.0", "dhi": "1.0", "dk": "leaf", "dp": "veg",
              "nt": "17", "noff": "1", "nlo": "0.6", "nhi": "1.0", "nk": "air", "np": "seed"}


def app_with_params(params):
    at = new_app()
    for k, v in params.items():
        at.query_params[k] = v
    return at.run()


def qp(at, key):
    v = at.query_params[key]
    return v[0] if isinstance(v, list) else v


def test_day_night_link_restores_controls_and_rh_results_in_fresh_session():
    at = app_with_params(ACCEPTANCE)
    assert not at.exception
    s = at.session_state
    # controls
    assert at.number_input(key="dn_t_day__num").value == 33.0
    assert at.number_input(key="dn_off_day__num").value == -2.0
    assert at.number_input(key="dn_lo_day__num").value == 1.0 == at.number_input(key="dn_hi_day__num").value
    assert at.radio(key="dn_kind_day").value == share.LEAF_LABEL
    assert at.selectbox(key="dn_preset_day").value == "Vegetative"
    assert at.selectbox(key="dn_offset_preset_day").value == "-2 °C"
    assert at.number_input(key="dn_t_night__num").value == 17.0
    assert at.number_input(key="dn_off_night__num").value == 1.0
    assert at.number_input(key="dn_lo_night__num").value == 0.6
    assert at.number_input(key="dn_hi_night__num").value == 1.0
    assert at.radio(key="dn_kind_night").value == share.AIR_LABEL
    assert at.selectbox(key="dn_preset_night").value == "Seedlings / propagation"
    assert at.selectbox(key="dn_offset_preset_night").value == "+1 °C"
    # calculated results (hand-computed with a stand-alone equation)
    day_rh = 100 * (es_hand(33 - 2) - 1.0) / es_hand(33)
    m = metric_starting(at, "Day required RH for leaf VPD 1.0 kPa at 33.0 °C")
    assert m.value == f"{day_rh:.1f} %"
    rh_lo, rh_hi = 100 * (1 - 1.0 / es_hand(17)), 100 * (1 - 0.6 / es_hand(17))
    n = metric_starting(at, "Night RH range for air VPD 0.6-1.0 kPa at 17.0 °C")
    assert n.value == f"{rh_lo:.1f} - {rh_hi:.1f} %"
    # the main calculator is untouched
    assert (s["t_air"], s["rh"], s["vpd_lo"], s["vpd_hi"], s["calc_offset"]) == (22.0, 60.0, 0.8, 1.2, 0.0)
    assert metric(at, "Air VPD") == "1.1 kPa"


def test_share_link_restores_preset_identity_and_custom_status():
    # Vegetative night and General horticulture night share the range 0.8-1.2 kPa.
    at = app_with_params({"nlo": "0.8", "nhi": "1.2", "np": "veg", "dlo": "0.9", "dhi": "1.3", "dp": "custom"})
    assert not at.exception
    assert at.selectbox(key="dn_preset_night").value == "Vegetative"
    assert at.selectbox(key="dn_preset_day").value == "Custom"
    assert (at.session_state["dn_lo_night"], at.session_state["dn_hi_night"]) == (0.8, 1.2)   # limits not overwritten
    assert (at.session_state["dn_lo_day"], at.session_state["dn_hi_day"]) == (0.9, 1.3)
    at2 = app_with_params({"nlo": "0.8", "nhi": "1.2", "np": "gen"})
    assert at2.selectbox(key="dn_preset_night").value == "General horticulture"


def test_inconsistent_or_unknown_preset_does_not_overwrite_saved_limits():
    at = app_with_params({"dlo": "0.8", "dhi": "1.2", "dp": "flow", "nlo": "0.7", "nhi": "1.1", "np": "nonsense"})
    assert not at.exception
    s = at.session_state
    assert (s["dn_lo_day"], s["dn_hi_day"], s["dn_lo_night"], s["dn_hi_night"]) == (0.8, 1.2, 0.7, 1.1)
    assert s["dn_preset_day"] == "General horticulture" and s["dn_preset_night"] == "Custom"


def test_legacy_link_keeps_day_night_defaults_and_old_presets():
    at = app_with_params({"m": "a", "t": "25", "rh": "40", "lo": "1.2", "hi": "1.5"})
    assert not at.exception
    s = at.session_state
    assert (s["dn_t_day"], s["dn_t_night"], s["dn_off_day"], s["dn_off_night"]) == (22.0, 17.0, 0.0, 0.0)
    assert (s["dn_lo_day"], s["dn_hi_day"], s["dn_lo_night"], s["dn_hi_night"]) == (0.8, 1.2, 0.8, 1.2)
    assert at.radio(key="dn_kind_day").value == share.AIR_LABEL
    assert s["dn_preset_day"] == s["dn_preset_night"] == "General horticulture"
    assert s["vpd_preset"] == "Flowering"


@pytest.mark.parametrize("bad", [
    {"dt": "abc", "nt": "nan", "doff": "inf", "noff": "-inf"},
    {"dt": "999", "nt": "-999", "dlo": "-5", "nhi": "50"},
    {"dk": "banana", "nk": "", "dp": "???", "np": "Vegetative"},
    {"dt": "", "dlo": "1e999", "nlo": "0x10"},
])
def test_invalid_day_night_link_parameters_fall_back_to_defaults_without_error(bad):
    at = app_with_params(bad)
    assert not at.exception
    s = at.session_state
    assert (s["dn_t_day"], s["dn_t_night"], s["dn_off_day"], s["dn_off_night"]) == (22.0, 17.0, 0.0, 0.0)
    assert (s["dn_lo_day"], s["dn_hi_day"], s["dn_lo_night"], s["dn_hi_night"]) == (0.8, 1.2, 0.8, 1.2)
    assert at.radio(key="dn_kind_day").value == at.radio(key="dn_kind_night").value == share.AIR_LABEL


def test_editing_day_night_settings_updates_url_and_leaves_other_period_and_main_untouched():
    at = new_app().run()
    set_num(at, "dn_t_day", 33.0)
    set_num(at, "dn_off_day", -2.0)
    at.radio(key="dn_kind_day").set_value(share.LEAF_LABEL).run()
    at.selectbox(key="dn_preset_day").set_value("Vegetative").run()
    assert (qp(at, "dt"), qp(at, "doff"), qp(at, "dk"), qp(at, "dp")) == ("33", "-2", "leaf", "veg")
    assert (qp(at, "dlo"), qp(at, "dhi")) == ("1", "1")
    assert (qp(at, "nt"), qp(at, "noff"), qp(at, "nk"), qp(at, "nlo"), qp(at, "nhi")) == ("17", "0", "air", "0.8", "1.2")
    assert (qp(at, "t"), qp(at, "rh"), qp(at, "lo"), qp(at, "hi")) == ("22", "60", "0.8", "1.2")
    set_num(at, "dn_hi_night", 1.5)
    assert qp(at, "nhi") == "1.5" and qp(at, "np") == "custom" and qp(at, "dhi") == "1"
    assert qp(at, "dt") == "33" and qp(at, "t") == "22"


def test_app_url_round_trip_into_a_fresh_session():
    at = new_app().run()
    set_num(at, "dn_t_night", 18.5)
    set_num(at, "dn_off_night", 1.0)
    at.radio(key="dn_kind_night").set_value(share.LEAF_LABEL).run()
    set_num(at, "dn_hi_night", 1.4)
    set_num(at, "dn_lo_night", 1.4)
    at.selectbox(key="dn_preset_day").set_value("Flowering").run()
    link = {k: qp(at, k) for k in ("dt", "doff", "dlo", "dhi", "dk", "dp", "nt", "noff", "nlo", "nhi", "nk", "np")}
    fresh = app_with_params(link)
    assert not fresh.exception
    for key in ("dn_t_day", "dn_off_day", "dn_lo_day", "dn_hi_day", "dn_preset_day", "dn_kind_day",
                "dn_t_night", "dn_off_night", "dn_lo_night", "dn_hi_night", "dn_preset_night", "dn_kind_night"):
        assert fresh.session_state[key] == at.session_state[key], key
    assert fresh.selectbox(key="dn_preset_day").value == "Flowering"
    assert fresh.selectbox(key="dn_preset_night").value == "Custom"


def test_share_explanation_mentions_day_night_settings():
    at = new_app().run()
    text = " ".join(c.value for c in at.caption)
    assert "independently for day and night" in text and "preset" in text


# ---- heatmap settings in shareable links -----------------------------------------------------------
HEATMAP_LINK = {"hk": "leaf", "htmin": "12", "htmax": "38", "hrmin": "25", "hrmax": "95", "hz": "3.5",
                "hcs": "Viridis", "hst": "0.2", "hg": "0", "hp": "0"}


def heatmap_spec(at):
    import json
    charts = [c for c in at.get("plotly_chart") if "temperature and relative humidity" in c.proto.spec]
    assert len(charts) == 1
    return json.loads(charts[0].proto.spec)


def test_heatmap_link_restores_controls_and_chart_alongside_other_settings():
    params = ACCEPTANCE | {"t": "25", "rh": "40", "lo": "0.9", "hi": "1.3", "ik": "leaf", "off": "-2"} | HEATMAP_LINK
    at = app_with_params(params)
    assert not at.exception
    # heatmap controls
    assert at.radio(key="hm_kind").value == share.LEAF_LABEL
    assert (at.number_input(key="hm_tmin").value, at.number_input(key="hm_tmax").value) == (12.0, 38.0)
    assert (at.number_input(key="hm_rhmin").value, at.number_input(key="hm_rhmax").value) == (25.0, 95.0)
    assert at.number_input(key="hm_zmax").value == 3.5
    assert at.selectbox(key="hm_cs").value == "Viridis" and at.selectbox(key="hm_step").value == 0.2
    assert at.checkbox(key="hm_target").value is False and at.checkbox(key="hm_point").value is False
    # the chart follows those settings
    spec = heatmap_spec(at)
    layout = spec["layout"]
    assert layout["xaxis"]["range"] == [12, 38] and layout["yaxis"]["range"] == [25, 95]
    assert "Leaf VPD" in layout["title"]["text"]
    heat = spec["data"][0]
    assert heat["zmax"] == 3.5 and heat["colorbar"]["title"]["text"] == "Leaf VPD (kPa)"
    assert heat["colorscale"][0][1] == "#440154"                                   # Viridis
    assert [d["type"] for d in spec["data"]] == ["heatmap", "contour"]             # no target layers, no point
    assert spec["data"][1]["contours"]["size"] == 0.2
    # calculator and day/night settings are restored as well
    s = at.session_state
    assert (s["t_air"], s["rh"], s["vpd_lo"], s["vpd_hi"], s["calc_offset"]) == (25.0, 40.0, 0.9, 1.3, -2.0)
    assert s["interval_kind"] == share.LEAF_LABEL
    assert (s["dn_t_day"], s["dn_off_day"], s["dn_kind_day"], s["dn_preset_day"]) == (
        33.0, -2.0, share.LEAF_LABEL, "Vegetative")
    assert (s["dn_t_night"], s["dn_hi_night"], s["dn_kind_night"]) == (17.0, 1.0, share.AIR_LABEL)


def test_heatmap_toggles_on_restore_target_and_point_layers():
    at = app_with_params({"hg": "1", "hp": "1", "ik": "leaf", "lo": "0.8", "hi": "1.2", "hk": "air"})
    kinds = [d["type"] for d in heatmap_spec(at)["data"]]
    assert kinds == ["heatmap", "heatmap", "contour", "contour", "scatter"]


def test_app_url_round_trip_of_heatmap_settings_into_a_fresh_session():
    at = new_app().run()
    at.radio(key="hm_kind").set_value(share.LEAF_LABEL).run()
    at.number_input(key="hm_tmin").set_value(15.0).run()
    at.number_input(key="hm_rhmax").set_value(90.0).run()
    at.selectbox(key="hm_cs").set_value("Turbo").run()
    at.selectbox(key="hm_step").set_value(0.1).run()
    at.number_input(key="hm_zmax").set_value(4.0).run()
    at.checkbox(key="hm_point").set_value(False).run()
    set_num(at, "t_air", 27.0)
    set_num(at, "dn_t_night", 15.5)
    link = {k: qp(at, k) for k in at.query_params}
    assert {"hk", "htmin", "htmax", "hrmin", "hrmax", "hz", "hcs", "hst", "hg", "hp"} <= set(link)
    fresh = app_with_params(link)
    assert not fresh.exception
    for key in ("hm_kind", "hm_tmin", "hm_tmax", "hm_rhmin", "hm_rhmax", "hm_cs", "hm_step", "hm_zmax",
                "hm_target", "hm_point", "t_air", "dn_t_night"):
        assert fresh.session_state[key] == at.session_state[key], key
    assert heatmap_spec(fresh)["layout"] == heatmap_spec(at)["layout"]


def test_editing_heatmap_settings_updates_url_without_touching_other_settings():
    at = new_app().run()
    before = {k: qp(at, k) for k in ("t", "rh", "dt", "nt", "dlo", "nhi")}
    at.selectbox(key="hm_cs").set_value("Plasma").run()
    at.checkbox(key="hm_target").set_value(False).run()
    assert qp(at, "hcs") == "Plasma" and qp(at, "hg") == "0"
    assert {k: qp(at, k) for k in before} == before


def test_legacy_link_keeps_heatmap_defaults():
    at = app_with_params(ACCEPTANCE | {"t": "25"})
    assert not at.exception
    assert at.radio(key="hm_kind").value == share.AIR_LABEL
    assert (at.number_input(key="hm_tmin").value, at.number_input(key="hm_tmax").value) == (10.0, 40.0)
    assert (at.number_input(key="hm_rhmin").value, at.number_input(key="hm_rhmax").value) == (10.0, 100.0)
    assert at.selectbox(key="hm_cs").value == "RdYlBu_r" and at.selectbox(key="hm_step").value == 0.5
    assert at.number_input(key="hm_zmax").value == 0.0
    assert at.checkbox(key="hm_target").value is True and at.checkbox(key="hm_point").value is True


@pytest.mark.parametrize("bad", [
    {"htmin": "abc", "htmax": "nan", "hrmin": "inf", "hrmax": "-5", "hz": "x"},
    {"hk": "water", "hcs": "rainbow", "hst": "0.3", "hg": "yes", "hp": "2"},
    {"htmin": "999", "hz": "1e999", "hrmin": "", "hst": "nan"},
])
def test_invalid_heatmap_link_parameters_fall_back_to_defaults_without_error(bad):
    at = app_with_params(bad)
    assert not at.exception
    assert at.radio(key="hm_kind").value == share.AIR_LABEL
    assert (at.number_input(key="hm_tmin").value, at.number_input(key="hm_tmax").value) == (10.0, 40.0)
    assert (at.number_input(key="hm_rhmin").value, at.number_input(key="hm_rhmax").value) == (10.0, 100.0)
    assert at.number_input(key="hm_zmax").value == 0.0
    assert at.selectbox(key="hm_cs").value == "RdYlBu_r" and at.selectbox(key="hm_step").value == 0.5
    assert at.checkbox(key="hm_target").value and at.checkbox(key="hm_point").value


def test_heatmap_share_defaults_match_the_widget_defaults():
    at = new_app().run()
    widgets = {"hm_tmin": at.number_input, "hm_tmax": at.number_input, "hm_rhmin": at.number_input,
               "hm_rhmax": at.number_input, "hm_zmax": at.number_input, "hm_cs": at.selectbox,
               "hm_step": at.selectbox, "hm_target": at.checkbox, "hm_point": at.checkbox}
    for key, default in share.HEATMAP_DEFAULTS.items():
        assert widgets[key](key=key).value == default, key
    assert at.radio(key="hm_kind").value == share.AIR_LABEL
    # a fresh session already exposes the complete heatmap parameter set in the URL
    assert {"hk", "htmin", "htmax", "hrmin", "hrmax", "hz", "hcs", "hst", "hg", "hp"} <= set(at.query_params)


@pytest.mark.parametrize("partial", [{"htmin": "15"}, {"hz": "2.5"}, {"hcs": "Plasma", "hg": "0"}, {"hk": "leaf"}])
def test_partial_heatmap_link_does_not_error_and_keeps_other_defaults(partial):
    at = app_with_params(partial)
    assert not at.exception
    assert at.number_input(key="hm_tmax").value == 40.0 and at.number_input(key="hm_rhmin").value == 10.0
    assert {k: qp(at, k) for k in partial} == {k: v for k, v in partial.items()}   # URL keeps the saved values
