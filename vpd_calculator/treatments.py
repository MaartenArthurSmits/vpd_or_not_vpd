"""Treatment-comparison table: validate editable rows and calculate air and leaf VPD for each valid row.

Calculations use the production functions in `vpd.py`; input limits are the same bounds that shared links use.
"""

from __future__ import annotations

import math

import pandas as pd

import share
import vpd

NAME, T_AIR, RH, OFFSET = "Treatment", "Air temperature (°C)", "Relative humidity (%)", "Leaf–air offset (°C)"
INPUTS = [NAME, T_AIR, RH, OFFSET]
T_LEAF, VPD_AIR, VPD_LEAF, STATUS = "Leaf temperature (°C)", "Air VPD (kPa)", "Leaf VPD (kPa)", "Status"
RESULTS = [T_LEAF, VPD_AIR, VPD_LEAF]

OK = "OK"
CONDENSATION = "Possible condensation (negative leaf VPD)"

# Allowed ranges for the numeric inputs: the same limits as the calculator inputs / shared links.
LIMITS = {T_AIR: share._NUMERIC["t"][1:], RH: share._NUMERIC["rh"][1:], OFFSET: share._NUMERIC["off"][1:]}
UNITS = {T_AIR: "°C", RH: "%", OFFSET: "°C"}

EXAMPLES = pd.DataFrame({
    NAME: ["Example A (22 °C, 60 % RH)", "Example B (33 °C, 60 % RH)"],
    T_AIR: [22.0, 33.0], RH: [60.0, 60.0], OFFSET: [0.0, 0.0],
})


def _number(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def evaluate(rows: pd.DataFrame) -> pd.DataFrame:
    """Inputs, results and a status per row. Invalid or incomplete rows get a message and no results."""
    out = []
    for position, (_, row) in enumerate(rows.iterrows(), start=1):
        name = row.get(NAME)
        name = "" if name is None or (isinstance(name, float) and math.isnan(name)) else str(name).strip()
        values, problems = {}, []
        for column in (T_AIR, RH, OFFSET):
            x = _number(row.get(column))
            lo, hi = LIMITS[column]
            if x is None:
                problems.append(f"{column.split(' (')[0]} missing or not a number")
            elif not lo <= x <= hi:
                problems.append(f"{column.split(' (')[0]} must be between {lo:g} and {hi:g} {UNITS[column]}")
            values[column] = x
        if not name:
            problems.append("treatment name missing")
        rec = {NAME: name, **values, T_LEAF: None, VPD_AIR: None, VPD_LEAF: None}
        if problems:
            rec[STATUS] = f"Row {position} not calculated: " + "; ".join(problems)
        else:
            r = vpd.calculate_vpd(values[T_AIR], values[RH], values[OFFSET])
            rec.update({T_LEAF: r.t_leaf, VPD_AIR: r.vpd_air, VPD_LEAF: r.vpd_leaf})
            rec[STATUS] = CONDENSATION if r.vpd_leaf < 0 else OK
        out.append(rec)
    return pd.DataFrame(out, columns=INPUTS + RESULTS + [STATUS])


def to_csv(results: pd.DataFrame) -> bytes:
    """Inputs and results at full precision (blank where a row was not calculated)."""
    return results.to_csv(index=False).encode("utf-8")
