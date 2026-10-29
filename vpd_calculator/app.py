"""VPD Calculator - Streamlit app.  Run with:  streamlit run app.py"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import streamlit as st

import citation
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
    for name in ("vpd", "share", "presets", "citation", "validation", "plots", "mpl_export", "rscript", "treatments"):
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
    "calc_offset": 0.0, "calc_leaf_meas": 22.0,
    "vpd_lo": 0.8, "vpd_hi": 1.2,
    "dn_t_day": 22.0, "dn_t_night": 17.0,
    "dn_off_day": 0.0, "dn_off_night": 0.0,
    "dn_lo_day": 0.8, "dn_hi_day": 1.2, "dn_lo_night": 0.8, "dn_hi_night": 1.2,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# Every shareable setting with its default (used when a setup file omits a setting).
CHOICE_DEFAULTS = {
    "mode": share.MODE_A, "target_kind": share.AIR_LABEL, "interval_kind": share.AIR_LABEL,
    "calc_leaf_method": share.OFFSET_METHOD, "dn_kind_day": share.AIR_LABEL, "dn_kind_night": share.AIR_LABEL,
    "hm_kind": share.AIR_LABEL,
}
SETTING_DEFAULTS = DEFAULTS | share.HEATMAP_DEFAULTS | CHOICE_DEFAULTS


def derive_preset_state():
    """Preset selectors follow the (already restored) numerical settings; saved identities are kept."""
    st.session_state["vpd_preset"] = presets.match_stage(st.session_state["vpd_lo"], st.session_state["vpd_hi"])
    st.session_state["calc_offset_preset"] = presets.match_offset_preset(st.session_state["calc_offset"])
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


def apply_setup():
    """'Apply setup' callback. Runs before the script reruns, so widget-bound keys may be changed safely.

    The whole file is validated first; on any problem nothing is changed.
    """
    upload = st.session_state.get("setup_upload")
    if upload is None:
        st.session_state["_setup_status"] = ("error", "Choose a setup file first. Nothing was changed.")
        return
    params, error = share.validate_setup(upload.getvalue())
    if error:
        st.session_state["_setup_status"] = ("error", f"Setup not applied: {error}")
        return
    for _p in ("day", "night"):
        st.session_state.pop(f"dn_preset_{_p}", None)         # saved identity comes only from the file
    st.session_state.update(SETTING_DEFAULTS)                 # settings missing from the file use the defaults
    st.session_state.update(share.parse_params(params))
    derive_preset_state()
    st.session_state["_setup_status"] = ("ok", f"Setup \"{upload.name}\" applied.")


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


def leaf_inputs(prefix, t_air):
    """Returns (effective_offset, measured_or_None)."""
    method = st.radio("Leaf temperature input", [share.OFFSET_METHOD, share.MEASURED_METHOD],
                      key=f"{prefix}_leaf_method", horizontal=True)
    if method == share.OFFSET_METHOD:
        off = offset_widget("Leaf temperature offset (°C)", f"{prefix}_offset", f"{prefix}_offset_preset")
        st.caption("Offsets are illustrative scenarios, not universal correction factors.")
        with st.expander("About leaf-offset scenarios"):
            st.markdown(presets.LEAF_OFFSET_DISCLAIMER)
            st.caption("Source for the typical leaf-offset note: " + presets.SOURCE_APA)
        return off, None
    meas = linked("Measured leaf temperature (°C)", f"{prefix}_leaf_meas", -5.0, 50.0, 0.1)
    return meas - t_air, meas


def kind_from_label(label):
    return vpd.AIR if label.startswith("Air") else vpd.LEAF


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


tab_calc, tab_daynight, tab_compare, tab_heat, tab_methods = st.tabs(
    ["Calculator", "Day & Night", "Compare treatments", "VPD Heatmap", "Methods & References"])

# ==========================================================================
# Calculator
# ==========================================================================
with tab_calc:
    st.title("Vapour Pressure Deficit calculator")
    mode = st.radio("Calculation mode", [share.MODE_A, share.MODE_B], key="mode", horizontal=True)
    mode_a = mode == share.MODE_A

    left, right = st.columns([5, 6], gap="large")
    with left:
        t_air = linked("Air temperature (°C)", "t_air", 0.0, 45.0, 0.1, num_min=-10.0, num_max=60.0)
        if mode_a:
            rh_in = linked("Relative humidity (%)", "rh", 0.0, 100.0, 0.1)
        else:
            kind_label = st.radio("Target VPD refers to", ["Air VPD", "Leaf VPD"],
                                  key="target_kind", horizontal=True)
            tgt = linked("Target VPD (kPa)", "target_vpd", 0.0, 5.0, 0.1, num_min=-5.0, num_max=10.0)
        offset, measured = leaf_inputs("calc", t_air)

    current_rh, cur_air, cur_leaf = None, None, None
    results_row = {}
    with right:
        st.subheader("Results")
        if mode_a:
            r = vpd.calculate_vpd(t_air, rh_in, offset, measured)
            c1, c2 = st.columns(2)
            c1.metric("Air VPD", f"{r.vpd_air:.1f} kPa")
            c2.metric("Leaf VPD", f"{r.vpd_leaf:.1f} kPa")
            st.caption(f"Leaf temperature used: {r.t_leaf:.1f} °C (offset {r.t_leaf - t_air:+.1f} °C)")
            with st.expander("Calculation details"):
                d1, d2, d3 = st.columns(3)
                d1.metric("Saturation vapour pressure (air)", f"{r.es_air:.1f} kPa")
                d2.metric("Actual vapour pressure", f"{r.ea:.1f} kPa")
                d3.metric("Saturation vapour pressure (leaf)", f"{r.es_leaf:.1f} kPa")
            for w in r.warnings:
                st.warning(w)
            current_rh, cur_air, cur_leaf = rh_in, r.vpd_air, r.vpd_leaf
            results_row = r.as_dict() | {"mode": "Calculate VPD"}
        else:
            res = vpd.calculate_required_rh(t_air, tgt, kind_from_label(kind_label), offset, measured)
            if res.attainable:
                st.metric("Required relative humidity", f"{res.rh:.1f} %")
                c1, c2 = st.columns(2)
                c1.metric("Resulting air VPD", f"{res.vpd_air:.1f} kPa")
                c2.metric("Resulting leaf VPD", f"{res.vpd_leaf:.1f} kPa")
                st.caption(f"Leaf temperature used: {res.t_leaf:.1f} °C (offset {res.t_leaf - t_air:+.1f} °C)")
                for w in res.warnings:
                    st.warning(w)
                current_rh = min(max(res.rh, 0.0), 100.0)  # only tiny float-tolerance clipping
                cur_air, cur_leaf = res.vpd_air, res.vpd_leaf
            else:
                st.error(res.message)
                st.metric("Required relative humidity (not physically attainable)", f"{res.rh:.1f} %")
            results_row = res.as_dict() | {"mode": "Calculate required RH"}

    with st.expander("Air VPD vs leaf VPD: what is the difference?"):
        st.markdown(
            """
