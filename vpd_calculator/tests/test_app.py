"""Streamlit AppTest interaction tests (no browser). Widgets are addressed by stable keys."""

import json
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


LIVE_KEYS = ("t_air", "rh", "target_vpd", "calc_offset", "calc_leaf_meas",
             "dn_lo_day", "dn_hi_day", "dn_lo_night", "dn_hi_night")


def set_num(at, key, value):
    """Set a number input. The Calculator inputs live in a browser component, so their committed value
    (what the component sends on release) is simulated by setting the canonical session value."""
    if key in LIVE_KEYS:
        at.session_state[key] = value
        at.run()
    else:
        at.number_input(key=f"{key}__num").set_value(value).run()


def live(at):
    """Data sent to the Calculator's live component: mode, target and inputs."""
    return json.loads(at.get("bidi_component")[0].proto.json)


def live_values(at):
    return {f["key"]: f["value"] for f in live(at)["inputs"]}


def tables(at):
    return {tuple(df.value.columns): df.value for df in at.dataframe}


# ---- tabs, defaults and modes -------------------------------------------------------------
def test_default_run_has_no_exceptions_and_known_values():
    at = new_app().run()
    assert not at.exception
    assert at.radio(key="mode").value == share.MODE_A
    assert live_values(at) == {"rh": 60.0, "t_air": 22.0, "calc_offset": -1.0}      # fresh default offset
    assert live(at)["target"] == {"lo": 0.7, "hi": 1.3, "kind": "leaf", "period": "Day"}
    assert at.selectbox(key="range_preset__w").value == presets.DEFAULT_PRESET


def test_exactly_four_tabs():
    at = new_app().run()
    assert [t.label for t in at.tabs] == ["Calculator", "Acceptable range", "VPD Heatmap",
                                          "Methods & References"]


def test_switch_to_rh_mode_transfers_the_current_canopy_vpd():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert not at.exception and live(at)["mode"] == "b"
    assert at.session_state["target_vpd"] == vpd.calculate_vpd(22.0, 60.0, -1.0).vpd_leaf       # full precision
    assert list(live_values(at)) == ["target_vpd", "t_air", "calc_offset"]                         # input order


def test_temperature_preserved_across_modes():
    at = new_app().run()
    set_num(at, "t_air", 30.5)
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="mode").set_value(share.MODE_A).run()
    assert at.session_state["t_air"] == 30.5
    assert live(at)["mode"] == "a" and live_values(at)["t_air"] == 30.5


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
    assert live_values(at) == {"rh": 40.5, "t_air": 25.0, "calc_offset": -1.0}


def test_edit_target_vpd_reverse():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 0.8)
    assert live_values(at)["target_vpd"] == 0.8


# ---- air vs leaf and leaf offset ---------------------------------------------------------
def test_calculator_has_only_offset_and_measured_leaf_inputs():
    at = new_app().run()
    calc = at.tabs[0]
    assert [w.key for w in calc.selectbox] == []                          # no offset scenario / growth-stage selectors
    assert at.radio(key="calc_leaf_method").value == share.OFFSET_METHOD
    set_num(at, "calc_offset", -2.0)
    assert live_values(at)["calc_offset"] == -2.0 and live(at)["leafMethod"] == "offset"
    at.radio(key="calc_leaf_method").set_value(share.MEASURED_METHOD).run()
    set_num(at, "calc_leaf_meas", 20.0)
    assert not at.exception
    assert live(at)["leafMethod"] == "measured" and live_values(at)["calc_leaf_meas"] == 20.0
    assert "calc_offset" not in live_values(at)


