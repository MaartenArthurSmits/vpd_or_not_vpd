"""Plotly figure builders for the VPD calculator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import rangecolor
import vpd

COLORSCALES = rangecolor.PALETTES


def contour_level_ranges(z_min, z_max, step, skip_zero):
    """(start, end) ranges of the ordinary contour levels; level 0 is left out when the saturation line is drawn."""
    start = np.ceil(z_min / step) * step
    if start - z_min < 1e-9:        # a contour on the data minimum is only an edge artefact
        start += step
    if not skip_zero or start > 0 or z_max < 0:
        return [(float(start), float(z_max))]
    ranges = []
    if start <= -step + 1e-9:
        ranges.append((float(start), float(-step)))
    if z_max >= step - 1e-9:
        ranges.append((float(step), float(z_max)))
    return ranges


def heatmap_figure(t_min, t_max, rh_min, rh_max, kind=vpd.LEAF, offset=0.0,
                   colorscale=rangecolor.DEFAULT_PALETTE, contour_step=0.5, z_max=None,
                   point=None, target=None, template=None,
                   width=None, height=650, target_kind=None, anchor=None) -> go.Figure:
    """Temperature x RH heatmap with labelled contours (canopy VPD by default).

    point  : (t_air, rh) selected state or None
    target : (vpd_low, vpd_high) dashed boundary lines or None (no colour band is drawn)
    anchor : (vpd_low, vpd_high) acceptable range that positions the palette (see rangecolor.mapping) or None
    z_max  : manual colour maximum (ignored when it does not clear the upper anchor)
    target_kind : VPD type the target interval refers to (default: same as `kind`).
    """
    temps = np.arange(t_min, t_max + 1e-9, 0.25)
    rhs = np.arange(rh_min, rh_max + 1e-9, 0.5)
    z = vpd.vpd_matrix(temps, rhs, kind, offset)
    label = "Air VPD" if kind == vpd.AIR else "Canopy VPD"
    tkind = kind if target_kind is None else target_kind
    zt = z if tkind == kind else vpd.vpd_matrix(temps, rhs, tkind, offset)
    anchored = anchor is not None and kind == vpd.LEAF
    m = rangecolor.mapping(float(z.min()), float(z.max()), *(anchor if anchored else (None, None)), z_max=z_max)
    dec = 2 if m["anchored"] else 1
    zero_line = kind == vpd.LEAF and vpd.zero_boundary_in_range(z)

    fig = go.Figure()
    colorbar = dict(title=dict(text=f"{label} (kPa)"))
    if m["anchored"]:
        tk = rangecolor.ticks(m)
        colorbar |= dict(tickmode="array", tickvals=[v for v, _ in tk], ticktext=[s for _, s in tk])
    fig.add_trace(go.Heatmap(
        z=z, x=temps, y=rhs, colorscale=[list(s) for s in rangecolor.stops(colorscale, m)], zmin=m["cmin"], zmax=m["cmax"],
        colorbar=colorbar,
        hovertemplate="Temperature: %{x:.1f} °C<br>RH: %{y:.1f} %<br>" + label + f": %{{z:.{dec}f}} kPa<extra></extra>",
        name=label,
    ))
    if m["anchored"]:           # legend entries for the two sides of the range, in the palette's end colours
        lut = rangecolor.palette_lut(colorscale)
        for name, symbol, colour in (("Below range: VPD under the lower limit", "triangle-down", lut[0]),
                                     ("Above range: VPD over the upper limit", "triangle-up", lut[-1])):
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=name, showlegend=True, hoverinfo="skip",
                                     marker=dict(symbol=symbol, size=11, color=colour, line=dict(color="black", width=1))))

    for start, end in contour_level_ranges(float(z.min()), float(z_max) if z_max else float(z.max()), contour_step, zero_line):
        fig.add_trace(go.Contour(
            z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip", ncontours=None,
            contours=dict(coloring="lines", showlabels=True, start=start, end=end,
                          size=contour_step, labelfont=dict(size=11, color="black"), labelformat=f".{dec}f"),
            line=dict(width=1), colorscale=[[0, "rgba(0,0,0,0.55)"], [1, "rgba(0,0,0,0.55)"]],
        ))

    if zero_line:       # canopy saturation boundary: thin neutral dotted line, drawn only where zero crosses the grid
        fig.add_trace(go.Contour(
            z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip",
            contours=dict(coloring="lines", showlabels=False, start=0.0, end=0.0, size=1.0),
            line=dict(width=1.5, color=vpd.ZERO_COLOUR, dash="dot"), colorscale=[[0, vpd.ZERO_COLOUR], [1, vpd.ZERO_COLOUR]],
            name=vpd.ZERO_LABEL, showlegend=True,
        ))

    if target is not None:
        lo, hi = target
        fig.add_trace(go.Contour(
            z=zt, x=temps, y=rhs, showscale=False, hoverinfo="skip",
            contours=dict(coloring="lines", showlabels=True, start=lo, end=hi,
                          size=max(hi - lo, 1e-6), labelformat=f".{dec}f",   # start == end: one contour
                          labelfont=dict(size=12, color="black")),
            line=dict(width=3, dash="dash"), colorscale=[[0, "black"], [1, "black"]],
            name=vpd.target_label(tkind, lo, hi, dec), showlegend=True,
        ))

    point_in_view = point is not None and t_min <= point[0] <= t_max and rh_min <= point[1] <= rh_max

    if point_in_view:
        t, rh = point
        v = vpd.vpd_matrix([t], [rh], kind, offset)[0, 0]
        hover = f"Selected<br>{t:.1f} °C, {rh:.1f} %<br>{label}: {v:.{dec}f} kPa"
        fig.add_trace(go.Scatter(
            x=[t], y=[rh], mode="markers", name="Selected",
            marker=dict(symbol="star", size=18, color="white",
                        line=dict(color="black", width=2)),
            hovertemplate=hover + "<extra></extra>",
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
    fig.add_trace(go.Scatter(x=rh, y=vpd.vpd_leaf(t_air, rh, t_air + offset), name="Canopy VPD",
                             line=dict(dash="dash"),
                             hovertemplate="RH %{x:.1f} %<br>%{y:.1f} kPa<extra>Canopy VPD</extra>"))
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
