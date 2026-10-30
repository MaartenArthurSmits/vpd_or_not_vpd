"""Static, publication-quality figures with Matplotlib (Agg backend).

No browser, Chrome or Chromium is needed. Figures are built on `matplotlib.figure.Figure`
directly (no pyplot), so rendering is safe inside the Streamlit server.
"""

from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import rangecolor  # noqa: E402
import vpd  # noqa: E402

CMAPS = {  # app colour-scale names -> Matplotlib colormaps
    "RdYlBu_r": "RdYlBu_r", "Viridis": "viridis", "Turbo": "turbo", "Cividis": "cividis",
    "Plasma": "plasma", "YlGnBu": "YlGnBu", "Spectral_r": "Spectral_r", "Greys": "Greys",
}


def heatmap_mpl(t_min, t_max, rh_min, rh_max, kind=vpd.AIR, offset=0.0, colorscale="RdYlBu_r",
                contour_step=0.5, z_max=None, point=None, target=None,
                figsize=(10.0, 6.5), target_kind=None, range_colour=False) -> Figure:
    """Temperature x RH heatmap with labelled contours, target range and selected point.

    Colours follow `kind`; the target shading/contours follow `target_kind` (default: `kind`).
    `range_colour`: colour canopy VPD by distance from the canopy target range (see rangecolor).
    """
    temps = np.arange(t_min, t_max + 1e-9, 0.25)
    rhs = np.arange(rh_min, rh_max + 1e-9, 0.5)
    z = vpd.vpd_matrix(temps, rhs, kind, offset)
    label = "Air VPD" if kind == vpd.AIR else "Canopy VPD"
    vmin = float(np.floor(z.min() * 2) / 2) if z.min() < 0 else 0.0
    vmax = float(z_max) if z_max else float(z.max())
    tkind = kind if target_kind is None else target_kind
    zt = z if tkind == kind else vpd.vpd_matrix(temps, rhs, tkind, offset)

    rc = bool(range_colour and kind == vpd.LEAF and target is not None and tkind == vpd.LEAF)
    dec = 2 if rc else 1
    fig = Figure(figsize=figsize, constrained_layout=True)
    ax = fig.subplots()
    if rc:
        lo_c, hi_c = target
        cmin, cmax = rangecolor.domain(lo_c, hi_c)
        cmap = LinearSegmentedColormap.from_list("roma_r", list(rangecolor.LUT), N=256)
        mesh = ax.pcolormesh(temps, rhs, z, cmap=cmap, norm=Normalize(cmin, cmax, clip=True), shading="auto",
                             rasterized=True)
        cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
        cticks = [cmin, lo_c] + ([] if vpd.is_point_target(lo_c, hi_c) else [hi_c]) + [cmax]
        cbar.set_ticks(cticks)
        cbar.set_ticklabels([f"{v:.2f}" for v in cticks])
    else:
        mesh = ax.pcolormesh(temps, rhs, z, cmap=CMAPS.get(colorscale, "RdYlBu_r"), vmin=vmin, vmax=vmax,
                             shading="auto", rasterized=True)
        cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label(f"{label} (kPa)")

    start = np.ceil(z.min() / contour_step) * contour_step
    levels = np.arange(start, vmax + contour_step / 2, contour_step)
    levels = levels[levels > z.min() + 1e-9]          # a contour on the data minimum is only an edge artefact
    if len(levels):
        cs = ax.contour(temps, rhs, z, levels=levels, colors="black", linewidths=0.6, alpha=0.6)
        ax.clabel(cs, fmt=f"%.{dec}f", fontsize=8)

    handles = []
    zero_drawn = kind == vpd.LEAF and vpd.zero_boundary_in_range(z)
    if zero_drawn:
        ax.contour(temps, rhs, z, levels=[0.0], colors=vpd.ZERO_COLOUR, linewidths=3.2, linestyles="-")
        handles.append(Line2D([], [], color=vpd.ZERO_COLOUR, linewidth=3.2, label=vpd.ZERO_LABEL))
    if target is not None:
        lo, hi = target
        if hi > lo and not rc:
            ax.contourf(temps, rhs, zt, levels=[lo, hi], colors=["white"], alpha=0.35)
        tl = sorted({float(lo), float(hi)})
        ct = ax.contour(temps, rhs, zt, levels=tl, colors="black", linewidths=2.0, linestyles="--")
        ax.clabel(ct, fmt=f"%.{dec}f", fontsize=9)
        handles.append(Line2D([], [], color="black", linestyle="--", linewidth=2.0,
                              label=vpd.target_label(tkind, lo, hi, dec)))
    if rc:
        handles += [Line2D([], [], marker="v", color=rangecolor.LOW_COLOUR, markeredgecolor="black", linestyle="none",
                           label="Below range: VPD under the lower limit"),
                    Line2D([], [], marker="^", color=rangecolor.HIGH_COLOUR, markeredgecolor="black", linestyle="none",
                           label="Above range: VPD over the upper limit")]
    point_in_view = point is not None and t_min <= point[0] <= t_max and rh_min <= point[1] <= rh_max
    if point_in_view:
        t, rh = point
        ax.plot([t], [rh], marker="*", markersize=16, markerfacecolor="white",
                markeredgecolor="black", markeredgewidth=1.5, linestyle="none", zorder=6,
                label=f"Selected: {t:.1f} °C, {rh:.1f} %")
    entries = ax.get_legend_handles_labels()[0] + handles
    if entries:
        ax.legend(handles=entries, loc="upper center", bbox_to_anchor=(0.5, -0.14),   # below the axis label
                  ncol=min(len(entries), 3), frameon=True, fontsize=9)

    ax.set_xlim(t_min, t_max)
    ax.set_ylim(rh_min, rh_max)
    ax.set_xlabel("Air temperature (°C)")
    ax.set_ylabel("Relative humidity (%)")
    ax.set_title(f"{label} (kPa) as a function of temperature and relative humidity", fontsize=12)
    notes = []
    if kind == vpd.LEAF:
        sign = "−" if offset < 0 else "+"
        notes.append(f"Leaf VPD assumes one constant leaf-air offset of {offset:+.1f} °C: "
                     f"leaf temperature = air temperature {sign} {abs(offset):.1f} °C throughout the chart.")
    if zero_drawn:
        notes.append("Negative leaf VPD (beyond the saturation line) indicates possible condensation.")
    if rc:
        notes.append(rangecolor.EXPLANATION)
    notes.append("Saturation vapour pressure: FAO-56 (Allen et al., 1998), Eq. 11.")
    # Captions are wrapped and placed in a figure-level label, so constrained layout reserves their space.
    fig.supxlabel("\n".join(textwrap.fill(n, width=125) for n in notes), x=0.01, ha="left", fontsize=8.5)
    return fig


def reference_mpl(curves, show_johnston=False, figsize=(8.0, 5.0)) -> Figure:
    """Air VPD vs RH, one colour per temperature; Johnston et al. (2025) dashed."""
    fig = Figure(figsize=figsize, constrained_layout=True)
    ax = fig.subplots()
    for t, d in curves.groupby("temperature_C", sort=True):
        line, = ax.plot(d["RH_percent"], d["VPD_FAO56_kPa"], label=f"{t:g} °C (FAO-56)")
        if show_johnston:
            ax.plot(d["RH_percent"], d["VPD_Johnston_kPa"], linestyle="--", linewidth=1.2,
                    color=line.get_color(), label=f"{t:g} °C (Johnston et al. 2025)")
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Relative humidity (%)")
    ax.set_ylabel("Air VPD (kPa)")
    ax.set_title("Air VPD vs relative humidity (leaf offset 0 °C)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    return fig


def to_bytes(fig: Figure, fmt: str = "png", dpi: int = 300) -> bytes:
    """Render a figure to PNG/PDF/SVG bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi)
    return buf.getvalue()
