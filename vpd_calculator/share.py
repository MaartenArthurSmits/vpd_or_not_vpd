"""Shareable-link support: encode/decode calculator settings as URL query parameters.

Pure functions (no Streamlit import) so they can be tested directly. Invalid or
out-of-range values in a link are ignored rather than clamped.
"""

from __future__ import annotations

import json
import math
from typing import Mapping
from urllib.parse import urlencode

import presets

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
    # heatmap axis limits and colour-scale maximum (0 = automatic); bounds follow the control limits
    "htmin": ("hm_tmin", -10.0, 60.0),
    "htmax": ("hm_tmax", -10.0, 60.0),
    "hrmin": ("hm_rhmin", 0.0, 99.0),
    "hrmax": ("hm_rhmax", 1.0, 100.0),
    "hz": ("hm_zmax", 0.0, 20.0),
}
_KIND = {"air": AIR_LABEL, "leaf": LEAF_LABEL}

# Day/night settings: period -> query-key prefix. Per period the keys are
#   <p>t air temperature, <p>off leaf offset, <p>lo / <p>hi VPD limits, <p>k air|leaf, <p>p preset id.
# Bounds equal the interface input bounds; invalid values are ignored (not clamped), as for the main settings.
_PERIODS = {"day": "d", "night": "n"}
_PERIOD_NUMERIC = {  # query suffix -> (session-state key pattern, min, max)
    "t": ("dn_t_{p}", -10.0, 60.0),
    "off": ("dn_off_{p}", -10.0, 10.0),
    "lo": ("dn_lo_{p}", 0.0, 10.0),
    "hi": ("dn_hi_{p}", 0.0, 10.0),
}
# Heatmap choices. The colour-scale names must match plots.COLORSCALES (checked by a test); the contour
# spacing options match the "Contour spacing (kPa)" control. The heatmap has no separate grid-resolution control.
_COLORSCALES = ["RdYlBu_r", "Viridis", "Turbo", "Cividis", "Plasma", "YlGnBu", "Spectral_r", "Greys"]
_CONTOUR_STEPS = [0.1, 0.2, 0.5, 1.0]
HEATMAP_DEFAULTS = {"hm_tmin": 10.0, "hm_tmax": 40.0, "hm_rhmin": 10.0, "hm_rhmax": 100.0, "hm_zmax": 0.0,
                    "hm_cs": "RdYlBu_r", "hm_step": 0.5, "hm_target": True, "hm_point": True}   # = widget defaults
_HEATMAP_NUMERIC = ("htmin", "htmax", "hrmin", "hrmax", "hz")
_BOOL_KEYS = {"hg": "hm_target", "hp": "hm_point"}      # highlight target range / mark selected point
# Preset identity (needed because different presets can have identical numerical ranges).
_STAGE_IDS = {"seed": "Seedlings / propagation", "veg": "Vegetative", "flow": "Flowering",
              "gen": "General horticulture", "custom": presets.CUSTOM}


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
    if params.get("hk") in _KIND:
        out["hm_kind"] = _KIND[params["hk"]]
    if params.get("hcs") in _COLORSCALES:
        out["hm_cs"] = params["hcs"]
    if "hst" in params:
        try:
            step = float(params["hst"])
        except (TypeError, ValueError):
            step = None
        if step is not None and math.isfinite(step):
            match = [s for s in _CONTOUR_STEPS if abs(s - step) < 1e-9]
            if match:
                out["hm_step"] = match[0]
    for q, key in _BOOL_KEYS.items():
        if params.get(q) in ("0", "1"):
            out[key] = params[q] == "1"
    for period, pre in _PERIODS.items():
        for suffix, (pattern, lo, hi) in _PERIOD_NUMERIC.items():
            q = pre + suffix
            if q in params:
                try:
                    v = float(params[q])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(v) and lo <= v <= hi:
                    out[pattern.format(p=period)] = v
        if params.get(pre + "k") in _KIND:
            out[f"dn_kind_{period}"] = _KIND[params[pre + "k"]]
        if params.get(pre + "p") in _STAGE_IDS:
            out[f"dn_preset_{period}"] = _STAGE_IDS[params[pre + "p"]]   # identity only; limits are separate
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
    ids = {name: i for i, name in _STAGE_IDS.items()}
    for period, pre in _PERIODS.items():
        if f"dn_t_{period}" not in state:        # day/night settings not initialised (e.g. unit tests)
            continue
        for suffix, (pattern, _lo, _hi) in _PERIOD_NUMERIC.items():
            p[pre + suffix] = _fmt(state[pattern.format(p=period)])
        p[pre + "k"] = "air" if state.get(f"dn_kind_{period}", AIR_LABEL) == AIR_LABEL else "leaf"
        preset = state.get(f"dn_preset_{period}")
        if preset in ids:
            p[pre + "p"] = ids[preset]
    # Heatmap controls. Their widgets are created after this runs on a fresh session, so fall back to the
    # control defaults (HEATMAP_DEFAULTS) until the widgets exist.
    for q in _HEATMAP_NUMERIC:
        key = _NUMERIC[q][0]
        p[q] = _fmt(state.get(key, HEATMAP_DEFAULTS[key]))
    p["hk"] = "air" if state.get("hm_kind", AIR_LABEL) == AIR_LABEL else "leaf"
    p["hcs"] = state.get("hm_cs", HEATMAP_DEFAULTS["hm_cs"])
    p["hst"] = _fmt(state.get("hm_step", HEATMAP_DEFAULTS["hm_step"]))
    for q, key in _BOOL_KEYS.items():
        p[q] = "1" if state.get(key, HEATMAP_DEFAULTS[key]) else "0"
    return p


