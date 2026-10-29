"""Plotly figure builders for the VPD calculator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import vpd

COLORSCALES = ["RdYlBu_r", "Viridis", "Turbo", "Cividis", "Plasma", "YlGnBu", "Spectral_r", "Greys"]


def heatmap_figure(t_min, t_max, rh_min, rh_max, kind=vpd.AIR, offset=0.0,
                   colorscale="RdYlBu_r", contour_step=0.5, z_max=None,
                   point=None, target=None, template=None,
                   width=None, height=650, target_kind=None, treatments=None) -> go.Figure:
    """Temperature x RH heatmap with labelled contours.

    point  : (t_air, rh) selected state or None
    target : (vpd_low, vpd_high) user-defined interval or None
    treatments : list of dicts (name, t_air, rh, offset, t_leaf, vpd_air, vpd_leaf) drawn as labelled markers;
                 their values use each treatment's own leaf offset, not the chart's.
    target_kind : VPD type the target interval refers to (default: same as `kind`). The colours
                  follow `kind`; the target shading and dashed contours follow `target_kind`.
    """
    temps = np.arange(t_min, t_max + 1e-9, 0.25)
    rhs = np.arange(rh_min, rh_max + 1e-9, 0.5)
    z = vpd.vpd_matrix(temps, rhs, kind, offset)
    label = "Air VPD" if kind == vpd.AIR else "Leaf VPD"
    zmin = float(np.floor(z.min() * 2) / 2) if z.min() < 0 else 0.0
    zmax = float(z_max) if z_max else float(z.max())
    tkind = kind if target_kind is None else target_kind
    zt = z if tkind == kind else vpd.vpd_matrix(temps, rhs, tkind, offset)

    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=z, x=temps, y=rhs, colorscale=colorscale, zmin=zmin, zmax=zmax,
        colorbar=dict(title=dict(text=f"{label} (kPa)")),
        hovertemplate="Temperature: %{x:.1f} °C<br>RH: %{y:.1f} %<br>"
                      + label + ": %{z:.1f} kPa<extra></extra>",
        name=label,
    ))

    if target is not None and not vpd.is_point_target(*target):     # a single value has no band to shade
        lo, hi = target
        mask = np.where((zt >= lo) & (zt <= hi), 1.0, np.nan)
        fig.add_trace(go.Heatmap(
            z=mask, x=temps, y=rhs, zmin=0, zmax=1, showscale=False, hoverinfo="skip",
            name=f"{vpd.target_label(tkind, lo, hi)} (overlay)",
            colorscale=[[0, "rgba(255,255,255,0.45)"], [1, "rgba(255,255,255,0.45)"]],
        ))

    start = np.ceil(z.min() / contour_step) * contour_step
    if start - z.min() < 1e-9:      # a contour on the data minimum is only an edge artefact
        start += contour_step
    fig.add_trace(go.Contour(
        z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip", ncontours=None,
        contours=dict(coloring="lines", showlabels=True, start=start, end=zmax,
                      size=contour_step, labelfont=dict(size=11, color="black"),
                      labelformat=".1f"),
        line=dict(width=1), colorscale=[[0, "rgba(0,0,0,0.55)"], [1, "rgba(0,0,0,0.55)"]],
    ))

    if kind == vpd.LEAF and vpd.zero_boundary_in_range(z):       # leaf saturation boundary (existing grid)
        fig.add_trace(go.Contour(
            z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip",
            contours=dict(coloring="lines", showlabels=False, start=0.0, end=0.0, size=1.0),
            line=dict(width=4, color=vpd.ZERO_COLOUR), colorscale=[[0, vpd.ZERO_COLOUR], [1, vpd.ZERO_COLOUR]],
            name=vpd.ZERO_LABEL, showlegend=True,
        ))

    if target is not None:
        lo, hi = target
        fig.add_trace(go.Contour(
            z=zt, x=temps, y=rhs, showscale=False, hoverinfo="skip",
            contours=dict(coloring="lines", showlabels=True, start=lo, end=hi,
                          size=max(hi - lo, 1e-6), labelformat=".1f",   # start == end: one contour
                          labelfont=dict(size=12, color="black")),
            line=dict(width=3, dash="dash"), colorscale=[[0, "black"], [1, "black"]],
            name=vpd.target_label(tkind, lo, hi), showlegend=True,
        ))

    if treatments:
        fig.add_trace(go.Scatter(
            x=[m["t_air"] for m in treatments], y=[m["rh"] for m in treatments], mode="markers+text",
            name="Comparison treatments", text=[m["name"] for m in treatments], textposition="top center",
            textfont=dict(size=11, color="black"),
            marker=dict(symbol="diamond", size=13, color="black", line=dict(color="white", width=2)),
            hoverinfo="text",
            hovertext=[(f"<b>{m['name']}</b><br>Air {m['t_air']:.1f} °C, RH {m['rh']:.1f} %<br>"
                        f"Leaf offset {m['offset']:+.1f} °C, leaf {m['t_leaf']:.1f} °C<br>"
                        f"Air VPD {m['vpd_air']:.1f} kPa<br>Leaf VPD {m['vpd_leaf']:.1f} kPa")
                       for m in treatments],
        ))

    if point is not None:
        t, rh = point
        if t_min <= t <= t_max and rh_min <= rh <= rh_max:
            v = vpd.vpd_matrix([t], [rh], kind, offset)[0, 0]
            fig.add_trace(go.Scatter(
                x=[t], y=[rh], mode="markers", name="Selected",
                marker=dict(symbol="star", size=18, color="white",
                            line=dict(color="black", width=2)),
                hovertemplate=f"Selected<br>{t:.1f} °C, {rh:.1f} %<br>{label}: {v:.1f} kPa<extra></extra>",
            ))

    fig.update_layout(
        template=template, height=height, width=width,
        xaxis=dict(title="Air temperature (°C)", range=[t_min, t_max]),
        yaxis=dict(title="Relative humidity (%)", range=[rh_min, rh_max]),
        title=f"{label} (kPa) as a function of temperature and relative humidity",
        legend=dict(orientation="h", y=-0.15),
        margin=dict(l=70, r=30, t=70, b=70),
    )
    return fig


def vpd_vs_rh_figure(t_air, offset, kind, interval=None, rh_range=None, point_rh=None,
                     template=None) -> go.Figure:
    """VPD as a function of RH at the selected temperature, with the target interval shaded."""
    rh = np.linspace(0, 100, 201)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rh, y=vpd.vpd_air(t_air, rh), name="Air VPD",
                             hovertemplate="RH %{x:.1f} %<br>%{y:.1f} kPa<extra>Air VPD</extra>"))
    fig.add_trace(go.Scatter(x=rh, y=vpd.vpd_leaf(t_air, rh, t_air + offset), name="Leaf VPD",
                             line=dict(dash="dash"),
                             hovertemplate="RH %{x:.1f} %<br>%{y:.1f} kPa<extra>Leaf VPD</extra>"))
    if rh_range and rh_range.get("attainable"):
        if rh_range["rh_min"] == rh_range["rh_max"]:        # single-value target: one line, no band
            fig.add_vline(x=rh_range["rh_min"], line_width=2, line_dash="dash", line_color="green",
                          annotation_text="target RH", annotation_position="top left")
        else:
            fig.add_vrect(x0=rh_range["rh_min"], x1=rh_range["rh_max"], opacity=0.2,
                          line_width=0, fillcolor="green",
                          annotation_text="target RH range", annotation_position="top left")
    if point_rh is not None:
        y = (vpd.vpd_air(t_air, point_rh) if kind == vpd.AIR
             else vpd.vpd_leaf(t_air, point_rh, t_air + offset))
        fig.add_trace(go.Scatter(x=[point_rh], y=[y], mode="markers", name="Current",
                                 marker=dict(size=12, symbol="star", line=dict(width=1))))
    fig.add_hline(y=0, line_width=1, line_dash="dot")
    fig.update_layout(template=template, height=330, margin=dict(l=60, r=20, t=30, b=50),
                      xaxis_title="Relative humidity (%)", yaxis_title="VPD (kPa)",
                      legend=dict(orientation="h", y=1.15))
    return fig


def reference_figure(curves: pd.DataFrame, show_johnston: bool = False, template=None) -> go.Figure:
    """Air VPD vs RH, one colour per temperature. FAO-56 solid; Johnston et al. (2025) dashed."""
    fig = go.Figure()
    for t, d in curves.groupby("temperature_C", sort=True):
        fig.add_trace(go.Scatter(
            x=d["RH_percent"], y=d["VPD_FAO56_kPa"], mode="lines", name=f"{t:g} °C (FAO-56)",
            legendgroup=f"{t:g}", hovertemplate="RH %{x:.1f} %<br>%{y:.4f} kPa<extra>" + f"{t:g} °C FAO-56</extra>"))
        if show_johnston:
            fig.add_trace(go.Scatter(
                x=d["RH_percent"], y=d["VPD_Johnston_kPa"], mode="lines", name=f"{t:g} °C (Johnston)",
                legendgroup=f"{t:g}", line=dict(dash="dash", width=1.5),
                hovertemplate="RH %{x:.1f} %<br>%{y:.4f} kPa<extra>" + f"{t:g} °C Johnston</extra>"))
    fig.update_layout(template=template, height=420, margin=dict(l=60, r=20, t=40, b=50),
                      xaxis=dict(title="Relative humidity (%)", range=[0, 100]),
                      yaxis=dict(title="Air VPD (kPa)", rangemode="tozero"),
                      title="Air VPD vs relative humidity (leaf offset 0 °C)")
    return fig


def reference_difference_figure(curves: pd.DataFrame, template=None) -> go.Figure:
    """FAO-56 minus Johnston VPD (kPa) vs RH."""
    fig = go.Figure()
    for t, d in curves.groupby("temperature_C", sort=True):
        fig.add_trace(go.Scatter(
            x=d["RH_percent"], y=d["difference_FAO56_minus_Johnston_kPa"], mode="lines",
            name=f"{t:g} °C", hovertemplate="RH %{x:.1f} %<br>%{y:.5f} kPa<extra>" + f"{t:g} °C</extra>"))
    fig.update_layout(template=template, height=300, margin=dict(l=70, r=20, t=40, b=50),
                      xaxis=dict(title="Relative humidity (%)", range=[0, 100]),
                      yaxis=dict(title="FAO-56 minus Johnston (kPa)", tickformat=".3f"),
                      title="Difference between the two saturation-vapour-pressure equations")
    return fig