def test_leaf_temperature_guidance_replaces_scenario_text():
    at = new_app().run()
    expander = next(e for e in at.expander if e.label == "Leaf-temperature guidance")
    assert expander.proto.expanded is False
    text = " ".join(m.value for m in expander.markdown) + " ".join(c.value for c in expander.caption)
    text = " ".join(text.split())
    for needle in ("1–3 °C below air", "10–15 °C warmer in direct sun", "Figure 4](https://doi.org/10.1371/journal.pone.0138930.g004)",
                   "| 0 | Night | −3 | −3 |", "| 250 | Overcast / shaded | −3 | −2 |", "| 500 | Cloudy | −2 | −1 |",
                   "| 750 | Partly cloudy | −1 | 0 |", "| 1,000 | Direct sunlight | +0 | +1 |",
                   "**measure representative leaves with an infrared thermometer**"):
        assert needle in text, needle
    everything = " ".join(m.value for m in at.tabs[0].markdown) + " ".join(c.value for c in at.tabs[0].caption)
    assert "illustrative scenarios, not universal correction factors" not in everything
    assert not any(e.label.startswith(("Air VPD vs leaf VPD", "About leaf-offset")) for e in at.expander)
    (image,) = at.get("image")
    assert image.proto.imgs[0].caption.startswith("Fig. 4. Calculated effects of environmental conditions")


def test_reverse_mode_has_no_target_basis_selector_and_is_canopy_only():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert not any(r.label == "Target VPD refers to" for r in at.radio) and "targetKind" not in live(at)
    set_num(at, "calc_offset", -2.0)
    assert live_values(at)["calc_offset"] == -2.0


def test_older_link_with_air_target_selection_is_still_canopy_only():
    at = app_with_params({"m": "b", "k": "air"})
    assert not at.exception and "targetKind" not in live(at) and "target_kind" not in at.session_state


def test_mode_switch_transfers_values_at_full_precision_without_drift():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 1.2)
    at.radio(key="mode").set_value(share.MODE_A).run()
    rh = at.session_state["rh"]
    assert rh == pytest.approx(vpd.rh_for_leaf_vpd(22.0, 1.2, 21.0), abs=1e-12)
    assert vpd.calculate_vpd(22.0, rh, -1.0).vpd_leaf == pytest.approx(1.2, abs=1e-12)
    set_num(at, "rh", 88.0)
    at.radio(key="mode").set_value(share.MODE_B).run()
    tv = at.session_state["target_vpd"]
    assert vpd.calculate_required_rh(22.0, tv, vpd.LEAF, -1.0).rh == pytest.approx(88.0, abs=1e-9)
    for _ in range(3):                                                          # repeated switching does not drift
        at.radio(key="mode").set_value(share.MODE_A).run()
        at.radio(key="mode").set_value(share.MODE_B).run()
    assert at.session_state["target_vpd"] == pytest.approx(tv, abs=1e-12) and at.session_state["rh"] == pytest.approx(88.0, abs=1e-9)
    at.radio(key="calc_leaf_method").set_value(share.MEASURED_METHOD).run()
    set_num(at, "calc_leaf_meas", 25.0)
    set_num(at, "t_air", 27.5)
    at.radio(key="mode").set_value(share.MODE_A).run()
    assert set(live_values(at)) == {"rh", "t_air", "calc_leaf_meas"} and at.session_state["calc_offset"] == -1.0
    assert at.session_state["rh"] == pytest.approx(vpd.calculate_required_rh(27.5, tv, vpd.LEAF, 0.0, 25.0).rh, abs=1e-9)


# ---- acceptable range replaces the Calculator's own target range -----------------------------------
def test_calculator_has_no_separate_target_range_controls():
    at = new_app().run()
    assert "Target VPD range" not in [s.value for s in at.subheader]
    keys = {w.key for w in at.tabs[0].number_input} | {w.key for w in at.tabs[0].selectbox} | {w.key for w in at.tabs[0].radio}
    assert not keys & {"vpd_lo__num", "vpd_hi__num", "vpd_preset", "interval_kind", "calc_offset_preset"}
    assert "Acceptable range" in [s.value for s in at.subheader]


# ---- day and night sections --------------------------------------------------------------------
# ---- validation messages ------------------------------------------------------------------------
# ---- share links and query parameters --------------------------------------------------------------
def test_share_link_restores_settings():
    at = new_app()
    at.query_params["t"] = "30"
    at.query_params["rh"] = "50"
    at.run()
    assert not at.exception
    assert at.session_state["t_air"] == 30.0
    assert live_values(at)["t_air"] == 30.0 and live_values(at)["rh"] == 50.0


