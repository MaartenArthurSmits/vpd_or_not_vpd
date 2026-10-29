"""Reference data and comparison helpers for the in-app "Scientific validation" section.

Everything here that is labelled "application" calls the production functions in
`vpd.py`; nothing re-implements the FAO-56 equation. The Johnston et al. (2025)
equation is a separate, independent formula used only as an alternative reference.

Provenance of the reference numbers (details and verification record: docs/VALIDATION.md)
-------------------------------------------------------------------------------------
PUBLISHED : FAO_ES_TABLE - es values printed in FAO-56 Annex 2, Table 2.3 (Allen et al., 1998),
            https://www.fao.org/4/x0490e/x0490e0j.htm (checked against the page, 2026-10-29).
CALCULATED: VPD_CASES - air VPD = es(T) * (1 - RH/100) evaluated from the FAO-56 Eq. 11 constants
            (https://www.fao.org/4/x0490e/x0490e07.htm) and from the Johnston et al. (2025) equation
            (https://doi.org/10.1029/2024JG008146), rounded to 4 d.p. These VPD values are NOT printed
            in FAO-56 Table 2.3, and it is NOT verified that they are printed in Johnston et al.
EQUATION  : the Johnston coefficients (6.1078 hPa -> 0.61078 kPa, 17.08085, 234.175) were verified
            against Johnston et al. (2025), Section 1 "Introduction", Equation 2 by an external source
            review on 2026-10-29 (not accessed directly in the session that wrote this note).
SPEC      : the original project specification that supplied the benchmark numbers is not in this
            repository; its historical provenance remains unverified.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import vpd

# --- PUBLISHED: saturation vapour pressure (kPa), FAO-56 Annex 2 Table 2.3, 3 d.p. ------
# Each value was checked against the printed table (rows T = 15.0, 20.0, 22.0, 25.0, 30.0, 33.0, 35.0).
FAO_ES_TABLE = {15: 1.705, 20: 2.338, 22: 2.644, 25: 3.168, 30: 4.243, 33: 5.030, 35: 5.623}
# Half a unit of the last published decimal (0.0005) plus a small float margin.
TOL_ES_KPA = 5.0e-4 + 1e-9

# --- CALCULATED benchmarks (not published tabulated values), 4 d.p. -----------------------
# (T degC, RH %, VPD from the FAO-56 Eq. 11 constants, VPD from the Johnston et al. (2025) equation).
# Both VPD columns were obtained by evaluating es(T) * (1 - RH/100) with each equation's constants;
# they reproduce at 4 d.p. when recomputed with a stand-alone calculation (review of 2026-10-29).
VPD_CASES = [
    (20, 50, 1.1691, 1.1710),
    (22, 60, 1.0576, 1.0593),
    (25, 60, 1.2671, 1.2691),
    (30, 70, 1.2729, 1.2747),
    (33, 60, 2.0121, 2.0146),
]
# Benchmarks are rounded to 4 d.p. (half-unit 5e-5); allow 1e-4.
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
    """Application air VPD vs the calculated FAO-56 benchmarks (predefined cases; not published values)."""
    rows = []
    for t, rh, ref, _ in cases:
        app = float(vpd.calculate_vpd(t, rh).vpd_air)
        diff = app - ref
        rows.append({"Air temperature (°C)": t, "RH (%)": rh,
                     "FAO-56 calculated benchmark VPD (kPa)": ref, "Application VPD (kPa)": app,
                     "Difference (kPa)": diff, "Outcome (vs calculated benchmark)": outcome(diff, TOL_VPD_KPA)})
    return pd.DataFrame(rows)


def alternative_equation_comparison(cases=VPD_CASES) -> pd.DataFrame:
    """Application (FAO-56) vs the alternative Johnston et al. (2025) equation.

    The 'Johnston calculated benchmark' column holds VPDs calculated from that equation (4 d.p.); it is
    not verified that these numbers are printed in the paper. (The equation coefficients themselves
    are verified against Johnston et al. (2025), Eq. 2; see the module docstring.)
    """
    rows = []
    for t, rh, _, ref_j in cases:
        app = float(vpd.calculate_vpd(t, rh).vpd_air)
        alt = float(johnston_vpd(t, rh))
        rows.append({"Air temperature (°C)": t, "RH (%)": rh,
                     "Johnston calculated benchmark VPD (kPa)": ref_j, "Johnston equation, computed (kPa)": alt,
                     "Application VPD (kPa)": app, "Application - Johnston (kPa)": app - alt,
                     "Johnston equation vs calculated benchmark": outcome(alt - ref_j, TOL_VPD_KPA)})
    return pd.DataFrame(rows)


def additional_example(t_c: float, rh: float) -> dict:
    """Free-form example: application vs alternative equation (no tabulated benchmark exists)."""
    app = float(vpd.calculate_vpd(t_c, rh).vpd_air)
    alt = float(johnston_vpd(t_c, rh))
    return {"Air temperature (°C)": t_c, "RH (%)": rh, "Application VPD (kPa)": app,
            "Johnston equation VPD (kPa)": alt, "Application - Johnston (kPa)": app - alt}


def max_abs_differences() -> dict:
    """Largest absolute differences, computed at full precision."""
    es = es_comparison()["Difference (kPa)"].abs().max()
    v = vpd_comparison()["Difference (kPa)"].abs().max()
    alt = alternative_equation_comparison()["Application - Johnston (kPa)"].abs().max()
    return {"es_vs_FAO_table": float(es), "vpd_vs_FAO56_benchmark": float(v),
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
