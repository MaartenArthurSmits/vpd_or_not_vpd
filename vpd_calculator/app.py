"""VPD Calculator - Streamlit app.  Run with:  streamlit run app.py"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import streamlit as st

import citation
import live_calculator
import mpl_export
import plots
import presets
import rscript
import share
import treatments
import validation
import vpd


def _refresh_helper_modules():
    """Reload helper modules whose file changed.

    Streamlit Cloud re-runs app.py after a push but keeps already-imported helper modules in
    memory, which can leave a new app.py talking to an old module.
    """
    for name in ("vpd", "live_calculator", "share", "presets", "citation", "validation", "plots", "mpl_export", "rscript", "treatments"):
        mod = importlib.import_module(name)
        stamp = Path(mod.__file__).stat().st_mtime_ns
        if getattr(mod, "_loaded_stamp", None) != stamp:
            importlib.reload(mod)
            mod._loaded_stamp = stamp


_refresh_helper_modules()

st.set_page_config(page_title="VPD Calculator", page_icon="🌿", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 2.3rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Session state: canonical values live in plain keys (never widget keys), so
# they survive mode switches and number/slider syncing cannot conflict.
# Interface values are shown with one decimal; full precision is kept internally.
# --------------------------------------------------------------------------
DEFAULTS = {
    "t_air": 22.0, "rh": 60.0, "target_vpd": 1.0,
    "calc_offset": -1.0, "calc_leaf_meas": 22.0,
    "vpd_lo": 0.8, "vpd_hi": 1.2,            # legacy: kept so old links/setups load; the Calculator no longer uses them
    "dn_t_day": 22.0, "dn_t_night": 17.0,
    "dn_off_day": 0.0, "dn_off_night": 0.0,
    "dn_lo_day": 0.8, "dn_hi_day": 1.2, "dn_lo_night": 0.8, "dn_hi_night": 1.2,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)



def derive_preset_state():
    """Preset selectors follow the (already restored) numerical settings; saved identities are kept."""
    for _p in ("day", "night"):
        st.session_state[f"dn_preset_{_p}"] = presets.resolve_stage(
            st.session_state.get(f"dn_preset_{_p}"),          # saved identity from the link/setup, if any
            st.session_state[f"dn_lo_{_p}"], st.session_state[f"dn_hi_{_p}"], _p)
        st.session_state[f"dn_offset_preset_{_p}"] = presets.match_offset_preset(st.session_state[f"dn_off_{_p}"])


# Settings from a shared link are applied once, at the start of the session.
if "_share_loaded" not in st.session_state:
    st.session_state.update(share.parse_params(st.query_params.to_dict()))
    derive_preset_state()
    st.session_state["_share_loaded"] = True


def linked(label, key, lo, hi, step, fmt="%.1f", num_min=None, num_max=None, help=None, after=None):
    """Number input + slider bound to one canonical value (`key`)."""
    num, sld = f"{key}__num", f"{key}__sld"
    val = float(st.session_state[key])
    st.session_state[num] = val
    st.session_state[sld] = min(max(val, lo), hi)

    def from_num():
        st.session_state[key] = float(st.session_state[num])
        if after:
            after()

    def from_sld():
        st.session_state[key] = float(st.session_state[sld])
        if after:
            after()

    st.number_input(label, min_value=lo if num_min is None else num_min,
                    max_value=hi if num_max is None else num_max,
                    step=step, format=fmt, key=num, on_change=from_num, help=help)
    st.slider(label, float(lo), float(hi), step=step, format=fmt, key=sld, on_change=from_sld,
              label_visibility="collapsed")
    return float(st.session_state[key])


def offset_widget(label, key, preset_key):
    """Leaf-offset preset selector plus a free (custom) numeric input."""
    def pick():
        v = presets.offset_from_label(st.session_state[preset_key])
        if v is not None:
            st.session_state[key] = v

    def edited():
        st.session_state[preset_key] = presets.match_offset_preset(st.session_state[key])

    st.session_state.setdefault(preset_key, presets.match_offset_preset(st.session_state[key]))
    st.selectbox("Leaf offset scenario", presets.LEAF_OFFSET_NAMES, key=preset_key, on_change=pick,
                 help="Illustrative scenarios, not universal correction factors.")
    return linked(label, key, -10.0, 10.0, 0.1, after=edited,
                  help="Leaf temperature minus air temperature.")


FIG4_PATH = Path(__file__).parent / "assets" / "nelson_bugbee_2015_fig4.png"
FIG4_URL = "https://doi.org/10.1371/journal.pone.0138930.g004"
LEAF_GUIDANCE = f"""
Most grow-equipment suppliers suggest using leaf temperatures 1–3 °C below air temperature, but actual differences
vary considerably: leaves have been measured 1–3 °C cooler in shade and 10–15 °C warmer in direct sun
([Butler, 1977](https://natuurtijdschriften.nl/pub/540166)).
[Nelson and Bugbee’s (2015)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138930) illustrates
how light intensity, airflow, humidity, leaf size, and stomatal conductance affect this difference.

It is recommended to **measure representative leaves with an infrared thermometer** whenever possible; otherwise,
use the following estimates.
"""
LEAF_TABLE = """
**Estimated leaf-temperature offsets** (°C; leaf minus air):

| PPFD (µmol m⁻² s⁻¹) | Natural-light indicator | Sunlight | Artificial lighting |
| ---: | --- | ---: | ---: |
| 0 | Night | −3 | −3 |
| 250 | Overcast / shaded | −3 | −2 |
| 500 | Cloudy | −2 | −1 |
| 750 | Partly cloudy | −1 | 0 |
| 1,000 | Direct sunlight | +0 | +1 |
"""
LEAF_TABLE_CAPTION = (
    f"Estimates informed by [Nelson and Bugbee (2015), Figure 4]({FIG4_URL}). The reference figure assumes 25 °C air, "
    "50% RH, 1 m/s airflow, 5 cm leaf width, and stomatal conductance of 0.4 mol m⁻² s⁻¹.")
EQ_SATURATION = r"e_s(T)=0.6108\exp\left(\frac{17.27T}{T+237.3}\right)"
EQ_FORWARD = r"VPD_{\mathrm{leaf}}=e_s(T_{\mathrm{leaf}})-e_s(T_{\mathrm{air}})\frac{RH}{100}"
EQ_REVERSE_LEAF = r"RH=100\frac{e_s(T_{\mathrm{leaf}})-VPD_{\mathrm{target}}}{e_s(T_{\mathrm{air}})}"
EQ_CAPTION = ("Temperature in °C; vapour pressure and VPD in kPa; RH in %. Saturation pressure: "
              "[FAO-56, Eq. 11](https://www.fao.org/4/x0490e/x0490e07.htm).")
FIG4_CREDIT = (f"Figure: Nelson & Bugbee (2015), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), "
               f"original at {FIG4_URL}. Shown unmodified.")


def kind_from_label(label):
    return vpd.AIR if label.startswith("Air") else vpd.LEAF


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


tab_calc, tab_daynight, tab_compare, tab_heat, tab_methods = st.tabs(
    ["Calculator", "Acceptable range", "Compare treatments", "VPD Heatmap", "Methods & References"])

# ==========================================================================
# Compare treatments (rendered before the Calculator tab so the setup download can read the current rows)
# ==========================================================================
with tab_compare:
    st.subheader("Compare treatments")
    st.caption("Edit the table to compare conditions side by side: add rows at the bottom, delete rows with the "
               "row selector. Leaf temperature = air temperature + offset. Rows with missing or out-of-range "
               "values are flagged and not calculated. This table is independent of the other tabs.")
    st.session_state.setdefault("cmp_base", treatments.EXAMPLES.copy())      # unchanged base; edits live in the widget
    edited = st.data_editor(
        st.session_state["cmp_base"], num_rows="dynamic", hide_index=True, key="cmp_editor", width="stretch",
        column_config={
            treatments.NAME: st.column_config.TextColumn(treatments.NAME, required=False),
            treatments.T_AIR: st.column_config.NumberColumn(treatments.T_AIR, format="%.1f", step=0.1),
            treatments.RH: st.column_config.NumberColumn(treatments.RH, format="%.1f", step=0.1),
            treatments.OFFSET: st.column_config.NumberColumn(treatments.OFFSET, format="%.1f", step=0.1),
        })
    compared = treatments.evaluate(edited)
    st.markdown("**Results**")
    st.dataframe(compared, hide_index=True, width="stretch", key="cmp_results",
                 column_config={c: st.column_config.NumberColumn(c, format="%.1f")
                                for c in (treatments.T_AIR, treatments.RH, treatments.OFFSET, *treatments.RESULTS)})
    flagged = compared[compared[treatments.STATUS] != treatments.OK]
    for _, row in flagged.iterrows():
        (st.warning if row[treatments.STATUS] == treatments.CONDENSATION else st.error)(
            f"{row[treatments.NAME] or 'Unnamed row'}: {row[treatments.STATUS]}")
    st.download_button("Download comparison (CSV)", treatments.to_csv(compared), "vpd_treatment_comparison.csv",
                       "text/csv", key="dl_compare_csv")
    st.caption("The table shows one decimal; the CSV keeps full calculation precision.")


# ==========================================================================
# Calculator
# ==========================================================================
with tab_calc:
    st.title("Vapour Pressure Deficit calculator")
    def sync_modes():
        """Mode switch: carry the current result over so both modes describe the same conditions (full precision)."""
        s = st.session_state
        s.pop("_sync_note", None)
        meas_in = s["calc_leaf_method"] == share.MEASURED_METHOD
        off_ = s["calc_leaf_meas"] - s["t_air"] if meas_in else s["calc_offset"]
        meas_ = s["calc_leaf_meas"] if meas_in else None
        if s["mode"] == share.MODE_B:                                     # VPD -> RH: current canopy VPD becomes the target
            v = vpd.calculate_vpd(s["t_air"], s["rh"], off_, meas_).vpd_leaf
            if -5.0 <= v <= 10.0:
                s["target_vpd"] = v
            else:
                s["_sync_note"] = "The calculated canopy VPD is outside the target-VPD input range, so it was not transferred."
        else:                                                              # RH -> VPD: current canopy RH becomes the RH input
            res = vpd.calculate_required_rh(s["t_air"], s["target_vpd"], vpd.LEAF, off_, meas_)
            if res.attainable:
                s["rh"] = min(max(res.rh, 0.0), 100.0)                    # only float-tolerance clipping
            else:
                s["_sync_note"] = "The calculated canopy RH is not attainable, so it was not transferred to the RH input."

    mode = st.radio("Calculation mode", [share.MODE_A, share.MODE_B], key="mode", horizontal=True,
                    on_change=sync_modes)
    if st.session_state.get("_sync_note"):
        st.info(st.session_state["_sync_note"])
    mode_a = mode == share.MODE_A

    o1, o3 = st.columns(2, gap="large")
    with o1:
        leaf_method = st.radio("Leaf temperature input", [share.OFFSET_METHOD, share.MEASURED_METHOD],
                               key="calc_leaf_method", horizontal=True)
    with o3:
        period = st.radio("Compare with Acceptable range", ["Day", "Night"], key="calc_period", horizontal=True)

    # The acceptable range of the chosen period (edited in the Acceptable range tab).
    p = period.lower()
    lo, hi = st.session_state[f"dn_lo_{p}"], st.session_state[f"dn_hi_{p}"]
    ikind = kind_from_label(st.session_state.get(f"dn_kind_{p}", share.AIR_LABEL))
    interval_ok = lo <= hi

    measured_in = leaf_method == share.MEASURED_METHOD
    live_inputs = []
    if mode_a:
        live_inputs.append(dict(key="rh", label="Relative humidity (%)", min=0.0, max=100.0, numMin=0.0, numMax=100.0, dec=1))
    else:
        live_inputs.append(dict(key="target_vpd", label="Target VPD (kPa)", min=0.0, max=5.0, numMin=-5.0, numMax=10.0, dec=2))
    live_inputs.append(dict(key="t_air", label="Air temperature (°C)", min=0.0, max=45.0, numMin=-10.0, numMax=60.0, dec=1))
    if measured_in:
        live_inputs.append(dict(key="calc_leaf_meas", label="Measured leaf temperature (°C)", min=-5.0, max=50.0,
                                numMin=-5.0, numMax=50.0, dec=1))
    else:
        live_inputs.append(dict(key="calc_offset", label="Leaf temperature offset (°C, leaf minus air)", min=-10.0,
                                max=10.0, numMin=-10.0, numMax=10.0, dec=1))
    for f in live_inputs:
        f.update(step=0.1, value=float(st.session_state[f["key"]]))
    live_bounds = {f["key"]: (f["numMin"], f["numMax"]) for f in live_inputs}

    def commit_live_values():
        """Store the values committed in the live component (release / Enter) as the canonical settings."""
        committed = (st.session_state.get("calc_live") or {}).get("values") or {}
        for key, value in committed.items():
            if key in live_bounds and live_bounds[key][0] <= float(value) <= live_bounds[key][1]:
                st.session_state[key] = float(value)

    live_calculator.live_calculator(
        {"mode": "a" if mode_a else "b", "leafMethod": "measured" if measured_in else "offset",
         "target": {"lo": lo, "hi": hi, "kind": ikind, "period": period} if interval_ok else None,
         "inputs": live_inputs},
        commit_live_values)

    # Full-precision values for exports, the heatmap and links (the panel above is drawn in the browser).
    t_air = st.session_state["t_air"]
    measured = st.session_state["calc_leaf_meas"] if measured_in else None
    offset = st.session_state["calc_leaf_meas"] - t_air if measured_in else st.session_state["calc_offset"]
    if mode_a:
        current_rh = st.session_state["rh"]
    else:
        res = vpd.calculate_required_rh(t_air, st.session_state["target_vpd"], vpd.LEAF, offset, measured)
        current_rh = min(max(res.rh, 0.0), 100.0) if res.attainable else None   # only tiny float-tolerance clipping

    es_air, es_leaf = (float(vpd.saturation_vapour_pressure(x)) for x in (t_air, offset + t_air))
    with st.expander("Calculation details"):
        d1, d2, d3 = st.columns(3)
        d1.markdown(f"Saturation vapour pressure (air)  \n**{es_air:.2f} kPa**")
        d3.markdown(f"Saturation vapour pressure (leaf)  \n**{es_leaf:.2f} kPa**")
        if mode_a or res.attainable:
            rh_used = st.session_state["rh"] if mode_a else res.rh
            d2.markdown(f"Actual vapour pressure  \n**{es_air * rh_used / 100:.2f} kPa**")
        st.latex(EQ_SATURATION)
        st.latex(EQ_FORWARD if mode_a else EQ_REVERSE_LEAF)
        st.caption(EQ_CAPTION)
        st.caption("Canopy VPD uses the representative leaf temperature; canopy RH is the surrounding air’s relative humidity.")

    with st.expander("Leaf-temperature guidance"):
        st.markdown(LEAF_GUIDANCE)
        st.markdown(LEAF_TABLE)
        st.caption(LEAF_TABLE_CAPTION)
        st.image(str(FIG4_PATH), width=640, caption="Fig. 4. Calculated effects of environmental conditions on the difference "
                 "between leaf temperature and air temperature under four radiation scenarios.")
        st.caption(FIG4_CREDIT)



    # Keep the address bar in sync so the current URL is always a shareable link.
    st.query_params.from_dict(share.build_params(st.session_state))

# ==========================================================================
# Day & Night
# ==========================================================================
with tab_daynight:
    # ---- Day and night ranges (stacked) ---------------------------------------
    st.subheader("Acceptable range")
    st.caption("Configure the day and night conditions independently. The required RH range is calculated "
               "at each period's own temperature and optional leaf offset. Presets are illustrative. "
               "The Calculator compares its current VPD with the Day or Night range set here.")
    live_calculator.copy_link_button(share.share_url(st.session_state))
    st.caption("Share your current settings.")

    def period_section(period: str):
        p = period.lower()

        def apply_preset():
            name = st.session_state[f"dn_preset_{p}"]
            if name in presets.GROWTH_STAGES:
                a, b = presets.stage_range(name, p)
                st.session_state[f"dn_lo_{p}"], st.session_state[f"dn_hi_{p}"] = a, b

        def range_edited():
            st.session_state[f"dn_preset_{p}"] = presets.match_stage(
                st.session_state[f"dn_lo_{p}"], st.session_state[f"dn_hi_{p}"], p)

        st.session_state.setdefault(f"dn_preset_{p}", presets.match_stage(
            st.session_state[f"dn_lo_{p}"], st.session_state[f"dn_hi_{p}"], p))
        with st.container(border=True):
            st.markdown(f"### {period}")
            a1, a2 = st.columns(2, gap="large")
            with a1:
                t = linked(f"{period} air temperature (°C)", f"dn_t_{p}", 0.0, 45.0, 0.1,
                           num_min=-10.0, num_max=60.0)
                off = offset_widget(f"{period} leaf temperature offset (°C, optional)", f"dn_off_{p}",
                                    f"dn_offset_preset_{p}")
            with a2:
                st.selectbox(f"{period} growth-stage preset (illustrative)", presets.PRESET_NAMES,
                             key=f"dn_preset_{p}", on_change=apply_preset)
                dlo = linked(f"{period} lower limit (kPa)", f"dn_lo_{p}", 0.0, 4.0, 0.1, num_max=10.0,
                             after=range_edited)
                dhi = linked(f"{period} upper limit (kPa)", f"dn_hi_{p}", 0.0, 4.0, 0.1, num_max=10.0,
                             after=range_edited)
                dkind = kind_from_label(st.radio(f"{period} range applies to", [share.AIR_LABEL, share.LEAF_LABEL],
                                                 key=f"dn_kind_{p}", horizontal=True))
            if dlo > dhi:
                st.error(f"{period}: lower limit must not exceed the upper limit.")
                return
            d_rr = vpd.rh_range_for_vpd_range(t, dlo, dhi, dkind, off)
            d_point = vpd.is_point_target(dlo, dhi)
            if d_point:
                st.markdown(f"**{period} target {dkind} VPD: {dlo:.1f} kPa**")
            if d_rr["attainable"] and d_point:
                st.metric(f"{period} required RH for {dkind} VPD {dlo:.1f} kPa at {t:.1f} °C",
                          f"{d_rr['rh_min']:.1f} %")
            elif d_rr["attainable"]:
                st.metric(f"{period} RH range for {dkind} VPD {dlo:.1f}-{dhi:.1f} kPa at {t:.1f} °C",
                          f"{d_rr['rh_min']:.1f} - {d_rr['rh_max']:.1f} %")
                if not d_rr["fully_attainable"]:
                    st.warning(f"{period}: part of the range is unattainable (unclipped RH "
                               f"{d_rr['rh_min_raw']:.1f} to {d_rr['rh_max_raw']:.1f} %).")
            elif d_point:
                st.error(f"{period}: no RH between 0 and 100 % gives a {dkind} VPD of {dlo:.1f} kPa "
                         f"(unclipped RH {d_rr['rh_min_raw']:.1f} %).")
            else:
                st.error(f"{period}: no RH between 0 and 100 % gives a {dkind} VPD in this range "
                         f"(unclipped RH {d_rr['rh_min_raw']:.1f} to {d_rr['rh_max_raw']:.1f} %).")
            rh_c = float(vpd.condensation_rh(t, t + off))
            if off < 0:
                msg = (f"**Condensation guidance:** with the leaf {abs(off):.1f} °C cooler than the air, leaf VPD "
                       f"reaches 0 at {rh_c:.1f} % RH. Above that RH, condensation on the leaf is possible.")
                if d_rr["attainable"]:
                    msg += (f" The {'required RH' if d_point else 'top of your RH range'} ({d_rr['rh_max']:.1f} %) is "
                            f"{'above' if d_rr['rh_max'] > rh_c else 'below'} that limit.")
                (st.warning if d_rr["attainable"] and d_rr["rh_max"] > rh_c else st.info)(msg)
            else:
                st.info("**Condensation guidance:** the leaf is not cooler than the air in this scenario, so "
                        "condensation on the leaf is not expected from the offset alone. Surfaces cooler than "
                        "the air (for example glazing at night) can still condense moisture.")

    period_section("Day")
    period_section("Night")

# ==========================================================================
# Heatmap
# ==========================================================================
with tab_heat:
    st.subheader("VPD as a function of temperature and relative humidity")
    h1, h2, h3, h4 = st.columns(4)
    t_min = h1.number_input("Min temperature (°C)", value=10.0, step=1.0, format="%.1f", key="hm_tmin")
    t_max = h2.number_input("Max temperature (°C)", value=40.0, step=1.0, format="%.1f", key="hm_tmax")
    rh_min = h3.number_input("Min RH (%)", value=10.0, min_value=0.0, max_value=99.0, step=5.0,
                             format="%.1f", key="hm_rhmin")
    rh_max = h4.number_input("Max RH (%)", value=100.0, min_value=1.0, max_value=100.0, step=5.0,
                             format="%.1f", key="hm_rhmax")
    g1, g2, g3, g4 = st.columns(4)
    hm_kind_label = g1.radio("VPD type", [share.AIR_LABEL, share.LEAF_LABEL], key="hm_kind", horizontal=True)
    cscale = g2.selectbox("Colour scale", plots.COLORSCALES, key="hm_cs")
    cstep = g3.selectbox("Contour spacing (kPa)", [0.1, 0.2, 0.5, 1.0], index=2, key="hm_step")
    zmax_in = g4.number_input("Colour scale max (kPa, 0 = auto)", min_value=0.0, value=0.0, step=0.5,
                              format="%.1f", key="hm_zmax")
    o1, o2 = st.columns(2)
    show_target = o1.checkbox("Highlight acceptable range (Day or Night, as chosen in the Calculator)", value=True, key="hm_target")
    show_point = o2.checkbox("Mark selected temperature/RH", value=True, key="hm_point")
    show_treatments = st.checkbox("Show comparison treatments", value=False, key="hm_treatments",
                                  help="Markers for the valid rows of the Compare treatments tab.")
    st.caption("Comparison markers are drawn in the interactive chart, the PNG/PDF/SVG downloads and the R script "
               "(valid treatments inside the axes only).")
    hm_kind = kind_from_label(hm_kind_label)

    if t_min >= t_max or rh_min >= rh_max:
        st.error("Minimum values must be smaller than maximum values.")
    else:
        pt = (t_air, current_rh) if (show_point and current_rh is not None) else None
        tg = (lo, hi) if (show_target and interval_ok) else None
        if hm_kind == vpd.LEAF or (tg is not None and ikind == vpd.LEAF):      # leaf VPD is used by the chart
            sign = "−" if offset < 0 else "+"
            note = (f"Canopy VPD here assumes one constant leaf–air offset of {offset:+.1f} °C: leaf temperature = "
                    f"air temperature {sign} {abs(offset):.1f} °C throughout this chart.")
            if measured is not None:
                note += (f" The offset is derived from the measured leaf temperature ({measured:.1f} °C) and the "
                         f"Calculator's air temperature ({t_air:.1f} °C).")
            st.caption(note)
        markers, n_outside = ([], 0)
        if show_treatments:
            markers, n_outside = treatments.markers_in_view(compared, t_min, t_max, rh_min, rh_max)
        fig = plots.heatmap_figure(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale, cstep,
                                   zmax_in or None, pt, tg, target_kind=ikind, treatments=markers or None)
        st.plotly_chart(fig, width="stretch", config={"toImageButtonOptions": {"format": "png", "scale": 2}})
        if n_outside:
            st.caption(f"{n_outside} calculated treatment{'s are' if n_outside > 1 else ' is'} outside the "
                       "displayed axes and not shown.")
        leaf_in_chart = hm_kind == vpd.LEAF or (tg is not None and ikind == vpd.LEAF)
        if leaf_in_chart and any(abs(m["offset"] - offset) > 1e-9 for m in markers):
            st.caption(f"Marker values use each treatment's own leaf offset; the chart background uses the "
                       f"Calculator's offset ({offset:+.1f} °C), so a marker's canopy VPD can differ from the "
                       "background colour at its position.")
        if any(trace.name == vpd.ZERO_LABEL for trace in fig.data):
            st.caption("Negative canopy VPD (beyond the saturation line) indicates possible condensation.")
        if tg:
            if vpd.is_point_target(lo, hi):
                st.caption(f"Dashed contour: user-defined single-value target **{ikind} VPD** "
                           f"{lo:.1f} kPa (the {period} target from the Acceptable range tab; "
                           f"colours show {hm_kind} VPD).")
            else:
                st.caption(f"Dashed contours and light overlay: user-defined target **{ikind} VPD** range "
                           f"{lo:.1f}-{hi:.1f} kPa (the {period} target from the Acceptable range tab; "
                           f"colours show {hm_kind} VPD).")

        d1, d2, d3 = st.columns(3)
        grid = vpd.vpd_grid(t_min, t_max, rh_min, rh_max, 0.5, 1.0, offset=offset)
        d1.download_button("Download grid (CSV)", to_csv(grid), "vpd_grid.csv", "text/csv", key="dl_grid_csv")

        hm_params = dict(t_min=t_min, t_max=t_max, rh_min=rh_min, rh_max=rh_max, kind=hm_kind,
                         offset=offset, colorscale=cscale, contour_step=cstep, z_max=zmax_in or None,
                         point=pt, target=tg, target_kind=ikind, treatments=markers or None)
        leaf_t = measured if measured is not None else t_air + offset
        r_code = rscript.build_r_script(
            mode_a, t_air, st.session_state["rh"], st.session_state["target_vpd"],
            vpd.LEAF, leaf_t,
            (lo, hi) if interval_ok else None, ikind, heatmap=hm_params)
        d3.download_button("Download reproducible R script", r_code.encode("utf-8"),
                           "vpd_heatmap.R", "text/plain", key="dl_rscript",
                           help="Reproduces the calculation and this heatmap with ggplot2 (PNG and PDF export).")

        marker_sig = tuple((m["name"], m["t_air"], m["rh"], m["offset"]) for m in markers)
        sig = (t_min, t_max, rh_min, rh_max, hm_kind, round(offset, 6), cscale, cstep, zmax_in, pt, tg, ikind,
               show_treatments, marker_sig)
        if d2.button("Prepare figure downloads", key="png_prepare"):
            export = mpl_export.heatmap_mpl(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale, cstep,
                                            zmax_in or None, pt, tg, target_kind=ikind,
                                            treatments=markers or None)
            st.session_state["png"] = (sig, mpl_export.to_bytes(export, "png", 300),
                                       mpl_export.to_bytes(export, "pdf"), mpl_export.to_bytes(export, "svg"))
        cached = st.session_state.get("png")
        # Only a complete entry (PNG, PDF and SVG) for the current settings is offered; older entries are ignored.
        if cached is not None and len(cached) == 4 and cached[0] == sig:
            d2.download_button("Download PNG", cached[1], "vpd_heatmap.png", "image/png", key="png_download")
            d2.download_button("Download PDF", cached[2], "vpd_heatmap.pdf", "application/pdf", key="pdf_download")
            d2.download_button("Download SVG", cached[3], "vpd_heatmap.svg", "image/svg+xml", key="svg_download")
        st.caption("PNG (300 dpi), PDF and SVG are rendered on the server with Matplotlib; no browser is needed. "
                   "The heatmap colour layer is raster; contours, labels and annotations are vector.")

# ==========================================================================
# Methods & References
# ==========================================================================
with tab_methods:
    st.header("Methods")
    st.markdown("**Saturation vapour pressure** (FAO-56, Allen et al. 1998, Eq. 11), with $T$ in °C and $e_s$ in kPa:")
    st.latex(r"e_s(T) = 0.6108\,\exp\!\left(\frac{17.27\,T}{T + 237.3}\right)")
    st.markdown("**Actual vapour pressure and deficits:**")
    st.latex(r"e_a = e_s(T_{air})\,\frac{RH}{100}")
    st.latex(r"VPD_{air} = e_s(T_{air}) - e_a \qquad VPD_{leaf} = e_s(T_{leaf}) - e_a")
    st.markdown("**Reverse calculation** (closed form, no numerical approximation):")
    st.latex(r"RH = 100\left(1 - \frac{VPD_{target}}{e_s(T_{air})}\right) \quad \text{(air VPD)}")
    st.latex(r"RH = 100\,\frac{e_s(T_{leaf}) - VPD_{target}}{e_s(T_{air})} \quad \text{(leaf VPD)}")
    st.latex(r"RH_{condensation} = 100\,\frac{e_s(T_{leaf})}{e_s(T_{air})} \quad \text{(leaf VPD} = 0\text{)}")
    st.markdown(
        """
**Assumptions and behaviour**
- The same $e_a$ (set by air temperature and RH) is used for air and leaf VPD; the leaf interior is
  assumed saturated at leaf temperature.
- Leaf temperature is either air temperature plus an offset, or a directly measured value. Offset presets
  (0, -1, -2, +1, +2 °C) are illustrative scenarios, not universal correction factors.
- Required RH outside 0-100 % is reported as unattainable, never clipped.
- Negative leaf VPD is allowed and flagged, since it indicates possible condensation on the leaf.
- The FAO-56 equation is an empirical formula in air temperature only; it does not use atmospheric pressure. Results far outside typical growth-chamber temperatures have not been checked here.
- Growth-stage VPD presets are illustrative horticultural ranges from a grower guide (Koverda, 2020). They are
  **not** scientifically validated, species-specific optima. Custom ranges are yours to define.
- The leaf-offset heatmap uses a constant offset across all air temperatures.
- Values are displayed with one decimal place for readability; calculations, validation tables and CSV
  exports keep full precision.

**Attribution.** Pulse Grow (Koverda, 2020) is the source of the illustrative growth-stage VPD ranges and the
typical leaf-offset note, and the inspiration for the interface. It is not the source of the equations; those
come from FAO-56 (Allen et al., 1998).

**References** (APA 7)
"""
    )
    st.markdown(
        """
- Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements* (FAO Irrigation and Drainage Paper No. 56). Food and Agriculture Organization of the United Nations. https://www.fao.org/4/x0490e/x0490e00.htm (Eq. 11: https://www.fao.org/4/x0490e/x0490e07.htm; Annex 2, Table 2.3: https://www.fao.org/4/x0490e/x0490e0j.htm)
- Garen, J. C., Crous, K. Y., Barton, C. V. M., Rymer, P. D., & Tjoelker, M. G. (2026). Joint dependence of leaf minimum conductance on vapor pressure deficit and temperature. *Plant Physiology, 201*(4), Article kiag575. https://doi.org/10.1093/plphys/kiag575
- Grossiord, C., Buckley, T. N., Cernusak, L. A., Novick, K. A., Poulter, B., Siegwolf, R. T. W., Sperry, J. S., & McDowell, N. G. (2020). Plant responses to rising vapor pressure deficit. *New Phytologist, 226*(6), 1550–1566. https://doi.org/10.1111/nph.16485
- Johnston, M. R., Barnes, M. L., Preisler, Y., Smith, W. K., Biederman, J. A., Scott, R. L., Williams, A. P., & Dannenberg, M. P. (2025). Effects of hot versus dry vapor pressure deficit on ecosystem carbon and water fluxes. *Journal of Geophysical Research: Biogeosciences, 130*(1), Article e2024JG008146. https://doi.org/10.1029/2024JG008146
- Koverda, P. (2020, February 12). *The ultimate vapor pressure deficit (VPD) guide*. Pulse Grow. https://pulsegrow.com/blogs/learn/vpd (illustrative growth-stage ranges, typical leaf-offset note and interface inspiration; not a source for the equations)
"""
    )

    with st.expander("How to cite this software"):
        st.caption("No DOI has been minted for this software. Cite the repository and version.")
        st.markdown("**APA 7**")
        st.code(citation.apa(), language=None)
        st.markdown("**BibTeX**")
        st.code(citation.bibtex(), language="bibtex")
        st.markdown("**IEEE**")
        st.code(citation.ieee(), language=None)
        st.caption(f"Author ORCID: {citation.ORCID}")

    with st.expander("Scientific validation", expanded=False):
        st.markdown(
            "This section compares the application's calculations with (i) saturation vapour pressures printed in a published table, "
            "(ii) benchmarks calculated from published equations and (iii) an alternative published equation. "
            "Comparisons below are **computed live** by calling the same functions the calculator uses. "
            "The automated test suite (run separately, e.g. in CI) is documented in "
            "[docs/VALIDATION.md](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/blob/main/docs/VALIDATION.md)."
        )

        st.markdown("#### A. Comparison with published research")
        st.markdown(
            """
- **Grossiord et al. (2020), Figure 2**: relationships between temperature, relative humidity, atmospheric
  vapour pressure and VPD. https://doi.org/10.1111/nph.16485
- **Johnston et al. (2025), Figure 1**: different temperature and RH combinations that give an equivalent VPD.
  https://doi.org/10.1029/2024JG008146
- **Garen et al. (2026), Figure 1a**: a psychrometric chart relating temperature, RH and VPD, with
  physically impossible combinations indicated. https://doi.org/10.1093/plphys/kiag575

These figures are not reproduced here (publisher copyright); follow the links to view them. The VPD heatmap and
the plot below are original visualisations of the same relationships. The published figures support the
expected qualitative relationships but are **not by themselves a numerical validation** of this application.
"""
        )

        st.markdown("#### B. Numerical comparison")
        st.markdown(
            """
Five kinds of evidence are kept separate:
1. **Agreement with published tabulated values**: saturation vapour pressures printed in FAO-56 Annex 2,
   Table 2.3 (first table below). Only these numbers are tabulated in a source.
2. **Agreement with calculated benchmarks**: air VPD values for five temperature/RH cases, calculated from the
   FAO-56 Eq. 11 constants and rounded to 4 d.p. They are **not** printed in FAO-56 Table 2.3. Agreement shows
   that the code evaluates the equation as intended; it is not an independent measurement or source.
3. **Comparison with an alternative published equation**: Johnston et al. (2025). The two equations are closely
   related empirical fits, so agreement shows consistency between formulations, not measurement accuracy.
   The Johnston benchmark values are calculated from that equation (Eq. 2 of the paper); that they appear in the paper is not verified.
4. **Internal consistency**: forward/reverse round trips, monotonicity and limiting cases (automated tests).
5. **Browser/interface tests**: the rendered app shows the expected numbers (automated tests).

None of these are experimental measurements.
"""
        )
        es_df = validation.es_comparison()
        st.caption(f"Saturation vapour pressure vs FAO-56 Table 2.3 (published to 3 d.p.; tolerance "
                   f"±{validation.TOL_ES_KPA:.4f} kPa). Validation tables show 3-5 decimals by design.")
        st.dataframe(es_df, hide_index=True, width="stretch", key="val_es_table",
                     column_config={c: st.column_config.NumberColumn(format="%.4f")
                                    for c in ("Published es (kPa)", "Application es (kPa)")} |
                                   {"Difference (kPa)": st.column_config.NumberColumn(format="%.5f")})
        st.caption("Alternative equation (Johnston et al., 2025): " + validation.JOHNSTON_FORMULA)
        st.dataframe(validation.alternative_equation_comparison(), hide_index=True, width="stretch",
                     key="val_alt_table",
                     column_config={c: st.column_config.NumberColumn(format="%.4f")
                                    for c in ("Johnston calculated benchmark VPD (kPa)", "Johnston equation, computed (kPa)",
                                              "Application VPD (kPa)")} |
                                   {"Application - Johnston (kPa)": st.column_config.NumberColumn(format="%.5f")})
        mx = validation.max_abs_differences()
        st.caption(
            f"Largest absolute differences: es vs FAO-56 table {mx['es_vs_FAO_table']:.5f} kPa; "
            f"VPD vs calculated FAO-56 benchmark {mx['vpd_vs_FAO56_benchmark']:.5f} kPa; "
            f"application vs Johnston equation {mx['application_vs_Johnston_equation']:.5f} kPa. "
            "The equations differ slightly because their saturation-vapour-pressure coefficients differ.")

        st.markdown("#### C. Air VPD versus relative humidity")
        c1, c2 = st.columns([3, 1])
        val_temps = c1.multiselect("Temperatures (°C)", list(range(0, 46)), default=[20, 25, 30],
                                   key="val_temps")
        val_alt = c2.checkbox("Overlay Johnston et al. (2025)", key="val_johnston")
        if not val_temps:
            st.info("Select at least one temperature.")
        else:
            curves = validation.reference_curves(sorted(val_temps))
            st.plotly_chart(plots.reference_figure(curves, val_alt), width="stretch")
            st.plotly_chart(plots.reference_difference_figure(curves), width="stretch")
            st.markdown(
                """
- At constant air temperature, VPD decreases linearly with RH.
- At constant RH, VPD increases with temperature.
- Air VPD is zero at 100 % RH.
- The two equations give slightly different values because their coefficients differ (difference shown above).
- Primary curves use FAO-56 with a leaf offset of 0 °C (air VPD does not depend on leaf temperature).
"""
            )
            g1, g2 = st.columns(2)
            g1.download_button("Download VPD-vs-RH numerical results (CSV)", to_csv(curves),
                               "vpd_vs_rh_reference.csv", "text/csv", key="dl_val_csv")
            # Every input of the exported figure: the selected temperatures and the Johnston overlay.
            val_sig = (tuple(sorted(val_temps)), bool(val_alt))
            if g2.button("Prepare VPD-vs-RH graph (PNG)", key="val_png_prepare"):
                st.session_state["val_png"] = (val_sig, mpl_export.to_bytes(
                    mpl_export.reference_mpl(curves, val_alt), "png", 200))
            if "val_png" in st.session_state and st.session_state["val_png"][0] == val_sig:
                g2.download_button("Download VPD-vs-RH graph (PNG)", st.session_state["val_png"][1],
                                   "vpd_vs_rh.png", "image/png", key="dl_val_png")

        st.markdown("#### D. Validation table")
        st.caption("Air VPD from the production function vs benchmarks calculated from the FAO-56 equation "
                   "(calculated values, not tabulated in FAO-56; rounded to 4 d.p.; "
                   f"tolerance ±{validation.TOL_VPD_KPA:.4f} kPa). "
                   "Values are compared at full precision before formatting. Outcomes are evaluated now, "
                   "when this page is rendered.")
        st.dataframe(validation.vpd_comparison(), hide_index=True, width="stretch", key="val_vpd_table",
                     column_config={c: st.column_config.NumberColumn(format="%.4f")
                                    for c in ("FAO-56 calculated benchmark VPD (kPa)", "Application VPD (kPa)")} |
                                   {"Difference (kPa)": st.column_config.NumberColumn(format="%.5f")})
        with st.expander("Inspect an additional example"):
            e1, e2 = st.columns(2)
            ex_t = e1.number_input("Air temperature (°C)", value=27.5, step=0.5, format="%.1f", key="val_extra_t")
            ex_rh = e2.number_input("RH (%)", value=65.0, min_value=0.0, max_value=100.0, step=1.0,
                                    format="%.1f", key="val_extra_rh")
            st.dataframe(pd.DataFrame([validation.additional_example(ex_t, ex_rh)]), hide_index=True,
                         width="stretch", key="val_extra_table",
                         column_config={c: st.column_config.NumberColumn(format="%.4f")
                                        for c in ("Application VPD (kPa)", "Johnston equation VPD (kPa)")} |
                                       {"Application - Johnston (kPa)": st.column_config.NumberColumn(format="%.5f")})
            st.caption("No tabulated benchmark exists for arbitrary inputs, so this example is compared "
                       "with the alternative equation only.")