# Every query-parameter name parse_params understands (derived from the tables above).
RECOGNIZED_PARAMS = (
    set(_NUMERIC) | {"m", "k", "ik", "hk", "hcs", "hst", "hg", "hp"}
    | {pre + suffix for pre in _PERIODS.values() for suffix in (*_PERIOD_NUMERIC, "k", "p")}
)


def validate_setup(raw) -> tuple[dict | None, str | None]:
    """Strictly validate a setup file (bytes or str). Returns (parameters, None) or (None, error message).

    Unlike links, an invalid value for a recognized parameter is an error (nothing is applied). Unknown
    parameter keys are ignored. The returned parameters only contain recognized keys, as strings.
    """
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
        doc = json.loads(text)
    except (UnicodeDecodeError, ValueError) as exc:
        return None, f"The file is not valid JSON ({exc.__class__.__name__}: {str(exc)[:80]})."
    if not isinstance(doc, dict):
        return None, "The file is not a VPD calculator setup (the top level must be a JSON object)."
    if doc.get("format") != SETUP_FORMAT:
        return None, f"Unsupported file format: expected \"{SETUP_FORMAT}\"."
    version = doc.get("schema_version")
    if isinstance(version, bool) or version != SETUP_SCHEMA_VERSION:
        return None, f"Unsupported schema_version: this app reads version {SETUP_SCHEMA_VERSION}."
    params = doc.get("parameters")
    if not isinstance(params, dict):
        return None, "The setup has no \"parameters\" object."
    clean: dict = {}
    problems = []
    for key, value in params.items():
        if key not in RECOGNIZED_PARAMS:
            continue                                            # unknown keys are ignored
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            problems.append(key)
            continue
        text_value = value if isinstance(value, str) else format(value, "g")
        if not parse_params({key: text_value}):
            problems.append(key)
            continue
        clean[key] = text_value
    if problems:
        return None, "Invalid value for: " + ", ".join(sorted(problems)) + ". Nothing was changed."
    return clean, None


SETUP_FORMAT = "vpd-calculator-setup"
SETUP_SCHEMA_VERSION = 1
SETUP_FILENAME = "vpd-setup.json"


def setup_document(state: Mapping) -> dict:
    """Downloadable setup document. `parameters` is exactly the shared-link serialization (build_params)."""
    return {"format": SETUP_FORMAT, "schema_version": SETUP_SCHEMA_VERSION, "parameters": build_params(state)}


def setup_json(state: Mapping) -> str:
    return json.dumps(setup_document(state), indent=2) + "\n"


def share_url(state: Mapping, base: str = APP_URL) -> str:
    return f"{base}?{urlencode(build_params(state))}"
