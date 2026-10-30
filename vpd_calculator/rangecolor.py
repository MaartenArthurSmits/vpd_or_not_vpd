"""Heatmap colour palettes and the range-anchored colour mapping.

One specification shared by the Plotly figure, the Matplotlib exports and the generated R script.

Palettes: the default "Blue–green–red" is this calculator's adaptation of ColorBrewer colours (nine anchor colours
interpolated linearly in RGB; see assets/colorbrewer_NOTICE.txt). It is not an unmodified standard palette and is not
claimed to be perceptually uniform. The other choices are the usual Matplotlib maps, with their own colours.

Mapping: with an acceptable range [L, U] and midpoint M, VPD values are positioned on the palette piecewise-linearly:
colour minimum -> 0, L -> 0.40, M -> 0.50, U -> 0.60, colour maximum -> 1 (a single anchor at M for equal limits).
The colour window covers the plotted data and always includes the anchors; every function here is pure and the
Plotly colour scale, the Matplotlib colormap and the R script all take the same (position, colour) stops.
"""

from __future__ import annotations

import numpy as np

DEFAULT_PALETTE = "Blue–green–red"
BREWER_ANCHORS = ((0.00, "#08306B"), (0.20, "#2171B5"), (0.40, "#66C2A5"), (0.50, "#1A9850"), (0.60, "#66BD63"),
                  (0.70, "#A6D96A"), (0.80, "#FDAE61"), (0.90, "#D73027"), (1.00, "#A50026"))
MPL_NAMES = {   # app palette name -> Matplotlib colormap (original colours, not modified)
    "RdYlBu_r": "RdYlBu_r", "Viridis": "viridis", "Turbo": "turbo", "Cividis": "cividis",
    "Plasma": "plasma", "YlGnBu": "YlGnBu", "Spectral_r": "Spectral_r", "Greys": "Greys",
}
PALETTES = [DEFAULT_PALETTE, *MPL_NAMES]
PALETTE_ID = "palette-v2"              # part of the figure-download cache signature
ANCHOR_POSITIONS = (0.0, 0.40, 0.50, 0.60, 1.0)
DELTA = 0.1                            # kPa; minimum distance of the colour limits beyond the range limits

EXPLANATION = ("Colours are positioned by the acceptable range: its lower limit, midpoint and upper limit sit at 40 %, "
               "50 % and 60 % of the palette; dashed lines mark the limits.")
PALETTE_NOTE = ("“Blue–green–red” adapts ColorBrewer colours (Apache-2.0); it is not a standard or "
                "perceptually uniform palette.")


def _rgb(hex_colour: str):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{int(round(min(max(c, 0), 255))):02x}" for c in rgb)


def palette_lut(name: str, n: int = 256):
    """`n` hex colours, evenly spaced in palette position."""
    pos = np.linspace(0.0, 1.0, n)
    if name == DEFAULT_PALETTE:
        xs = [p for p, _ in BREWER_ANCHORS]
        chans = [[_rgb(c)[i] for _, c in BREWER_ANCHORS] for i in range(3)]
        return [_hex(rgb) for rgb in zip(*(np.interp(pos, xs, ch) for ch in chans))]
    from matplotlib import colormaps
    return [_hex(np.array(rgba[:3]) * 255) for rgba in colormaps[MPL_NAMES[name]](pos)]


def mapping(data_min: float, data_max: float, lo=None, hi=None, z_max=None):
    """Colour window and anchors. Without a valid range the palette is simply spread over the data (as before)."""
    if lo is None or hi is None or not (lo <= hi) or not np.isfinite([lo, hi]).all():
        cmin = float(np.floor(data_min * 2) / 2) if data_min < 0 else 0.0
        cmax = float(z_max) if z_max and z_max > cmin else float(data_max)
        if cmax <= cmin:
            cmax = cmin + 1.0
        return dict(cmin=cmin, cmax=cmax, vs=[cmin, cmax], ps=[0.0, 1.0], anchored=False)
    mid = (lo + hi) / 2
    cmin = min(float(data_min), (lo if lo < hi else mid) - DELTA)
    cmax = max(float(data_max), (hi if lo < hi else mid) + DELTA)
    if z_max and z_max > (hi if lo < hi else mid):        # manual colour maximum (must clear the upper anchor)
        cmax = float(z_max)
    if lo < hi:
        vs, ps = [cmin, lo, mid, hi, cmax], list(ANCHOR_POSITIONS)
    else:
        vs, ps = [cmin, mid, cmax], [0.0, 0.5, 1.0]
    return dict(cmin=cmin, cmax=cmax, vs=vs, ps=ps, anchored=True, lo=lo, hi=hi, mid=mid)


def position(value, m: dict):
    """Palette position (0-1) of a VPD value under mapping `m`; clamped at the colour limits."""
    return np.interp(value, m["vs"], m["ps"])


def stops(name: str, m: dict, n: int = 256):
    """(position along the colour bar 0-1, hex) stops for Plotly, Matplotlib and R."""
    lut = palette_lut(name, n)
    ps = np.linspace(0.0, 1.0, n)
    vs = np.interp(ps, m["ps"], m["vs"])                  # VPD at each palette position
    xs = (vs - m["cmin"]) / (m["cmax"] - m["cmin"])
    xs[0], xs[-1] = 0.0, 1.0
    return [(round(float(x), 12), c) for x, c in zip(xs, lut)]


def ticks(m: dict):
    """Colour-bar ticks as (VPD, label) in kPa, including the range limits."""
    out = [(m["cmin"], f"{m['cmin']:.2f}")]
    if m["anchored"]:
        if m["lo"] < m["hi"]:
            out += [(m["lo"], f"{m['lo']:.2f} lower limit"), (m["hi"], f"{m['hi']:.2f} upper limit")]
        else:
            out += [(m["mid"], f"{m['mid']:.2f} target")]
    out.append((m["cmax"], f"{m['cmax']:.2f}"))
    return out
