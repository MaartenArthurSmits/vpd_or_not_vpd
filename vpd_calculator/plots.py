"""Plotly figure builders for the VPD calculator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import vpd

COLORSCALES = ["RdYlBu_r", "Viridis", "Turbo", "Cividis", "Plasma", "YlGnBu", "Spectral_r", "Greys"]


def heatmap_figure(t_min, t_max, rh_min, rh_max, kind=vpd.AIR, offset=0.0,
                   colorscale="RdYlBu_r", contour_step=0.5, z_max=None,
                   point=None, target=None, template=None,
                   width=None, height=650) -> go.Figure:
    """Temperature x RH heatmap with labelled contours.

    point  : (t_air, rh) selected state or None
    target : (vpd_low, vpd_high) user-defined interval or None
    """
    temps = np.arange(t_min, t_max + 1e-9, 0.25)
    rhs = np.arange(rh_min, rh_max + 1e-9, 0.5)
    z = vpd.vpd_matrix(temps, rhs, kind, offset)
    label = "Air VPD" if kind == vpd.AIR else "Leaf VPD"
    zmin = float(np.floor(z.min() * 2) / 2) if z.min() < 0 else 0.0
    zmax = float(z_max) if z_max else float(z.max())

    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=z, x=temps, y=rhs, colorscale=colorscale, zmin=zmin, zmax=zmax,
        colorbar=dict(title=dict(text=f"{label} (kPa)")),
        hovertemplate="Temperature: %{x:.2f} °C<br>RH: %{y:.1f} %<br>"
                      + label + ": %{z:.3f} kPa<extra></extra>",
        name=label,
    ))

    if target is not None:
        lo, hi = target
        mask = np.where((z >= lo) & (z <= hi), 1.0, np.nan)
        fig.add_trace(go.Heatmap(
            z=mask, x=temps, y=rhs, zmin=0, zmax=1, showscale=False, hoverinfo="skip",
            colorscale=[[0, "rgba(255,255,255,0.45)"], [1, "rgba(255,255,255,0.45)"]],
        ))

    start = np.ceil(z.min() / contour_step) * contour_step
    fig.add_trace(go.Contour(
        z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip", ncontours=None,
        contours=dict(coloring="lines", showlabels=True, start=start, end=zmax,
                      size=contour_step, labelfont=dict(size=11, color="black"),
                      labelformat=".1f"),
        line=dict(width=1), colorscale=[[0, "rgba(0,0,0,0.55)"], [1, "rgba(0,0,0,0.55)"]],
    ))

    if target is not None:
        lo, hi = target
        fig.add_trace(go.Contour(
            z=z, x=temps, y=rhs, showscale=False, hoverinfo="skip",
            contours=dict(coloring="lines", showlabels=True, start=lo, end=hi,
                          size=max(hi - lo, 1e-6), labelformat=".2f",
                          labelfont=dict(size=12, color="black")),
            line=dict(width=3, dash="dash"), colorscale=[[0, "black"], [1, "black"]], name="Target VPD",
        ))

    if point is not None:
        t, rh = point
        if t_min <= t <= t_max and rh_min <= rh <= rh_max:
            v = vpd.vpd_matrix([t], [rh], kind, offset)[0, 0]
            fig.add_trace(go.Scatter(
                x=[t], y=[rh], mode="markers", name="Selected",
                marker=dict(symbol="star", size=18, color="white",
                            line=dict(color="black", width=2)),
                hovertemplate=f"Selected<br>{t:.2f} °C, {rh:.1f} %<br>{label}: {v:.3f} kPa<extra></extra>",
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
                             hovertemplate="RH %{x:.1f} %<br>%{y:.3f} kPa<extra>Air VPD</extra>"))
    fig.add_trace(go.Scatter(x=rh, y=vpd.vpd_leaf(t_air, rh, t_air + offset), name="Leaf VPD",
                             line=dict(dash="dash"),
                             hovertemplate="RH %{x:.1f} %<br>%{y:.3f} kPa<extra>Leaf VPD</extra>"))
    if rh_range and rh_range.get("attainable"):
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


def timeseries_figure(clean: pd.DataFrame, interval=None, kind=vpd.AIR, template=None) -> go.Figure:
    """VPD, temperature and RH over time for logger data (output of logger_data)."""
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.5, 0.25, 0.25],
                        subplot_titles=("VPD (kPa)", "Temperature (°C)", "Relative humidity (%)"))
    x = clean["time"]
    fig.add_trace(go.Scattergl(x=x, y=clean["VPD_air_kPa"], mode="lines", name="Air VPD",
                               hovertemplate="%{y:.3f} kPa<extra>Air VPD</extra>"), row=1, col=1)
    fig.add_trace(go.Scattergl(x=x, y=clean["VPD_leaf_kPa"], mode="lines", name="Leaf VPD",
                               line=dict(dash="dash"),
                               hovertemplate="%{y:.3f} kPa<extra>Leaf VPD</extra>"), row=1, col=1)
    if interval is not None:
        fig.add_hrect(y0=interval[0], y1=interval[1], row=1, col=1, opacity=0.15,
                      fillcolor="green", line_width=0,
                      annotation_text=f"target {kind} VPD (user-defined)", annotation_position="top left")
    fig.add_trace(go.Scattergl(x=x, y=clean["temperature_C"], mode="lines", name="Air temperature",
                               hovertemplate="%{y:.2f} °C<extra>Air temperature</extra>"), row=2, col=1)
    fig.add_trace(go.Scattergl(x=x, y=clean["RH_percent"], mode="lines", name="RH",
                               hovertemplate="%{y:.1f} %<extra>RH</extra>"), row=3, col=1)
    fig.update_layout(template=template, height=720, margin=dict(l=60, r=20, t=50, b=40),
                      legend=dict(orientation="h", y=-0.08))
    return fig


def treatment_figure(df: pd.DataFrame, rh_label="RH (%)", template=None) -> go.Figure:
    """Grouped comparison of RH and VPD across treatments, coloured by day/night."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=(rh_label, "VPD (kPa): bars = air, diamonds = leaf"),
                        horizontal_spacing=0.12)
    for period in ("Day", "Night"):
        d = df[df.Period == period]
        fig.add_trace(go.Bar(x=d["Treatment"], y=d[rh_label], name=period, legendgroup=period,
                             customdata=d[["Temperature (°C)"]],
                             hovertemplate="%{x} (%{customdata[0]} °C)<br>RH %{y:.2f} %<extra>" + period + "</extra>"),
                      row=1, col=1)
        fig.add_trace(go.Bar(x=d["Treatment"], y=d["Air VPD (kPa)"], name=period, legendgroup=period,
                             showlegend=False,
                             hovertemplate="%{x}<br>Air VPD %{y:.3f} kPa<extra>" + period + "</extra>"),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=d["Treatment"], y=d["Leaf VPD (kPa)"], mode="markers",
                                 legendgroup=period, showlegend=False,
                                 marker=dict(symbol="diamond", size=10, color="black",
                                             line=dict(width=1, color="white")),
                                 hovertemplate="%{x}<br>Leaf VPD %{y:.3f} kPa<extra>" + period + "</extra>"),
                      row=1, col=2)
    fig.add_hline(y=100, line_dash="dot", row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", row=1, col=1)
    fig.update_layout(template=template, barmode="group", height=420,
                      margin=dict(l=60, r=20, t=60, b=50), legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(title_text="%", row=1, col=1)
    fig.update_yaxes(title_text="kPa", row=1, col=2)
    return fig
