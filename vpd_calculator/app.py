"""VPD Calculator - Streamlit app.  Run with:  streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import logger_data
import plots
import share
import vpd

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
# --------------------------------------------------------------------------
DEFAULTS = {
    "t_air": 22.0, "rh": 60.0, "target_vpd": 1.0,
    "calc_offset": 0.0, "calc_leaf_meas": 22.0,
    "vpd_lo": 0.8, "vpd_hi": 1.2,
    "dn_t_day": 22.0, "dn_t_night": 22.0,
    "dn_rh_day": 70.0, "dn_rh_night": 80.0,
    "dn_vpd_day": 1.0, "dn_vpd_night": 0.6,
    "dn_off_day": 0.0, "dn_off_night": 0.0,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# Settings from a shared link are applied once, at the start of the session.
if "_share_loaded" not in st.session_state:
    st.session_state.update(share.parse_params(st.query_params.to_dict()))
    st.session_state["_share_loaded"] = True


def linked(label, key, lo, hi, step, fmt="%.2f", num_min=None, num_max=None, help=None):
    """Number input + slider bound to one canonical value (`key`)."""
    num, sld = f"{key}__num", f"{key}__sld"
    val = float(st.session_state[key])
    st.session_state[num] = val
    st.session_state[sld] = min(max(val, lo), hi)

    def from_num():
        st.session_state[key] = float(st.session_state[num])

    def from_sld():
        st.session_state[key] = float(st.session_state[sld])

    st.number_input(label, min_value=lo if num_min is None else num_min,
                    max_value=hi if num_max is None else num_max,
                    step=step, format=fmt, key=num, on_change=from_num, help=help)
    st.slider(label, float(lo), float(hi), step=step, key=sld, on_change=from_sld,
              label_visibility="collapsed")
    return float(st.session_state[key])


def leaf_inputs(prefix, t_air):
    """Returns (effective_offset, measured_or_None)."""
    method = st.radio("Leaf temperature input", [share.OFFSET_METHOD, share.MEASURED_METHOD],
                      key=f"{prefix}_leaf_method", horizontal=True)
    if method == share.OFFSET_METHOD:
        off = linked("Leaf temperature offset (°C)", f"{prefix}_offset", -10.0, 10.0, 0.1,
                     help="Leaf temperature minus air temperature. Transpiring leaves are often cooler (negative offset).")
        return off, None
    meas = linked("Measured leaf temperature (°C)", f"{prefix}_leaf_meas", -5.0, 50.0, 0.1)
    return meas - t_air, meas


def kind_from_label(label):
    return vpd.AIR if label.startswith("Air") else vpd.LEAF


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


tab_calc, tab_heat, tab_dn, tab_data, tab_methods = st.tabs(
    ["Calculator", "VPD Heatmap", "Day/Night Experiments", "Measured Data", "Methods"])

# ==========================================================================
# Calculator
# ==========================================================================
with tab_calc:
    st.title("Vapour Pressure Deficit calculator")
    mode = st.radio(
        "Calculation mode",
        [share.MODE_A, share.MODE_B], key="mode", horizontal=True)
    mode_a = mode == share.MODE_A

    left, right = st.columns([5, 6], gap="large")
    with left:
        t_air = linked("Air temperature (°C)", "t_air", 0.0, 45.0, 0.1, num_min=-10.0, num_max=60.0)
        if mode_a:
            rh_in = linked("Relative humidity (%)", "rh", 0.0, 100.0, 0.1)
        else:
            kind_label = st.radio("Target VPD refers to", ["Air VPD", "Leaf VPD"],
                                  key="target_kind", horizontal=True)
            tgt = linked("Target VPD (kPa)", "target_vpd", 0.0, 5.0, 0.01, fmt="%.3f",
                         num_min=-5.0, num_max=10.0)
        offset, measured = leaf_inputs("calc", t_air)

    current_rh, cur_air, cur_leaf = None, None, None
    results_row = {}
    with right:
        st.subheader("Results")
        if mode_a:
            r = vpd.calculate_vpd(t_air, rh_in, offset, measured)
            c1, c2 = st.columns(2)
            c1.metric("Air VPD", f"{r.vpd_air:.3f} kPa")
            c2.metric("Leaf VPD", f"{r.vpd_leaf:.3f} kPa")
            c3, c4 = st.columns(2)
            c3.metric("Saturation vapour pressure (air)", f"{r.es_air:.3f} kPa")
            c4.metric("Actual vapour pressure", f"{r.ea:.3f} kPa")
            st.caption(f"Leaf temperature: {r.t_leaf:.2f} °C (offset {r.t_leaf - t_air:+.2f} °C); "
                       f"saturation vapour pressure at leaf: {r.es_leaf:.3f} kPa")
            for w in r.warnings:
                st.warning(w)
            current_rh, cur_air, cur_leaf = rh_in, r.vpd_air, r.vpd_leaf
            results_row = r.as_dict() | {"mode": "Calculate VPD"}
        else:
            res = vpd.calculate_required_rh(t_air, tgt, kind_from_label(kind_label), offset, measured)
            if res.attainable:
                st.metric("Required relative humidity", f"{res.rh:.2f} %")
                c1, c2 = st.columns(2)
                c1.metric("Resulting air VPD", f"{res.vpd_air:.3f} kPa")
                c2.metric("Resulting leaf VPD", f"{res.vpd_leaf:.3f} kPa")
                st.caption(f"Leaf temperature: {res.t_leaf:.2f} °C (offset {res.t_leaf - t_air:+.2f} °C)")
                for w in res.warnings:
                    st.warning(w)
                current_rh = min(max(res.rh, 0.0), 100.0)  # only tiny float-tolerance clipping
                cur_air, cur_leaf = res.vpd_air, res.vpd_leaf
            else:
                st.error(res.message)
                st.metric("Required relative humidity (not physically attainable)", f"{res.rh:.2f} %")
            results_row = res.as_dict() | {"mode": "Calculate required RH"}

    with st.expander("Air VPD vs leaf VPD"):
        st.markdown(
            "**Air VPD** is the drying power of the bulk air: saturation vapour pressure at air "
            "temperature minus the actual vapour pressure. **Leaf VPD** replaces the air temperature "
            "with the leaf temperature in the saturation term, because the air inside the leaf is "
            "assumed saturated at leaf temperature. It is the driving force for transpiration. "
            "A cooler leaf lowers leaf VPD; a negative value means condensation is possible.")

    # ---- Target VPD interval ------------------------------------------------
    st.divider()
    st.subheader("Target VPD interval (user-defined)")
    st.caption("Illustrative range chosen by you. It is not an experimentally validated optimum "
               "for any species, including *Fragaria vesca*.")
    ic1, ic2, ic3 = st.columns([1, 1, 1], gap="large")
    with ic1:
        lo = linked("Lower limit (kPa)", "vpd_lo", 0.0, 4.0, 0.05, fmt="%.3f", num_max=10.0)
    with ic2:
        hi = linked("Upper limit (kPa)", "vpd_hi", 0.0, 4.0, 0.05, fmt="%.3f", num_max=10.0)
    with ic3:
        ikind_label = st.radio("Interval applies to", ["Air VPD", "Leaf VPD"], key="interval_kind")
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
                txt = f"Current {ikind} VPD = {cur:.3f} kPa"
                if pos == "inside":
                    st.success(f"{txt}: inside the interval {lo:.3f}-{hi:.3f} kPa.")
                else:
                    st.warning(f"{txt}: {pos} the interval {lo:.3f}-{hi:.3f} kPa.")
            if rr["attainable"]:
                st.metric(f"RH range for {ikind} VPD {lo:.2f}-{hi:.2f} kPa at {t_air:.1f} °C",
                          f"{rr['rh_min']:.2f} - {rr['rh_max']:.2f} %")
                if not rr["fully_attainable"]:
                    st.warning(
                        f"Part of the interval is unattainable: unclipped RH range is "
                        f"{rr['rh_min_raw']:.2f} to {rr['rh_max_raw']:.2f} %. Showing the attainable part.")
            else:
                st.error(f"No RH between 0 and 100 % gives a {ikind} VPD in this interval "
                         f"(unclipped RH {rr['rh_min_raw']:.2f} to {rr['rh_max_raw']:.2f} %).")
        with s2:
            st.plotly_chart(plots.vpd_vs_rh_figure(t_air, offset, ikind, rh_range=rr, point_rh=current_rh),
                            width="stretch")

    # ---- Export current settings --------------------------------------------
    settings = pd.DataFrame(
        [{"quantity": k, "value": v} for k, v in (
            {"mode": results_row.get("mode"), "target_kind": results_row.get("kind"),
             "target_vpd_kPa": results_row.get("target_vpd"),
             "interval_low_kPa": lo, "interval_high_kPa": hi, "interval_kind": ikind} |
            {k: v for k, v in results_row.items()
             if k not in ("mode", "kind", "target_vpd", "warnings", "message")}).items()])
    st.download_button("Download current settings and results (CSV)", to_csv(settings),
                       "vpd_current_settings.csv", "text/csv")

    # Keep the address bar in sync so the current URL is always a shareable link.
    st.query_params.from_dict(share.build_params(st.session_state))
    with st.expander("Share these settings"):
        st.caption("Opening this link restores the calculator mode, temperature, RH, target VPD, "
                   "leaf temperature and target interval.")
        st.code(share.share_url(st.session_state), language=None)

# ==========================================================================
# Heatmap
# ==========================================================================
with tab_heat:
    st.subheader("VPD as a function of temperature and relative humidity")
    h1, h2, h3, h4 = st.columns(4)
    t_min = h1.number_input("Min temperature (°C)", value=10.0, step=1.0, key="hm_tmin")
    t_max = h2.number_input("Max temperature (°C)", value=40.0, step=1.0, key="hm_tmax")
    rh_min = h3.number_input("Min RH (%)", value=10.0, min_value=0.0, max_value=99.0, step=5.0, key="hm_rhmin")
    rh_max = h4.number_input("Max RH (%)", value=100.0, min_value=1.0, max_value=100.0, step=5.0, key="hm_rhmax")
    g1, g2, g3, g4 = st.columns(4)
    hm_kind_label = g1.radio("VPD type", ["Air VPD", "Leaf VPD"], key="hm_kind", horizontal=True)
    cscale = g2.selectbox("Colour scale", plots.COLORSCALES, key="hm_cs")
    cstep = g3.selectbox("Contour spacing (kPa)", [0.1, 0.2, 0.25, 0.5, 1.0], index=3, key="hm_step")
    zmax_in = g4.number_input("Colour scale max (kPa, 0 = auto)", min_value=0.0, value=0.0, step=0.5, key="hm_zmax")
    o1, o2 = st.columns(2)
    show_target = o1.checkbox("Highlight target interval from Calculator tab", value=True, key="hm_target")
    show_point = o2.checkbox("Mark selected temperature/RH", value=True, key="hm_point")
    hm_kind = kind_from_label(hm_kind_label)

    if t_min >= t_max or rh_min >= rh_max:
        st.error("Minimum values must be smaller than maximum values.")
    else:
        if hm_kind == vpd.LEAF:
            st.caption(f"Leaf VPD uses a leaf offset of {offset:+.2f} °C from the Calculator tab"
                       + (" (derived from the measured leaf temperature at the selected air temperature)."
                          if measured is not None else "."))
        pt = (t_air, current_rh) if (show_point and current_rh is not None) else None
        tg = (lo, hi) if (show_target and interval_ok) else None
        fig = plots.heatmap_figure(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale, cstep,
                                   zmax_in or None, pt, tg)
        st.plotly_chart(fig, width="stretch", config={"toImageButtonOptions": {"format": "png", "scale": 2}})
        if tg:
            st.caption(f"Dashed contours and light overlay: user-defined {hm_kind} VPD interval "
                       f"{lo:.2f}-{hi:.2f} kPa.")

        d1, d2 = st.columns(2)
        grid = vpd.vpd_grid(t_min, t_max, rh_min, rh_max, 0.5, 1.0, offset=offset)
        d1.download_button("Download grid (CSV)", to_csv(grid), "vpd_grid.csv", "text/csv")
        sig = (t_min, t_max, rh_min, rh_max, hm_kind, round(offset, 6), cscale, cstep, zmax_in, pt, tg)
        if d2.button("Prepare publication-quality PNG"):
            try:
                export = plots.heatmap_figure(t_min, t_max, rh_min, rh_max, hm_kind, offset, cscale,
                                              cstep, zmax_in or None, pt, tg,
                                              template="plotly_white", width=1400, height=900)
                st.session_state["png"] = (sig, export.to_image(format="png", scale=2))
            except Exception as e:  # kaleido/Chrome missing
                st.session_state.pop("png", None)
                st.info("Server-side PNG export is not available in this environment "
                        "(it needs Chrome/Chromium). Use the camera icon in the chart's toolbar "
                        "to download a PNG instead, or run the app locally with Chrome installed.")
                st.caption(f"Details: {type(e).__name__}")
        if "png" in st.session_state and st.session_state["png"][0] == sig:
            d2.download_button("Download PNG", st.session_state["png"][1], "vpd_heatmap.png", "image/png")

# ==========================================================================
# Day / night experiments
# ==========================================================================
with tab_dn:
    st.subheader("Day/night phytotron conditions")
    st.caption("The treatments below are experimental temperature settings, not VPD recommendations.")

    def apply_preset():
        p = st.session_state["dn_preset"]
        if p in vpd.TREATMENTS:
            st.session_state["dn_t_day"], st.session_state["dn_t_night"] = vpd.TREATMENTS[p]

    w1, w2, w3 = st.columns([2, 2, 1])
    workflow = w1.radio("Workflow", ["Enter RH, calculate VPD", "Enter target VPD, calculate RH"],
                        key="dn_workflow", horizontal=True)
    from_rh = workflow.startswith("Enter RH")
    w2.selectbox("Temperature preset", ["Custom"] + list(vpd.TREATMENTS), key="dn_preset",
                 on_change=apply_preset)
    dn_kind = vpd.AIR
    if not from_rh:
        dn_kind = kind_from_label(w3.radio("Target VPD refers to", ["Air VPD", "Leaf VPD"], key="dn_kind"))

    cday, cnight = st.columns(2, gap="large")
    vals, offs, temps_dn, res_dn = {}, {}, {}, {}
    for col, period, p in ((cday, "Day", "day"), (cnight, "Night", "night")):
        with col:
            st.markdown(f"#### {period}")
            temps_dn[p] = linked(f"{period} temperature (°C)", f"dn_t_{p}", 0.0, 45.0, 0.1,
                                 num_min=-10.0, num_max=60.0)
            if from_rh:
                vals[p] = linked(f"{period} RH (%)", f"dn_rh_{p}", 0.0, 100.0, 0.1)
            else:
                vals[p] = linked(f"{period} target VPD (kPa)", f"dn_vpd_{p}", 0.0, 4.0, 0.01,
                                 fmt="%.3f", num_min=-5.0, num_max=10.0)
            offs[p] = linked(f"{period} leaf temperature offset (°C)", f"dn_off_{p}", -10.0, 10.0, 0.1)
            if from_rh:
                r = vpd.calculate_vpd(temps_dn[p], vals[p], offs[p])
                a, b = st.columns(2)
                a.metric(f"{period} air VPD", f"{r.vpd_air:.3f} kPa")
                b.metric(f"{period} leaf VPD", f"{r.vpd_leaf:.3f} kPa")
                for wmsg in r.warnings:
                    st.warning(f"{period}: {wmsg}")
            else:
                r = vpd.calculate_required_rh(temps_dn[p], vals[p], dn_kind, offs[p])
                if r.attainable:
                    st.metric(f"{period} required RH", f"{r.rh:.2f} %")
                    a, b = st.columns(2)
                    a.metric("Air VPD", f"{r.vpd_air:.3f} kPa")
                    b.metric("Leaf VPD", f"{r.vpd_leaf:.3f} kPa")
                    for wmsg in r.warnings:
                        st.warning(f"{period}: {wmsg}")
                else:
                    st.error(f"{period}: {r.message}")

    st.divider()
    st.subheader("Treatment comparison")
    st.caption("Uses the day/night RH or target VPD and leaf offsets above, applied to each treatment's "
               "temperatures. In target-VPD mode this gives the RH needed to hold the same VPD "
               "across treatments. The table is editable (add rows for further treatments).")
    base = pd.DataFrame([{"Treatment": n, "Day (°C)": d, "Night (°C)": nt}
                         for n, (d, nt) in vpd.TREATMENTS.items()])
    edited = st.data_editor(base, num_rows="dynamic", key="dn_editor", hide_index=True)
    edited = edited.dropna().drop_duplicates("Treatment")
    treatments = {str(r["Treatment"]): (float(r["Day (°C)"]), float(r["Night (°C)"]))
                  for _, r in edited.iterrows()}
    if treatments:
        cmp_df = vpd.treatment_table(
            treatments, "rh" if from_rh else "vpd", vals["day"], vals["night"], dn_kind,
            offs["day"], offs["night"])
        if not cmp_df["Attainable"].all():
            st.warning("Some treatment/period combinations are physically unattainable "
                       "(RH outside 0-100 %). See the Note column; values are not clipped.")
        st.dataframe(cmp_df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.3f")
                                    for c in cmp_df.columns if "VPD" in c} |
                                   {"RH (%)": st.column_config.NumberColumn(format="%.2f")})
        st.plotly_chart(plots.treatment_figure(cmp_df), width="stretch")
        st.download_button("Download treatment comparison (CSV)", to_csv(cmp_df),
                           "vpd_treatment_comparison.csv", "text/csv")

# ==========================================================================
# Measured data
# ==========================================================================
with tab_data:
    st.subheader("Measured data from a logger")
    st.caption("Upload a CSV with temperature (°C) and RH over time. Rows with missing values, "
               "unparseable times or RH outside 0-100 % are excluded and counted below. "
               "Data are processed in your session and not stored.")
    up = st.file_uploader("Logger CSV", type=["csv", "txt"], key="data_upload")
    use_example = st.checkbox("Use synthetic example data (not real measurements)", key="data_example")

    raw = None
    if up is not None:
        try:
            raw = pd.read_csv(up, sep=None, engine="python")
        except Exception as e:
            st.error(f"Could not read the file as CSV ({type(e).__name__}).")
    elif use_example:
        raw = logger_data.example_data()

    if raw is None or raw.empty:
        st.info("Upload a file or tick the example data option to begin.")
    else:
        cols = list(raw.columns)
        guess = logger_data.guess_columns(cols)
        NONE = "(none)"

        def pick(label, g, key, allow_none=False):
            options = ([NONE] if allow_none else []) + cols
            idx = options.index(g) if g in options else 0
            return st.selectbox(label, options, index=idx, key=key)

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            time_sel = pick("Time column", guess["time"], "data_time", allow_none=True)
        with k2:
            temp_sel = pick("Air temperature column (°C)", guess["temp"], "data_temp")
        with k3:
            rh_sel = pick("RH column", guess["rh"], "data_rh")
        with k4:
            rh_unit = st.radio("RH unit", ["%", "fraction"], key="data_rh_unit", horizontal=True)
        l1, l2 = st.columns(2)
        with l1:
            leaf_src = st.radio("Leaf temperature", ["Offset from air", "Measured column"],
                                key="data_leaf_src", horizontal=True)
        with l2:
            if leaf_src == "Offset from air":
                leaf_off = st.number_input("Leaf temperature offset (°C)", value=0.0, step=0.1,
                                           key="data_offset")
                leaf_col = None
            else:
                leaf_col = pick("Leaf temperature column (°C)", guess["leaf"], "data_leaf")
                leaf_off = 0.0

        clean, rep = logger_data.load_logger_data(
            raw, None if time_sel == NONE else time_sel, temp_sel, rh_sel, rh_unit,
            leaf_col, leaf_off)
        st.caption(f"{rep['rows_used']} of {rep['rows_in']} rows used.")
        if rep["dropped_bad_time"] or rep["dropped_missing_values"] or rep["dropped_rh_out_of_range"]:
            st.warning(
                f"Excluded rows: {rep['dropped_bad_time']} with unparseable time, "
                f"{rep['dropped_missing_values']} with missing/non-numeric values, "
                f"{rep['dropped_rh_out_of_range']} with RH outside 0-100 % "
                "(if RH is a 0-1 fraction, change the RH unit).")
        if rep["temperature_outside_-10_60_kept"]:
            st.warning(f"{rep['temperature_outside_-10_60_kept']} rows have temperatures outside "
                       "-10 to 60 °C; they were kept, please check your sensor data.")
        if rep["negative_leaf_vpd_rows"]:
            st.warning(f"{rep['negative_leaf_vpd_rows']} rows have negative leaf VPD "
                       "(possible condensation).")

        if clean.empty:
            st.error("No usable rows remain. Check the selected columns and units.")
        else:
            interval_for_data = (lo, hi) if interval_ok else None
            summ = logger_data.summarise(clean, lo, hi, ikind) if interval_ok else None
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Mean air VPD", f"{clean['VPD_air_kPa'].mean():.3f} kPa")
            m2.metric("Mean leaf VPD", f"{clean['VPD_leaf_kPa'].mean():.3f} kPa")
            m3.metric("Air VPD range", f"{clean['VPD_air_kPa'].min():.2f} - {clean['VPD_air_kPa'].max():.2f} kPa")
            if summ:
                m4.metric(f"Records inside {lo:.2f}-{hi:.2f} kPa ({ikind})", f"{summ['pct_inside']:.1f} %")
                st.caption("Interval taken from the Calculator tab (user-defined). The share counts "
                           "records, so it equals share of time only for evenly spaced sampling.")
            st.plotly_chart(plots.timeseries_figure(clean, interval_for_data, ikind), width="stretch")
            with st.expander("Processed data"):
                st.dataframe(clean, hide_index=True, width="stretch")
            st.download_button("Download processed data with VPD (CSV)", to_csv(clean),
                               "vpd_logger_processed.csv", "text/csv")

# ==========================================================================
# Methods
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
    st.markdown(
        """
**Assumptions and behaviour**
- The same $e_a$ (set by air temperature and RH) is used for air and leaf VPD; the leaf interior is
  assumed saturated at leaf temperature.
- Leaf temperature is either air temperature plus an offset, or a directly measured value.
- Required RH outside 0-100 % is reported as unattainable, never clipped.
- Negative leaf VPD is allowed and flagged, since it indicates possible condensation on the leaf.
- The FAO-56 equation is an empirical formula in air temperature only; it does not use atmospheric pressure. Results far outside typical growth-chamber temperatures have not been checked here.
- Target VPD intervals are user-defined and are not validated optima for *Fragaria vesca* or any other species.
- The leaf-offset heatmap uses a constant offset across all air temperatures.

**References**
- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration: guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56. Food and Agriculture Organization of the United Nations, Rome. Equation 11 (saturation vapour pressure) is in Chapter 3, "Meteorological data": https://www.fao.org/4/x0490e/x0490e07.htm (full document: https://www.fao.org/4/x0490e/x0490e00.htm)
- Interface inspiration only (not a source for the equations): Pulse Grow, *Vapor Pressure Deficit (VPD)* guide. https://pulsegrow.com/blogs/learn/vpd
""")
