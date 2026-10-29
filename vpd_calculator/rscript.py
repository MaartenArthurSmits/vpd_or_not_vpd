"""Generate a self-contained, dependency-free R script that reproduces a calculator state."""

from __future__ import annotations

from datetime import date

import vpd


def _num(x) -> str:
    return repr(float(x))


def build_r_script(mode_a: bool, t_air: float, rh: float, target_vpd: float, kind: str,
                   t_leaf: float, interval=None, interval_kind: str = vpd.AIR) -> str:
    """R script (base R only) reproducing the current calculation.

    Output lines are 'name: value' so they are easy to compare with the app.
    """
    L = [
        "# VPD calculation reproduced from the VPD Calculator",
        "# https://github.com/MaartenArthurSmits/vpd_or_not_vpd",
        f"# Generated {date.today().isoformat()}",
        "# Saturation vapour pressure: FAO-56 Eq. 11 (Allen et al., 1998),",
        "# https://www.fao.org/4/x0490e/x0490e07.htm",
        "# Units: temperature in degC, RH in %, pressures in kPa.",
        "",
        "es <- function(t) 0.6108 * exp(17.27 * t / (t + 237.3))",
        "",
        f"t_air  <- {_num(t_air)}",
        f"t_leaf <- {_num(t_leaf)}   # leaf temperature (air temperature + offset, or measured)",
    ]
    if mode_a:
        L += [
            f"rh     <- {_num(rh)}",
            "",
            "ea       <- es(t_air) * rh / 100",
            "vpd_air  <- es(t_air) - ea",
            "vpd_leaf <- es(t_leaf) - ea",
        ]
    else:
        L += [f"target_vpd <- {_num(target_vpd)}   # target {kind} VPD (kPa)", ""]
        if kind == vpd.AIR:
            L.append("rh <- 100 * (1 - target_vpd / es(t_air))")
        else:
            L.append("rh <- 100 * (es(t_leaf) - target_vpd) / es(t_air)")
        L += [
            "if (rh < 0 || rh > 100) cat(sprintf('WARNING: target unattainable, RH would be %.4f %%\\n', rh))",
            "ea       <- es(t_air) * rh / 100",
            "vpd_air  <- es(t_air) - ea",
            "vpd_leaf <- es(t_leaf) - ea",
        ]
    L += [
        "",
        "cat(sprintf('es_air: %.6f\\n', es(t_air)))",
        "cat(sprintf('es_leaf: %.6f\\n', es(t_leaf)))",
        "cat(sprintf('ea: %.6f\\n', ea))",
        "cat(sprintf('rh: %.6f\\n', rh))",
        "cat(sprintf('vpd_air: %.6f\\n', vpd_air))",
        "cat(sprintf('vpd_leaf: %.6f\\n', vpd_leaf))",
        "if (vpd_leaf < 0) cat('NOTE: negative leaf VPD (condensation possible)\\n')",
    ]
    if interval is not None and interval[0] <= interval[1]:
        lo, hi = interval
        L += ["", f"# User-defined target {interval_kind} VPD interval (kPa); not a validated optimum",
              f"vpd_lo <- {_num(lo)}", f"vpd_hi <- {_num(hi)}"]
        if interval_kind == vpd.AIR:
            L += ["rh_at_vpd_lo <- 100 * (1 - vpd_lo / es(t_air))",
                  "rh_at_vpd_hi <- 100 * (1 - vpd_hi / es(t_air))"]
        else:
            L += ["rh_at_vpd_lo <- 100 * (es(t_leaf) - vpd_lo) / es(t_air)",
                  "rh_at_vpd_hi <- 100 * (es(t_leaf) - vpd_hi) / es(t_air)"]
        L += ["cat(sprintf('rh_range_unclipped: %.6f to %.6f\\n', rh_at_vpd_hi, rh_at_vpd_lo))"]

    # Expected values from the app, for cross-checking the R output
    if mode_a:
        r = vpd.calculate_vpd(t_air, rh, measured_leaf=t_leaf)
    else:
        r = vpd.calculate_required_rh(t_air, target_vpd, kind, measured_leaf=t_leaf)
    L += ["", "# Values computed by the app at export time:",
          f"# vpd_air: {r.vpd_air:.6f}", f"# vpd_leaf: {r.vpd_leaf:.6f}",
          f"# rh: {(r.rh):.6f}", ""]
    return "\n".join(L)
