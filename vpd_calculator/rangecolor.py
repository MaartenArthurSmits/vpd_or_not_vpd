"""Range-based heatmap colours: green inside the acceptable canopy-VPD range, warmer colours with distance outside it.

One specification shared by the Plotly figure, the Matplotlib exports and the generated R script. The mapping is
fixed in kPa: the colour scale always spans [lower - MARGIN, upper + MARGIN], so a given VPD keeps its colour for a
given target whatever the displayed axes. The colours are display choices, not biological stress thresholds.
"""

from __future__ import annotations

GREEN = "#4caf50"                      # same green as the result bars
NEAR_WHITE = "#f4f4ee"
YELLOW = "#ffe500"
ORANGE = "#ff9100"
RED = "#e8201c"
DEEP_RED = "#6e0000"

# (distance outside the range in kPa, colour); inside the inclusive range the colour is GREEN.
DISTANCE_STOPS = ((0.0, NEAR_WHITE), (0.10, NEAR_WHITE), (0.20, YELLOW), (0.30, ORANGE), (0.40, RED), (1.00, DEEP_RED))
MARGIN = 1.0                           # kPa beyond each limit covered by the colour scale (deep red from here on)
EPS = 1e-6                             # kPa; width of the green/near-white transition at the limits
INSIDE_TOL = 1e-9                      # same inclusive tolerance as vpd.VPD_CLASSIFY_TOL

EXPLANATION = "Green shows the acceptable range; warmer colours show increasing distance outside it."


def _rgb(hex_colour: str):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(c):02x}" for c in rgb)


def _mix(c0: str, c1: str, f: float) -> str:
    a, b = _rgb(c0), _rgb(c1)
    return _hex(tuple(x + (y - x) * f for x, y in zip(a, b)))


def distance(value: float, lo: float, hi: float) -> float:
    return max(lo - value, 0.0, value - hi)


def colour_for(value: float, lo: float, hi: float) -> str:
    """Display colour of a canopy VPD for the range [lo, hi] (inclusive; equal limits are a target, not a band)."""
    d = distance(value, lo, hi)
    if lo < hi and d <= INSIDE_TOL:
        return GREEN
    for (d0, c0), (d1, c1) in zip(DISTANCE_STOPS, DISTANCE_STOPS[1:]):
        if d <= d1:
            return _mix(c0, c1, (d - d0) / (d1 - d0))
    return DEEP_RED


def domain(lo: float, hi: float):
    """Fixed colour-scale limits (kPa)."""
    return lo - MARGIN, hi + MARGIN


def vpd_stops(lo: float, hi: float):
    """Colour stops as (VPD kPa, colour), increasing in VPD, over `domain(lo, hi)`."""
    below = [(lo - d, c) for d, c in reversed(DISTANCE_STOPS[1:])]               # deep red ... near-white at lo - 0.10
    above = [(hi + d, c) for d, c in DISTANCE_STOPS[1:]]
    if lo < hi:
        return below + [(lo - EPS, NEAR_WHITE), (lo, GREEN), (hi, GREEN), (hi + EPS, NEAR_WHITE)] + above
    return below + above                                                          # single target: no green band


def colorscale(lo: float, hi: float):
    """The same stops normalised to 0-1 for Plotly, Matplotlib and R."""
    zmin, zmax = domain(lo, hi)
    return [(round((v - zmin) / (zmax - zmin), 10), c) for v, c in vpd_stops(lo, hi)]
