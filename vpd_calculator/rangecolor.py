"""Range-based heatmap colours: the Scientific colour map "roma_r" centred on the acceptable canopy-VPD range.

One specification shared by the Plotly figure, the Matplotlib exports and the generated R script. The complete
256-colour table (assets/roma.txt, reversed) is used unchanged. The colour scale spans a fixed window
[lower - MARGIN, upper + MARGIN] kPa, so its centre is the midpoint (lower + upper) / 2: deep blue is low canopy VPD,
pale green the midpoint of the range, dark brick-red high canopy VPD. The limits of the range are marked by contour
lines, not by a colour band. The window depends only on the selected range, never on the displayed axes.

Colour table: "roma" from the Scientific colour maps by Fabio Crameri (https://doi.org/10.5281/zenodo.8035877),
MIT licence; see assets/roma_NOTICE.txt.
"""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
PALETTE_ID = "roma_r"                  # identifies the palette in the figure-download cache signature
MARGIN = 1.0                           # kPa on each side of the range covered by the colour scale

EXPLANATION = ("Colours show canopy VPD relative to the acceptable range: blue below, pale green at its midpoint, "
               "red above; dashed contours mark its limits.")


def _load():
    rows = [tuple(float(x) for x in line.split())
            for line in (ASSETS / "roma.txt").read_text().splitlines() if line.strip()]
    assert len(rows) == 256 and all(len(r) == 3 for r in rows)
    return rows[::-1]                  # roma_r


LUT = tuple(_load())                   # 256 (r, g, b) in 0-1, low VPD first


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


HEX = tuple(_hex(c) for c in LUT)
LOW_COLOUR, MID_COLOUR, HIGH_COLOUR = HEX[0], HEX[127], HEX[-1]


def domain(lo: float, hi: float):
    """Fixed colour-scale limits (kPa), centred on the midpoint of the range."""
    return lo - MARGIN, hi + MARGIN


def colorscale(lo: float = None, hi: float = None):
    """The 256-colour table as (position 0-1, hex) stops; the kPa window comes from `domain`."""
    return [(i / 255, c) for i, c in enumerate(HEX)]


def colour_for(value: float, lo: float, hi: float):
    """Colour (r, g, b in 0-1) of a canopy VPD for the range [lo, hi], interpolating the table; clamped outside."""
    zmin, zmax = domain(lo, hi)
    x = min(max((value - zmin) / (zmax - zmin), 0.0), 1.0) * 255
    i = min(int(x), 254)
    f = x - i
    return tuple(a + (b - a) * f for a, b in zip(LUT[i], LUT[i + 1]))