def test_legacy_share_url_still_works_and_selects_matching_preset():
    at = new_app()
    for k, v in {"m": "b", "t": "25", "rh": "60", "tv": "1.1", "k": "leaf", "lo": "1.2", "hi": "1.5",
                 "ik": "leaf", "off": "-2"}.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception
    s = at.session_state
    assert (s["t_air"], s["target_vpd"], s["interval_kind"], s["calc_offset"]) == (
        25.0, 1.1, share.LEAF_LABEL, -2.0)
    assert (s["vpd_lo"], s["vpd_hi"]) == (1.2, 1.5)                  # legacy settings still load (no longer used)
    assert live(at)["mode"] == "b"
    assert live_values(at) == {"t_air": 25.0, "target_vpd": 1.1, "calc_offset": -2.0}


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
    at.radio(key="hm_kind").set_value("Canopy VPD").run()
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
    at.selectbox(key="range_preset__w").set_value(presets.PRESET_NAMES[5]).run()
    at.checkbox(key="val_johnston").set_value(True).run()
    assert not at.exception


# ---- single-value (point) targets: equal lower and upper limits -----------------------------------
def texts(elements):
    return [e.value for e in elements]


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


ACCEPTANCE = {"dlo": "1.0", "dhi": "1.0", "nlo": "0.6", "nhi": "1.0", "rp": "custom"}
OBSOLETE = {"dt": "33", "doff": "-2", "nt": "12", "noff": "1", "dp": "veg", "np": "seed"}      # old per-period parameters


def app_with_params(params):
    at = new_app()
    for k, v in params.items():
        at.query_params[k] = v
    return at.run()


def qp(at, key):
    v = at.query_params[key]
    return v[0] if isinstance(v, list) else v


def test_calculator_has_no_csv_json_or_share_section():
    at = new_app().run()
    calc = at.tabs[0]
    assert not any(e.label == "Share these settings" for e in at.expander)
    assert not calc.get("download_button") and not calc.get("file_uploader")
    assert not any(b.key == "setup_apply" for b in calc.button)
    labels = [getattr(b.proto, "label", "") for b in at.get("download_button")]
    assert not any("settings and results" in x or "setup (JSON)" in x for x in labels)
    assert "Download grid (CSV)" in labels and not any("comparison" in x.lower() for x in labels)


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
    assert "Canopy VPD" in layout["title"]["text"]
    heat = spec["data"][0]
    assert heat["zmax"] == 3.5 and heat["colorbar"]["title"]["text"] == "Canopy VPD (kPa)"
    assert heat["colorscale"][0][1] == "#440154"                                   # Viridis
    # no target layers or point; the extra contour is the leaf VPD = 0 line (-2 degC offset crosses the chart)
    assert [d["type"] for d in spec["data"]] == ["heatmap", "contour", "contour"]
    assert spec["data"][2]["name"] == "Leaf saturation: VPD = 0 kPa"
    assert spec["data"][1]["contours"]["size"] == 0.2
    # calculator and day/night settings are restored as well
    s = at.session_state
    assert (s["t_air"], s["rh"], s["vpd_lo"], s["vpd_hi"], s["calc_offset"]) == (25.0, 40.0, 0.9, 1.3, -2.0)
    assert s["interval_kind"] == share.LEAF_LABEL
    assert (s["dn_lo_day"], s["dn_hi_day"], s["range_preset"]) == (1.0, 1.0, presets.CUSTOM)
    assert (s["dn_lo_night"], s["dn_hi_night"]) == (0.6, 1.0)


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
    set_num(at, "dn_lo_night", 0.55)
    link = {k: qp(at, k) for k in at.query_params}
    assert {"hk", "htmin", "htmax", "hrmin", "hrmax", "hz", "hcs", "hst", "hg", "hp"} <= set(link)
    fresh = app_with_params(link)
    assert not fresh.exception
    for key in ("hm_kind", "hm_tmin", "hm_tmax", "hm_rhmin", "hm_rhmax", "hm_cs", "hm_step", "hm_zmax",
                "hm_target", "hm_point", "t_air", "dn_lo_night"):
        assert fresh.session_state[key] == at.session_state[key], key
    assert heatmap_spec(fresh)["layout"] == heatmap_spec(at)["layout"]


def test_editing_heatmap_settings_updates_url_without_touching_other_settings():
    at = new_app().run()
    before = {k: qp(at, k) for k in ("t", "rh", "nlo", "dlo", "nhi")}
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


