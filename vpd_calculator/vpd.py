"""Scientific core for the VPD calculator.

All functions use degrees Celsius, percent relative humidity and kPa.
Saturation vapour pressure follows FAO-56 (Allen et al., 1998, Eq. 11):

    es(T) = 0.6108 * exp(17.27 * T / (T + 237.3))

Reverse (RH from target VPD) calculations are closed-form, not numerical.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

RH_TOL = 1e-9  # floating-point tolerance for the 0-100% boundary checks
AIR = "air"
LEAF = "leaf"


def saturation_vapour_pressure(t_c):
    """FAO-56 saturation vapour pressure (kPa). Accepts scalars or arrays."""
    t = np.asarray(t_c, dtype=float) if not np.isscalar(t_c) else float(t_c)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def actual_vapour_pressure(t_air, rh):
    """Actual vapour pressure ea = es(T_air) * RH / 100 (kPa)."""
    return saturation_vapour_pressure(t_air) * np.asarray(rh, dtype=float) / 100.0 \
        if not np.isscalar(rh) else saturation_vapour_pressure(t_air) * rh / 100.0


def leaf_temperature(t_air, offset: float = 0.0, measured: Optional[float] = None):
    """Leaf temperature from an offset (default) or a directly measured value."""
    return measured if measured is not None else t_air + offset


def vpd_air(t_air, rh):
    """VPD_air = es(T_air) - ea (kPa)."""
    return saturation_vapour_pressure(t_air) - actual_vapour_pressure(t_air, rh)


def vpd_leaf(t_air, rh, t_leaf=None):
    """VPD_leaf = es(T_leaf) - ea (kPa). Defaults to T_leaf = T_air."""
    t_leaf = t_air if t_leaf is None else t_leaf
    return saturation_vapour_pressure(t_leaf) - actual_vapour_pressure(t_air, rh)


def rh_for_air_vpd(t_air, target_vpd):
    """RH (%) giving the target air VPD: 100 * (1 - VPD / es(T_air)). Unclamped."""
    return 100.0 * (1.0 - target_vpd / saturation_vapour_pressure(t_air))


def rh_for_leaf_vpd(t_air, target_vpd, t_leaf=None):
    """RH (%) giving the target leaf VPD: 100 * (es(T_leaf) - VPD) / es(T_air). Unclamped."""
    t_leaf = t_air if t_leaf is None else t_leaf
    return 100.0 * (saturation_vapour_pressure(t_leaf) - target_vpd) / saturation_vapour_pressure(t_air)


def rh_for_target(t_air, target_vpd, kind: str = AIR, t_leaf=None):
    if kind == AIR:
        return rh_for_air_vpd(t_air, target_vpd)
    if kind == LEAF:
        return rh_for_leaf_vpd(t_air, target_vpd, t_leaf)
    raise ValueError(f"kind must be '{AIR}' or '{LEAF}', got {kind!r}")


# --------------------------------------------------------------------------
# Result containers with validation (no silent clamping)
# --------------------------------------------------------------------------
@dataclass
class VPDResult:
    t_air: float
    rh: float
    t_leaf: float
    es_air: float
    es_leaf: float
    ea: float
    vpd_air: float
    vpd_leaf: float
    warnings: list

    def as_dict(self):
        return asdict(self)


def calculate_vpd(t_air: float, rh: float, offset: float = 0.0,
                  measured_leaf: Optional[float] = None) -> VPDResult:
    """Mode A: forward calculation."""
    t_leaf = leaf_temperature(t_air, offset, measured_leaf)
    warnings = []
    if not (0.0 <= rh <= 100.0):
        warnings.append(f"RH = {rh:.2f}% is outside the physical range 0-100%.")
    es_a = float(saturation_vapour_pressure(t_air))
    es_l = float(saturation_vapour_pressure(t_leaf))
    ea = es_a * rh / 100.0
    v_leaf = es_l - ea
    if v_leaf < 0:
        warnings.append(
            f"Leaf VPD is negative ({v_leaf:.3f} kPa): the air is supersaturated relative to "
            "the leaf surface, so condensation on the leaf is possible."
        )
    return VPDResult(t_air, rh, t_leaf, es_a, es_l, ea, es_a - ea, v_leaf, warnings)


@dataclass
class RHResult:
    t_air: float
    t_leaf: float
    kind: str
    target_vpd: float
    rh: float                  # unclamped value
    attainable: bool
    message: str
    vpd_air: float
    vpd_leaf: float
    warnings: list

    def as_dict(self):
        return asdict(self)


def calculate_required_rh(t_air: float, target_vpd: float, kind: str = AIR,
                          offset: float = 0.0,
                          measured_leaf: Optional[float] = None) -> RHResult:
    """Mode B: RH required to reach a target air or leaf VPD (closed form)."""
    t_leaf = leaf_temperature(t_air, offset, measured_leaf)
    rh = float(rh_for_target(t_air, target_vpd, kind, t_leaf))
    es_a = float(saturation_vapour_pressure(t_air))
    es_l = float(saturation_vapour_pressure(t_leaf))
    ea = es_a * rh / 100.0
    attainable = -RH_TOL <= rh <= 100.0 + RH_TOL
    warnings = []
    if attainable:
        msg = "Target is attainable."
    else:
        ref = es_a if kind == AIR else es_l
        if kind == AIR:
            lo, hi = 0.0, es_a
        else:
            lo, hi = es_l - es_a, es_l
        if rh > 100:
            msg = (f"Unattainable: the target {kind} VPD of {target_vpd:.3f} kPa is below the "
                   f"minimum reachable VPD ({lo:.3f} kPa at 100% RH) for these temperatures "
                   f"(would need RH = {rh:.2f}%).")
        else:
            msg = (f"Unattainable: the target {kind} VPD of {target_vpd:.3f} kPa exceeds the "
                   f"maximum reachable VPD ({hi:.3f} kPa at 0% RH) for these temperatures "
                   f"(would need RH = {rh:.2f}%).")
    v_leaf = es_l - ea
    if v_leaf < 0:
        warnings.append(f"Leaf VPD is negative ({v_leaf:.3f} kPa): condensation on the leaf is possible.")
    return RHResult(t_air, t_leaf, kind, target_vpd, rh, attainable, msg, es_a - ea, v_leaf, warnings)


def rh_range_for_vpd_range(t_air: float, vpd_low: float, vpd_high: float, kind: str = AIR,
                           offset: float = 0.0, measured_leaf: Optional[float] = None) -> dict:
    """RH interval corresponding to a VPD interval (higher VPD <-> lower RH).

    Returns unclamped limits plus the portion that is physically attainable
    (None if the intervals do not overlap).
    """
    if vpd_low > vpd_high:
        raise ValueError("Lower VPD limit must not exceed the upper limit.")
    t_leaf = leaf_temperature(t_air, offset, measured_leaf)
    rh_at_low_vpd = float(rh_for_target(t_air, vpd_low, kind, t_leaf))   # upper RH
    rh_at_high_vpd = float(rh_for_target(t_air, vpd_high, kind, t_leaf))  # lower RH
    lo, hi = max(rh_at_high_vpd, 0.0), min(rh_at_low_vpd, 100.0)
    attainable = lo <= hi
    return {
        "rh_min_raw": rh_at_high_vpd,
        "rh_max_raw": rh_at_low_vpd,
        "rh_min": lo if attainable else None,
        "rh_max": hi if attainable else None,
        "attainable": attainable,
        "fully_attainable": attainable and rh_at_high_vpd >= 0 and rh_at_low_vpd <= 100,
    }


def classify_vpd(value: float, low: float, high: float) -> str:
    """'below', 'inside' or 'above' a user-defined interval."""
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "inside"


# --------------------------------------------------------------------------
# Grids
# --------------------------------------------------------------------------
def vpd_grid(t_min: float, t_max: float, rh_min: float, rh_max: float,
             t_step: float = 0.5, rh_step: float = 1.0, kind: str = AIR,
             offset: float = 0.0) -> pd.DataFrame:
    """Long-format table of temperature x RH with air and leaf VPD."""
    temps = np.arange(t_min, t_max + t_step / 2, t_step)
    rhs = np.arange(rh_min, rh_max + rh_step / 2, rh_step)
    tt, rr = np.meshgrid(temps, rhs)
    es_a = saturation_vapour_pressure(tt)
    ea = es_a * rr / 100.0
    df = pd.DataFrame({
        "temperature_C": tt.ravel(),
        "RH_percent": rr.ravel(),
        "leaf_temperature_C": (tt + offset).ravel(),
        "es_kPa": es_a.ravel(),
        "ea_kPa": ea.ravel(),
        "VPD_air_kPa": (es_a - ea).ravel(),
        "VPD_leaf_kPa": (saturation_vapour_pressure(tt + offset) - ea).ravel(),
    })
    return df


def vpd_matrix(temps, rhs, kind: str = AIR, offset: float = 0.0) -> np.ndarray:
    """2-D array (len(rhs) x len(temps)) of VPD for heatmaps."""
    tt, rr = np.meshgrid(np.asarray(temps, float), np.asarray(rhs, float))
    ea = saturation_vapour_pressure(tt) * rr / 100.0
    t_ref = tt if kind == AIR else tt + offset
    return saturation_vapour_pressure(t_ref) - ea


# --------------------------------------------------------------------------
# Day / night treatments
# --------------------------------------------------------------------------
TREATMENTS = {
    "Control 1": (22.0, 22.0),
    "Control 2": (22.0, 17.0),
    "Warming 1": (33.0, 33.0),
    "Warming 2": (33.0, 28.0),
}


def treatment_table(treatments: dict, mode: str, value_day: float, value_night: float,
                    kind: str = AIR, offset_day: float = 0.0,
                    offset_night: float = 0.0) -> pd.DataFrame:
    """Compare treatments.

    mode='rh'  : value_* are RH (%) -> VPD is computed.
    mode='vpd' : value_* are target VPD (kPa) -> required RH is computed
                 (so the same target is held across temperature treatments).
    """
    rows = []
    for name, (td, tn) in treatments.items():
        for period, t, val, off in (("Day", td, value_day, offset_day),
                                    ("Night", tn, value_night, offset_night)):
            if mode == "rh":
                r = calculate_vpd(t, val, off)
                rows.append({"Treatment": name, "Period": period, "Temperature (°C)": t,
                             "Leaf temperature (°C)": r.t_leaf, "RH (%)": val,
                             "Air VPD (kPa)": r.vpd_air, "Leaf VPD (kPa)": r.vpd_leaf,
                             "Attainable": 0 <= val <= 100, "Note": "; ".join(r.warnings)})
            elif mode == "vpd":
                r = calculate_required_rh(t, val, kind, off)
                rows.append({"Treatment": name, "Period": period, "Temperature (°C)": t,
                             "Leaf temperature (°C)": r.t_leaf, f"Target {kind} VPD (kPa)": val,
                             "RH (%)": r.rh, "Air VPD (kPa)": r.vpd_air,
                             "Leaf VPD (kPa)": r.vpd_leaf, "Attainable": r.attainable,
                             "Note": r.message if not r.attainable else "; ".join(r.warnings)})
            else:
                raise ValueError("mode must be 'rh' or 'vpd'")
    return pd.DataFrame(rows)
