"""Shareable-link support: encode/decode calculator settings as URL query parameters.

Pure functions (no Streamlit import) so they can be tested directly. Invalid or
out-of-range values in a link are ignored rather than clamped.
"""

from __future__ import annotations

import math
from typing import Mapping
from urllib.parse import urlencode

APP_URL = "https://vpd-or-not-vpd.streamlit.app/"

MODE_A = "Calculate VPD (from temperature and RH)"
MODE_B = "Calculate required RH (from target VPD)"
OFFSET_METHOD = "Offset from air"
MEASURED_METHOD = "Measured leaf temperature"
AIR_LABEL, LEAF_LABEL = "Air VPD", "Leaf VPD"

# query key -> (session-state key, min, max)
_NUMERIC = {
    "t": ("t_air", -10.0, 60.0),
    "rh": ("rh", 0.0, 100.0),
    "tv": ("target_vpd", -5.0, 10.0),
    "off": ("calc_offset", -10.0, 10.0),
    "lm": ("calc_leaf_meas", -5.0, 50.0),
    "lo": ("vpd_lo", 0.0, 10.0),
    "hi": ("vpd_hi", 0.0, 10.0),
}
_KIND = {"air": AIR_LABEL, "leaf": LEAF_LABEL}


def parse_params(params: Mapping[str, str]) -> dict:
    """Convert query parameters to session-state updates."""
    out: dict = {}
    for q, (key, lo, hi) in _NUMERIC.items():
        if q in params:
            try:
                v = float(params[q])
            except (TypeError, ValueError):
                continue
            if math.isfinite(v) and lo <= v <= hi:
                out[key] = v
    if params.get("m") in ("a", "b"):
        out["mode"] = MODE_A if params["m"] == "a" else MODE_B
    if params.get("k") in _KIND:
        out["target_kind"] = _KIND[params["k"]]
    if params.get("ik") in _KIND:
        out["interval_kind"] = _KIND[params["ik"]]
    if "calc_leaf_meas" in out:
        out["calc_leaf_method"] = MEASURED_METHOD
    elif "calc_offset" in out:
        out["calc_leaf_method"] = OFFSET_METHOD
    return out


def _fmt(x) -> str:
    return format(round(float(x), 4), "g")


def build_params(state: Mapping) -> dict:
    """Convert current settings (session state) to query parameters."""
    p = {
        "m": "a" if state.get("mode", MODE_A) == MODE_A else "b",
        "t": _fmt(state["t_air"]),
        "rh": _fmt(state["rh"]),
        "tv": _fmt(state["target_vpd"]),
        "k": "air" if state.get("target_kind", AIR_LABEL) == AIR_LABEL else "leaf",
        "lo": _fmt(state["vpd_lo"]),
        "hi": _fmt(state["vpd_hi"]),
        "ik": "air" if state.get("interval_kind", AIR_LABEL) == AIR_LABEL else "leaf",
    }
    if state.get("calc_leaf_method", OFFSET_METHOD) == MEASURED_METHOD:
        p["lm"] = _fmt(state["calc_leaf_meas"])
    else:
        p["off"] = _fmt(state["calc_offset"])
    return p


def share_url(state: Mapping, base: str = APP_URL) -> str:
    return f"{base}?{urlencode(build_params(state))}"
