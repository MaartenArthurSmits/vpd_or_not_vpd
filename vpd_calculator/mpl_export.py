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

def heatmap_mpl(t_min, t_max, rh_min, rh_max, kind=vpd.LEAF, offset=0.0, colorscale=rangecolor.DEFAULT_PALETTE,
                contour_step=0.5, z_max=None, point=None, target=None,
                figsize=(10.0, 6.5), target_kind=None, anchor=None) -> Figure:
    """Temperature x RH heatmap with labelled contours, acceptable-range boundaries and selected point.

    `anchor`: (low, high) acceptable range that positions the palette (see rangecolor.mapping); `target`: the dashed
    boundary lines (no colour band is drawn). Same colour stops as the interactive chart.
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
    vmax = float(z_max) if z_max else float(z.max())

    fig = Figure(figsize=figsize, constrained_layout=True)
    ax = fig.subplots()
    cmap = LinearSegmentedColormap.from_list("range_palette", rangecolor.stops(colorscale, m), N=1024)
    mesh = ax.pcolormesh(temps, rhs, z, cmap=cmap, norm=Normalize(m["cmin"], m["cmax"], clip=True), shading="auto",
                         rasterized=True)
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    if m["anchored"]:
        tk = rangecolor.ticks(m)                      # numbers only here: long tick labels squeeze the figure
        cbar.set_ticks([v for v, _ in tk])
        cbar.set_ticklabels([f"{v:.2f}" for v, _ in tk])
    cbar.set_label(f"{label} (kPa)")

    zero_drawn = kind == vpd.LEAF and vpd.zero_boundary_in_range(z)
    levels = np.arange(np.ceil(z.min() / contour_step) * contour_step, vmax + contour_step / 2, contour_step)
    levels = levels[levels > z.min() + 1e-9]          # a contour on the data minimum is only an edge artefact
    if zero_drawn:
        levels = levels[np.abs(levels) > 1e-9]        # no ordinary zero contour over the saturation boundary
    if len(levels):
        cs = ax.contour(temps, rhs, z, levels=levels, colors="black", linewidths=0.6, alpha=0.6)
        ax.clabel(cs, fmt=f"%.{dec}f", fontsize=8)

    handles = []
    if zero_drawn:
        ax.contour(temps, rhs, z, levels=[0.0], colors=vpd.ZERO_COLOUR, linewidths=1.3, linestyles=":")
        handles.append(Line2D([], [], color=vpd.ZERO_COLOUR, linewidth=1.3, linestyle=":", label=vpd.ZERO_LABEL))
    if target is not None:
        lo, hi = target
        tl = sorted({float(lo), float(hi)})
        ct = ax.contour(temps, rhs, zt, levels=tl, colors="black", linewidths=2.0, linestyles="--")
        ax.clabel(ct, fmt=f"%.{dec}f", fontsize=9)
        handles.append(Line2D([], [], color="black", linestyle="--", linewidth=2.0,
                              label=vpd.target_label(tkind, lo, hi, dec)))
    if m["anchored"]:
        lut = rangecolor.palette_lut(colorscale)
        handles += [Line2D([], [], marker="v", color=lut[0], markeredgecolor="black", linestyle="none",
                           label="Below range: VPD under the lower limit"),
                    Line2D([], [], marker="^", color=lut[-1], markeredgecolor="black", linestyle="none",
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
                  ncol=min(len(entries), 3 if len(entries) <= 4 else 2), frameon=True, fontsize=9)

    ax.set_xlim(t_min, t_max)
    ax.set_ylim(rh_min, rh_max)
    ax.set_xlabel("Air temperature (°C)")
    ax.set_ylabel("Relative humidity (%)")
    ax.set_title(f"{label} (kPa) as a function of temperature and relative humidity", fontsize=12)
    notes = []
    if kind == vpd.LEAF:
        sign = "−" if offset < 0 else "+"
        notes.append(f"Canopy VPD assumes one constant leaf-air offset of {offset:+.1f} °C: "
                     f"leaf temperature = air temperature {sign} {abs(offset):.1f} °C throughout the chart.")
    if zero_drawn:
        notes.append("Negative canopy VPD (beyond the saturation boundary) indicates possible condensation.")
    if m["anchored"]:
        notes.append(rangecolor.EXPLANATION)
    if colorscale == rangecolor.DEFAULT_PALETTE:
        notes.append(rangecolor.PALETTE_NOTE)
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