# ---- heatmap leaf-temperature assumption caption -----------------------------------------------------
def leaf_note(at):
    return [c.value for c in at.tabs[2].caption if "constant leaf–air offset" in c.value]


def test_heatmap_leaf_assumption_caption_for_leaf_colours_and_leaf_targets():
    at = app_with_params({"hk": "leaf", "off": "-2"})                       # leaf heatmap, offset input
    (note,) = leaf_note(at)
    assert "-2.0 °C" in note and "air temperature − 2.0 °C throughout this chart" in note and "derived" not in note
    at = app_with_params({"hk": "air", "hg": "1", "off": "-2"})   # air heatmap, canopy target shown
    assert len(leaf_note(at)) == 1
    # measured leaf temperature: 22 degC air, 20 degC leaf -> -2 degC offset, explained
    at = app_with_params({"hk": "air", "t": "22", "lm": "20"})
    (note,) = leaf_note(at)
    assert "-2.0 °C" in note and "air temperature − 2.0 °C throughout this chart" in note
    assert "30 °C" not in note
    assert "measured leaf temperature (20.0 °C)" in note and "air temperature (22.0 °C)" in note


def test_heatmap_condensation_note_only_when_the_zero_line_is_drawn():
    def notes(params):
        return [c.value for c in new_app_with(params).tabs[2].caption if "possible condensation" in c.value]
    new_app_with = app_with_params
    assert len(notes({"hk": "leaf", "off": "-2"})) == 1          # zero boundary crosses the chart
    assert notes({"hk": "leaf", "off": "0"}) == []               # VPD = 0 only at the 100 % RH edge
    assert notes({"hk": "air", "off": "-2"}) == []               # air heatmaps are unchanged


def test_heatmap_leaf_assumption_caption_absent_without_leaf_use():
    assert leaf_note(app_with_params({"hk": "air", "hg": "0", "off": "-2"})) == []  # target hidden
    assert leaf_note(app_with_params({"hk": "air", "dlo": "1.5", "dhi": "0.5"})) == []  # invalid range


# ---- heatmap figure downloads (PNG, PDF, SVG) and their cache -----------------------------------------
def heatmap_downloads(at):
    return {b.proto.label for b in at.get("download_button")} & {"Download PNG", "Download PDF", "Download SVG"}


def capture_heatmap_downloads(monkeypatch):
    from streamlit.delta_generator import DeltaGenerator
    calls = {}
    original = DeltaGenerator.download_button          # the heatmap buttons are created on a column

    def spy(self, label, data, file_name=None, mime=None, *args, **kwargs):
        if label in ("Download PNG", "Download PDF", "Download SVG"):
            calls[label] = {"data": data, "file_name": file_name, "mime": mime}
        return original(self, label, data, file_name, mime, *args, **kwargs)

    monkeypatch.setattr(DeltaGenerator, "download_button", spy)
    return calls


def test_heatmap_svg_download_is_offered_with_png_and_pdf_and_follows_the_settings(monkeypatch):
    calls = capture_heatmap_downloads(monkeypatch)
    at = new_app().run()
    assert heatmap_downloads(at) == set()                                   # nothing before preparing
    at.checkbox(key="hm_target").set_value(False).run()                     # the (canopy) target overlay is not drawn
    at.button(key="png_prepare").click().run()
    assert not at.exception and heatmap_downloads(at) == {"Download PNG", "Download PDF", "Download SVG"}
    assert (calls["Download SVG"]["file_name"], calls["Download SVG"]["mime"]) == ("vpd_heatmap.svg", "image/svg+xml")
    svg = calls["Download SVG"]["data"]
    assert svg[:5] == b"<?xml" and b"<svg" in svg and b"<image" in svg      # raster colour layer
    assert b"Air VPD" in svg and b"Canopy VPD" not in svg
    assert calls["Download PNG"]["data"][:8] == b"\x89PNG\r\n\x1a\n" and calls["Download PDF"]["data"][:5] == b"%PDF-"
    at.run()                                                                # unchanged settings keep the downloads
    assert heatmap_downloads(at) == {"Download PNG", "Download PDF", "Download SVG"}
    at.radio(key="hm_kind").set_value(share.LEAF_LABEL).run()               # changed settings hide the old ones
    assert heatmap_downloads(at) == set()
    at.button(key="png_prepare").click().run()
    assert b"Canopy VPD" in calls["Download SVG"]["data"] and heatmap_downloads(at)