**Air VPD** is the drying power of the bulk air. It is the saturation vapour pressure at *air*
temperature minus the actual vapour pressure of the air:

$$VPD_{air} = e_s(T_{air}) - e_a$$

**Leaf VPD** uses the same actual vapour pressure $e_a$ but evaluates saturation at *leaf* temperature,
because the air spaces inside a leaf are assumed to be saturated at leaf temperature:

$$VPD_{leaf} = e_s(T_{leaf}) - e_a$$

Leaf VPD is therefore the vapour-pressure gradient from the leaf interior to the surrounding air, which is the
driving force for water loss. When the leaf is cooler than the air (for example because it is transpiring),
$e_s(T_{leaf})$ is smaller, so leaf VPD is lower than air VPD. If the leaf is cool enough that
$e_s(T_{leaf}) < e_a$, leaf VPD becomes negative and condensation on the leaf is possible.

The leaf-temperature offset is an input, not a calculated quantity. Use the offset scenarios as illustrations
only; they are not universal correction factors. Where it matters, measure leaf temperature directly.
Grower guidance describes leaves as typically about 1-3 °C cooler than the air (Koverda, 2020); see
Methods & References for sources and limitations.
"""
        )

    # ---- Target VPD range ---------------------------------------------------
    st.divider()
    st.subheader("Target VPD range")

    def apply_main_preset():
        name = st.session_state["vpd_preset"]
        if name in presets.GROWTH_STAGES:
            st.session_state["vpd_lo"], st.session_state["vpd_hi"] = presets.stage_range(name, "day")

    def main_range_edited():
        st.session_state["vpd_preset"] = presets.match_stage(st.session_state["vpd_lo"], st.session_state["vpd_hi"])

    st.session_state.setdefault("vpd_preset", presets.match_stage(st.session_state["vpd_lo"], st.session_state["vpd_hi"]))
    pc1, pc2 = st.columns([1, 2], gap="large")
    with pc1:
        st.selectbox("Growth-stage preset (illustrative)", presets.PRESET_NAMES, key="vpd_preset",
                     on_change=apply_main_preset)
    with pc2:
        stage = st.session_state["vpd_preset"]
        if stage in presets.GROWTH_STAGES:
            st.caption(f"**{stage}.** {presets.GROWTH_STAGES[stage]['note']}")
        st.caption("Illustrative ranges, not scientifically validated species-specific optima.")
        with st.expander("About the growth-stage presets"):
            st.markdown(presets.PRESET_DISCLAIMER + " Choose 'Custom' or edit the limits to set your own range.")
            st.caption("Source: " + presets.SOURCE_APA)
    ic1, ic2, ic3 = st.columns([1, 1, 1], gap="large")
    with ic1:
        lo = linked("Lower limit (kPa)", "vpd_lo", 0.0, 4.0, 0.1, num_max=10.0, after=main_range_edited)
    with ic2:
        hi = linked("Upper limit (kPa)", "vpd_hi", 0.0, 4.0, 0.1, num_max=10.0, after=main_range_edited)
    with ic3:
        ikind_label = st.radio("Range applies to", ["Air VPD", "Leaf VPD"], key="interval_kind")
        ikind = kind_from_label(ikind_label)

    interval_ok = lo <= hi
    if not interval_ok:
        st.error("Lower limit must not exceed the upper limit.")
    else:
        rr = vpd.rh_range_for_vpd_range(t_air, lo, hi, ikind, offset, measured)
        s1, s2 = st.columns([1, 1], gap="large")
        with s1:
            cur = None if current_rh is None else (cur_air if ikind == vpd.AIR else cur_leaf)
            if cur is None:
                st.info("Current conditions are not available (target VPD is unattainable).")
            else:
                pos = vpd.classify_vpd(cur, lo, hi)
                txt = f"Current {ikind} VPD = {cur:.1f} kPa"
                if vpd.is_point_target(lo, hi):
                    msg = f"{txt}: {vpd.classify_wording(pos)} ({lo:.1f} kPa)."
                    (st.success if pos == "inside" else st.warning)(msg)
                elif pos == "inside":
                    st.success(f"{txt}: inside the range {lo:.1f}-{hi:.1f} kPa.")
                else:
                    st.warning(f"{txt}: {pos} the range {lo:.1f}-{hi:.1f} kPa.")
            if vpd.is_point_target(lo, hi):
                st.markdown(f"**Target {ikind} VPD: {lo:.1f} kPa**")
            if rr["attainable"] and vpd.is_point_target(lo, hi):
                st.metric(f"Required RH for {ikind} VPD {lo:.1f} kPa at {t_air:.1f} °C",
                          f"{rr['rh_min']:.1f} %")
            elif rr["attainable"]:
                st.metric(f"RH range for {ikind} VPD {lo:.1f}-{hi:.1f} kPa at {t_air:.1f} °C",
                          f"{rr['rh_min']:.1f} - {rr['rh_max']:.1f} %")
                if not rr["fully_attainable"]:
                    st.warning(
                        f"Part of the range is unattainable: unclipped RH range is "
                        f"{rr['rh_min_raw']:.1f} to {rr['rh_max_raw']:.1f} %. Showing the attainable part.")
            elif vpd.is_point_target(lo, hi):
                st.error(f"No RH between 0 and 100 % gives a {ikind} VPD of {lo:.1f} kPa "
                         f"(unclipped RH {rr['rh_min_raw']:.1f} %).")
            else:
                st.error(f"No RH between 0 and 100 % gives a {ikind} VPD in this range "
                         f"(unclipped RH {rr['rh_min_raw']:.1f} to {rr['rh_max_raw']:.1f} %).")
        with s2:
            st.plotly_chart(plots.vpd_vs_rh_figure(t_air, offset, ikind, rh_range=rr, point_rh=current_rh),
                            width="stretch")


    # ---- Export current settings --------------------------------------------
    st.divider()
    settings = pd.DataFrame(
        [{"quantity": k, "value": v} for k, v in (
            {"mode": results_row.get("mode"), "target_kind": results_row.get("kind"),
             "target_vpd_kPa": results_row.get("target_vpd"),
             "range_low_kPa": lo, "range_high_kPa": hi, "range_kind": ikind} |
            {k: v for k, v in results_row.items()
             if k not in ("mode", "kind", "target_vpd", "warnings", "message")}).items()])
    st.download_button("Download current settings and results (CSV)", to_csv(settings),
                       "vpd_current_settings.csv", "text/csv", key="dl_settings_csv")

    # Keep the address bar in sync so the current URL is always a shareable link.
    st.query_params.from_dict(share.build_params(st.session_state))
    with st.expander("Share these settings"):
        st.caption("Opening this link restores the calculator mode, temperature, RH, target VPD, "
                   "leaf temperature and target range, plus, independently for day and night: air "
                   "temperature, leaf-temperature offset, lower and upper VPD limits, whether the range "
                   "applies to air or leaf VPD, and the selected growth-stage preset (or Custom). "
                   "It also restores the heatmap settings: VPD type, temperature and RH limits, colour "
                   "scale and maximum, contour spacing, and the target and selected-point toggles.")
        st.code(share.share_url(st.session_state), language=None)
        st.download_button("Download setup (JSON)", share.setup_json(st.session_state).encode("utf-8"),
                           share.SETUP_FILENAME, "application/json", key="dl_setup_json")
        st.caption("The JSON file records the calculation and heatmap settings (the same settings as the link), "
                   "not results, images or other session data.")
        st.file_uploader("Load setup (JSON)", type=["json"], key="setup_upload",
                         help="Choosing a file does not change anything until you press Apply setup.")
        st.button("Apply setup", key="setup_apply", on_click=apply_setup,
                  disabled=st.session_state.get("setup_upload") is None)
        st.caption("Applying a setup replaces the calculator, day/night and heatmap settings. Settings missing "
                   "from the file return to their defaults; an invalid file changes nothing.")
        _status = st.session_state.pop("_setup_status", None)
        if _status:
            (st.success if _status[0] == "ok" else st.error)(_status[1])

# ==========================================================================
# Day & Night
# ==========================================================================
with tab_daynight:
    # ---- Day and night ranges (stacked) ---------------------------------------
    st.subheader("Day and night target VPD ranges")
    st.caption("Configure the day and night conditions independently. The required RH range is calculated "
               "at each period's own temperature and optional leaf offset. Presets are illustrative.")

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
                dkind = kind_from_label(st.radio(f"{period} range applies to", ["Air VPD", "Leaf VPD"],
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
# Compare treatments
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
    hm_kind_label = g1.radio("VPD type", ["Air VPD", "Leaf VPD"], key="hm_kind", horizontal=True)
    cscale = g2.selectbox("Colour scale", plots.COLORSCALES, key="hm_cs")
    cstep = g3.selectbox("Contour spacing (kPa)", [0.1, 0.2, 0.5, 1.0], index=2, key="hm_step")
    zmax_in = g4.number_input("Colour scale max (kPa, 0 = auto)", min_value=0.0, value=0.0, step=0.5,
                              format="%.1f", key="hm_zmax")
    o1, o2 = st.columns(2)
    show_target = o1.checkbox("Highlight target range from Calculator tab", value=True, key="hm_target")
    show_point = o2.checkbox("Mark selected temperature/RH", value=True, key="hm_point")
    hm_kind = kind_from_label(hm_kind_label)

    if t_min >= t_max or rh_min >= rh_max:
        st.error("Minimum values must be smaller than maximum values.")
    else:
        pt = (t_air, current_rh) if (show_point and current_rh is not None) else None
        tg = (lo, hi) if (show_target and interval_ok) else None
        if hm_kind == vpd.LEAF or (tg is not None and ikind == vpd.LEAF):      # leaf VPD is used by the chart
            sign = "−" if offset < 0 else "+"
            note = (f"Leaf VPD here assumes one constant leaf–air offset of {offset:+.1f} °C: leaf temperature = "
                    f"air temperature {sign} {abs(offset):.1f} °C throughout this chart.")
            if measured is not None:
                note += (f" The offset is derived from the measured leaf temperature ({measured:.1f} °C) and the "
                         f"Calculator's air temperature ({t_air:.1f} °C).")
            st.caption(note)
        fig = plots.heatmap_figure(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale, cstep,
                                   zmax_in or None, pt, tg, target_kind=ikind)
        st.plotly_chart(fig, width="stretch", config={"toImageButtonOptions": {"format": "png", "scale": 2}})
        if any(trace.name == vpd.ZERO_LABEL for trace in fig.data):
            st.caption("Negative leaf VPD (beyond the saturation line) indicates possible condensation.")
        if tg:
            if vpd.is_point_target(lo, hi):
                st.caption(f"Dashed contour: user-defined single-value target **{ikind} VPD** "
                           f"{lo:.1f} kPa (set by 'Range applies to' on the Calculator tab; "
                           f"colours show {hm_kind} VPD).")
            else:
                st.caption(f"Dashed contours and light overlay: user-defined target **{ikind} VPD** range "
                           f"{lo:.1f}-{hi:.1f} kPa (set by 'Range applies to' on the Calculator tab; "
                           f"colours show {hm_kind} VPD).")

        d1, d2, d3 = st.columns(3)
        grid = vpd.vpd_grid(t_min, t_max, rh_min, rh_max, 0.5, 1.0, offset=offset)
        d1.download_button("Download grid (CSV)", to_csv(grid), "vpd_grid.csv", "text/csv", key="dl_grid_csv")

        hm_params = dict(t_min=t_min, t_max=t_max, rh_min=rh_min, rh_max=rh_max, kind=hm_kind,
                         offset=offset, colorscale=cscale, contour_step=cstep, z_max=zmax_in or None,
                         point=pt, target=tg, target_kind=ikind)
        leaf_t = measured if measured is not None else t_air + offset
        r_code = rscript.build_r_script(
            mode_a, t_air, st.session_state["rh"], st.session_state["target_vpd"],
            kind_from_label(st.session_state.get("target_kind", "Air VPD")), leaf_t,
            (lo, hi) if interval_ok else None, ikind, heatmap=hm_params)
        d3.download_button("Download reproducible R script", r_code.encode("utf-8"),
                           "vpd_heatmap.R", "text/plain", key="dl_rscript",
                           help="Reproduces the calculation and this heatmap with ggplot2 (PNG and PDF export).")

        sig = (t_min, t_max, rh_min, rh_max, hm_kind, round(offset, 6), cscale, cstep, zmax_in, pt, tg, ikind)
        if d2.button("Prepare figure downloads", key="png_prepare"):
            export = mpl_export.heatmap_mpl(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale, cstep,
                                            zmax_in or None, pt, tg, target_kind=ikind)
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
