"""Reference data and comparison helpers for the in-app "Scientific validation" section.

Everything here that is labelled "application" calls the production functions in
`vpd.py`; nothing re-implements the FAO-56 equation. The Johnston et al. (2025)
equation is a separate, independent formula used only as an alternative reference.

Sources
-------
FAO-56 Annex 2, Table 2.3 (Allen et al., 1998): https://www.fao.org/4/x0490e/x0490e0j.htm
Johnston et al. (2025): https://doi.org/10.1029/2024JG008146
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import vpd

# --- Published saturation vapour pressure (kPa), FAO-56 Table 2.3, 3 d.p. -------------
FAO_ES_TABLE = {15: 1.705, 20: 2.338, 22: 2.644, 25: 3.168, 30: 4.243, 33: 5.030, 35: 5.623}
# Half a unit of the last published decimal (0.0005) plus a small float margin.
TOL_ES_KPA = 5.0e-4 + 1e-9

# --- Reference VPD cases: (T degC, RH %, FAO-56 VPD kPa, Johnston VPD kPa), 4 d.p. -----
VPD_CASES = [
    (20, 50, 1.1691, 1.1710),
    (22, 60, 1.0576, 1.0593),
    (25, 60, 1.2671, 1.2691),
    (30, 70, 1.2729, 1.2747),
    (33, 60, 2.0121, 2.0146),
]
# Reference values are rounded to 4 d.p. (half-unit 5e-5); allow 1e-4.
TOL_VPD_KPA = 1.0e-4

JOHNSTON_FORMULA = "es(T) = 0.61078 * exp(17.08085 * T / (T + 234.175))  [kPa; paper gives hPa, divided by 10]"


def johnston_es(t_c):
    """Saturation vapour pressure (kPa) from Johnston et al. (2025). Independent of vpd.py."""
    t = np.asarray(t_c, dtype=float)
    return 0.61078 * np.exp(17.08085 * t / (t + 234.175))


def johnston_vpd(t_c, rh):
    return johnston_es(t_c) * (1.0 - np.asarray(rh, dtype=float) / 100.0)


def es_comparison() -> pd.DataFrame:
    """Application es vs published FAO-56 Table 2.3 (full-precision comparison)."""
    rows = []
    for t, published in FAO_ES_TABLE.items():
        app = float(vpd.saturation_vapour_pressure(t))
        diff = app - published
        rows.append({"Air temperature (°C)": t, "Published es (kPa)": published,
                     "Application es (kPa)": app, "Difference (kPa)": diff,
                     "Outcome": outcome(diff, TOL_ES_KPA)})
    return pd.DataFrame(rows)


def outcome(diff: float, tol: float) -> str:
    return "Within tolerance" if abs(diff) <= tol else "Outside tolerance"


def vpd_comparison(cases=VPD_CASES) -> pd.DataFrame:
    """Application air VPD vs FAO-56 reference values (predefined cases)."""
    rows = []
    for t, rh, ref, _ in cases:
        app = float(vpd.calculate_vpd(t, rh).vpd_air)
        diff = app - ref
        rows.append({"Air temperature (°C)": t, "RH (%)": rh,
                     "FAO-56 reference VPD (kPa)": ref, "Application VPD (kPa)": app,
                     "Difference (kPa)": diff, "Validation outcome": outcome(diff, TOL_VPD_KPA)})
    return pd.DataFrame(rows)


def alternative_equation_comparison(cases=VPD_CASES) -> pd.DataFrame:
    """Application (FAO-56) vs the alternative Johnston et al. (2025) equation."""
    rows = []
    for t, rh, _, ref_j in cases:
        app = float(vpd.calculate_vpd(t, rh).vpd_air)
        alt = float(johnston_vpd(t, rh))
        rows.append({"Air temperature (°C)": t, "RH (%)": rh,
                     "Johnston reference VPD (kPa)": ref_j, "Johnston equation, computed (kPa)": alt,
                     "Application VPD (kPa)": app, "Application - Johnston (kPa)": app - alt,
                     "Johnston computed vs published reference": outcome(alt - ref_j, TOL_VPD_KPA)})
    return pd.DataFrame(rows)


def additional_example(t_c: float, rh: float) -> dict:
    """Free-form example: application vs alternative equation (no published value exists)."""
    app = float(vpd.calculate_vpd(t_c, rh).vpd_air)
    alt = float(johnston_vpd(t_c, rh))
    return {"Air temperature (°C)": t_c, "RH (%)": rh, "Application VPD (kPa)": app,
            "Johnston equation VPD (kPa)": alt, "Application - Johnston (kPa)": app - alt}


def max_abs_differences() -> dict:
    """Largest absolute differences, computed at full precision."""
    es = es_comparison()["Difference (kPa)"].abs().max()
    v = vpd_comparison()["Difference (kPa)"].abs().max()
    alt = alternative_equation_comparison()["Application - Johnston (kPa)"].abs().max()
    return {"es_vs_FAO_table": float(es), "vpd_vs_FAO_reference": float(v),
            "application_vs_Johnston_equation": float(alt)}


def reference_curves(temps, rh_step: float = 1.0, offset: float = 0.0) -> pd.DataFrame:
    """VPD vs RH for each temperature: FAO-56 (production) and Johnston (alternative)."""
    rh = np.arange(0.0, 100.0 + rh_step / 2, rh_step)
    frames = []
    for t in temps:
        v = vpd.vpd_air(float(t), rh)
        j = johnston_vpd(t, rh)
        frames.append(pd.DataFrame({"temperature_C": float(t), "RH_percent": rh,
                                    "VPD_FAO56_kPa": v, "VPD_Johnston_kPa": j,
                                    "difference_FAO56_minus_Johnston_kPa": v - j}))
    return pd.concat(frames, ignore_index=True)