def test_older_cached_heatmap_export_without_svg_is_ignored_without_error():
    at = new_app().run()
    at.button(key="png_prepare").click().run()
    sig, png, pdf, _svg = at.session_state["png"]
    at.session_state["png"] = (sig, png, pdf)                               # entry written by an older version
    at.run()
    assert not at.exception and heatmap_downloads(at) == set()
    at.button(key="png_prepare").click().run()                              # preparing again refreshes it
    assert len(at.session_state["png"]) == 4 and "Download SVG" in heatmap_downloads(at)


# ---- acceptable range: presets, shared conditions, reset ----------------------------------------------------
def panel_payloads(at):
    return [p for p in controls_and_panels(at) if not p.get("controlsOnly")]


def controls_and_panels(at):
    return [json.loads(c.proto.json) for c in at.get("bidi_component") if c.proto.component_name == "vpd_live_calculator"]


def limits(at):
    s = at.session_state
    return (s["dn_lo_day"], s["dn_hi_day"]), (s["dn_lo_night"], s["dn_hi_night"])


def test_range_tab_only_edits_ranges_and_has_one_preset_selector():
    at = new_app().run()
    tab = at.tabs[1]
    assert [w.key for w in tab.selectbox] == ["range_preset__w"] and tab.selectbox[0].label == "Range preset"
    assert tab.selectbox[0].options == [presets.display_label(n) for n in presets.PRESET_NAMES]
    assert tab.selectbox[0].value == presets.DEFAULT_PRESET
    ctl = [p for p in controls_and_panels(at) if p.get("controlsOnly")]
    assert [[f["key"] for f in p["inputs"]] for p in ctl] == [["dn_lo_day", "dn_hi_day"], ["dn_lo_night", "dn_hi_night"]]
    assert not tab.number_input and all(f["step"] == 0.05 and f["dec"] == 2 for p in ctl for f in p["inputs"])
    assert not tab.metric and not tab.info
    assert limits(at) == ((0.7, 1.3), (0.7, 1.3))
    assert "Uses the current Calculator conditions." in [c.value for c in tab.caption]
    assert not tab.radio and len(panel_payloads(at)) == 3
    assert any(e.label == "About these ranges" for e in at.expander) and any(e.label == "About night-time VPD" for e in at.expander)


def test_preset_sets_both_periods_manual_edit_changes_one_and_new_preset_resets_both():
    at = new_app().run()
    name = presets.PRESET_NAMES[4]                                           # ASHRAE leafy greens, 0.65-0.90
    at.selectbox(key="range_preset__w").set_value(name).run()
    assert limits(at) == ((0.65, 0.9), (0.65, 0.9)) and at.session_state["range_preset"] == name
    set_num(at, "dn_hi_night", 1.1)
    assert limits(at) == ((0.65, 0.9), (0.65, 1.1)) and at.selectbox(key="range_preset__w").value == presets.CUSTOM
    at.run()                                                                  # reruns do not re-apply a preset
    assert limits(at) == ((0.65, 0.9), (0.65, 1.1))
    at.selectbox(key="range_preset__w").set_value(presets.CUSTOM).run()      # Custom keeps the bounds
    assert limits(at) == ((0.65, 0.9), (0.65, 1.1))
    at.selectbox(key="range_preset__w").set_value(presets.PRESET_NAMES[7]).run()
    assert limits(at) == ((0.8, 1.2), (0.8, 1.2))


def test_changing_bounds_does_not_change_calculator_conditions_and_each_period_has_its_own_bar():
    at = new_app().run()
    before = live_values(at)
    set_num(at, "dn_lo_day", 0.9)
    set_num(at, "dn_hi_day", 0.9)                                             # equal bounds are supported
    set_num(at, "dn_hi_night", 1.1)
    assert live_values(at) == before
    cal, day, night = panel_payloads(at)
    assert [p.get("readonly") for p in (cal, day, night)] == [None, True, True]
    assert day["target"] == {"lo": 0.9, "hi": 0.9, "kind": "leaf", "period": "Day"}
    assert night["target"] == {"lo": 0.7, "hi": 1.1, "kind": "leaf", "period": "Night"}
    assert (day["title"], night["title"]) == ("Day result", "Night result")
    assert cal["inputs"] == day["inputs"] == night["inputs"] and cal["mode"] == day["mode"] == night["mode"]  # shared conditions
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert all(p["mode"] == "b" for p in panel_payloads(at))
    set_num(at, "dn_lo_night", 2.0)                                           # invalid range: no band for that period only
    assert panel_payloads(at)[2]["target"] is None and panel_payloads(at)[1]["target"] is not None


def test_range_settings_survive_reruns_and_link_round_trip():
    at = new_app().run()
    at.selectbox(key="range_preset__w").set_value(presets.PRESET_NAMES[6]).run()
    set_num(at, "dn_lo_night", 0.5)
    link = {k: qp(at, k) for k in at.query_params}
    assert link["rp"] == "custom" and link["nlo"] == "0.5" and link["dlo"] == "0.4" and not {"dt", "nt", "doff", "noff"} & set(link)
    fresh = app_with_params(link)
    assert limits(fresh) == ((0.4, 0.8), (0.5, 0.8)) and fresh.session_state["range_preset"] == presets.CUSTOM
    same = app_with_params({"dlo": "0.4", "dhi": "0.8", "nlo": "0.4", "nhi": "0.8", "rp": "bayer"})
    assert same.session_state["range_preset"] == presets.PRESET_NAMES[6]


def test_obsolete_day_night_condition_parameters_do_not_override_calculator():
    at = app_with_params(ACCEPTANCE | OBSOLETE | {"t": "25", "rh": "40", "off": "-2"})
    assert not at.exception
    assert live_values(at) == {"rh": 40.0, "t_air": 25.0, "calc_offset": -2.0} and "dn_t_day" not in at.session_state
    assert limits(at) == ((1.0, 1.0), (0.6, 1.0))
    bad = app_with_params({"dlo": "abc", "nhi": "99", "rp": "nonsense"})
    assert not bad.exception and limits(bad) == ((0.7, 1.3), (0.7, 1.3)) and bad.session_state["range_preset"] == presets.DEFAULT_PRESET


def test_reset_restores_calculator_defaults_and_keeps_ranges():
    at = new_app().run()
    at.selectbox(key="range_preset__w").set_value(presets.PRESET_NAMES[5]).run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    at.radio(key="calc_leaf_method").set_value(share.MEASURED_METHOD).run()
    set_num(at, "t_air", 31.0)
    set_num(at, "calc_leaf_meas", 27.0)
    set_num(at, "calc_offset", 0.5)
    set_num(at, "target_vpd", 2.0)
    at.radio(key="calc_period").set_value("Night").run()
    at.button(key="calc_reset").click().run()
    assert not at.exception
    assert at.radio(key="mode").value == share.MODE_A and at.radio(key="calc_leaf_method").value == share.OFFSET_METHOD
    assert live_values(at) == {"rh": 60.0, "t_air": 22.0, "calc_offset": -1.0}
    assert at.session_state["calc_leaf_meas"] == 22.0
    assert at.session_state["target_vpd"] == vpd.calculate_vpd(22.0, 60.0, -1.0).vpd_leaf
    assert limits(at) == ((1.0, 1.4), (1.0, 1.4)) and at.session_state["range_preset"] == presets.PRESET_NAMES[5]
    assert at.radio(key="calc_period").value == "Night"
    assert panel_payloads(at)[0]["epoch"] == 1 and (qp(at, "t"), qp(at, "rh"), qp(at, "off")) == ("22", "60", "-1")


def test_copy_link_reflects_latest_range_edits_and_the_url_is_not_shown():
    at = new_app().run()
    set_num(at, "dn_lo_night", 0.55)
    url = json.loads([c for c in at.get("bidi_component") if c.proto.component_name == "vpd_copy_link"][0].proto.json)["url"]
    assert url == share.share_url(at.session_state) and "nlo=0.55" in url
    assert "Share your current settings." in [c.value for c in at.tabs[1].caption]
    assert not any("?" in x.value and "http" in x.value for x in at.code)


def test_preset_limits_stay_fixed_canopy_targets_while_temperatures_change():
    at = new_app().run()
    at.selectbox(key="range_preset__w").set_value(presets.PRESET_NAMES[7]).run()          # strawberry 0.80-1.20 kPa
    at.radio(key="mode").set_value(share.MODE_B).run()
    set_num(at, "target_vpd", 1.0)
    for t_air, t_leaf, rh in ((22.0, 21.0, 56.2), (33.0, 32.0, 74.6)):
        set_num(at, "t_air", t_air)
        set_num(at, "calc_offset", t_leaf - t_air)
        assert live(at)["target"] == {"lo": 0.8, "hi": 1.2, "kind": "leaf", "period": "Day"}
        assert round(vpd.calculate_required_rh(t_air, 1.0, vpd.LEAF, t_leaf - t_air).rh, 1) == rh
        assert limits(at) == ((0.8, 1.2), (0.8, 1.2)) and live_values(at)["calc_offset"] == t_leaf - t_air
    captions = [c.value for c in at.tabs[1].caption]
    assert "Provisional canopy targets using an equal-temperature reference." not in captions
    assert "Source: [Yamanaka et al. (2025)](https://doi.org/10.2503/hortj.SZD-015)" in captions


def test_dropdown_labels_show_the_range_and_the_source_caption_is_one_short_link():
    at = new_app().run()
    labels = at.tabs[1].selectbox[0].options
    assert labels == ["Established plants — 0.70–1.30 kPa (Lopez 2026)", "Established plants — 0.70–1.50 kPa (Runkle 2021)",
                      "Propagation — 0.30–0.70 kPa (Lopez 2026)", "Propagation — 0.30–0.70 kPa (Runkle 2021)",
                      "Leafy greens & herbs — 0.65–0.90 kPa (ASHRAE 2023)", "Flowering & fruiting — 1.00–1.40 kPa (ASHRAE 2023)",
                      "Cucumber — 0.40–0.80 kPa (Bayer 2020)", "Strawberry — 0.80–1.20 kPa (Yamanaka 2025)", "Custom range"]
    assert "Source: [Lopez et al. (2026)](https://www.inside-grower.com/Article/?articleid=28096)" in [c.value for c in at.tabs[1].caption]
    at.selectbox(key="range_preset__w").set_value(presets.CUSTOM).run()
    assert "Edit the day and night limits below." in [c.value for c in at.tabs[1].caption]
    about = next(e for e in at.expander if e.label == "About these ranges")
    assert len(about.markdown) == 1 and about.markdown[0].value == presets.ABOUT_RANGES


def test_lopez_and_runkle_propagation_keep_their_identity_despite_identical_bounds():
    lopez, runkle = presets.PRESET_NAMES[2], presets.PRESET_NAMES[3]
    assert presets.preset_range(lopez) == presets.preset_range(runkle) == (0.3, 0.7)
    at = new_app().run()
    at.selectbox(key="range_preset__w").set_value(lopez).run()
    assert limits(at) == ((0.3, 0.7), (0.3, 0.7)) and at.session_state["range_preset"] == lopez
    at.run()
    assert at.session_state["range_preset"] == lopez and qp(at, "rp") == "lopez-prop"
    fresh = app_with_params({k: qp(at, k) for k in at.query_params})
    assert fresh.session_state["range_preset"] == lopez and fresh.selectbox(key="range_preset__w").value == lopez
    at.selectbox(key="range_preset__w").set_value(runkle).run()
    assert at.session_state["range_preset"] == runkle and qp(at, "rp") == "runkle-low"
    assert app_with_params({"dlo": "0.3", "dhi": "0.7", "nlo": "0.3", "nhi": "0.7", "rp": "runkle-low"}).session_state["range_preset"] == runkle


def test_reverse_panel_data_and_shared_control_implementation():
    at = new_app().run()
    at.radio(key="mode").set_value(share.MODE_B).run()
    assert [p["mode"] for p in panel_payloads(at)] == ["b", "b", "b"]            # calculator, Day panel, Night panel
    assert [p["controlsOnly"] for p in controls_and_panels(at) if p.get("controlsOnly")] == [True, True]
