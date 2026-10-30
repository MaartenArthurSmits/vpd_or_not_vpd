"""Generate a self-contained R script reproducing the calculator state and (optionally) the heatmap.

The numerical part uses base R only. The heatmap part needs ggplot2 (the `scales` package ships with
it); contour labels are added when the optional `metR` package is installed.
"""

from __future__ import annotations

from datetime import date

import numpy as np

import rangecolor
import vpd

# app colour scale -> ggplot2 fill scale
_R_SCALES = {
    "RdYlBu_r": 'scale_fill_distiller(palette = "RdYlBu", direction = -1, limits = zlim, oob = scales::squish)',
    "Viridis": 'scale_fill_viridis_c(option = "D", limits = zlim, oob = scales::squish)',
    "Turbo": 'scale_fill_viridis_c(option = "H", limits = zlim, oob = scales::squish)',
    "Cividis": 'scale_fill_viridis_c(option = "E", limits = zlim, oob = scales::squish)',
    "Plasma": 'scale_fill_viridis_c(option = "C", limits = zlim, oob = scales::squish)',
    "YlGnBu": 'scale_fill_distiller(palette = "YlGnBu", direction = 1, limits = zlim, oob = scales::squish)',
    "Spectral_r": 'scale_fill_distiller(palette = "Spectral", direction = -1, limits = zlim, oob = scales::squish)',
    "Greys": 'scale_fill_distiller(palette = "Greys", direction = 1, limits = zlim, oob = scales::squish)',
}


def _num(x) -> str:
    return repr(float(x))


def _heatmap_block(h: dict) -> list:
    kind = h.get("kind", vpd.AIR)
    offset = float(h.get("offset", 0.0))
    step = float(h.get("contour_step", 0.5))
    temps = np.arange(h["t_min"], h["t_max"] + 1e-9, 0.25)
    rhs = np.arange(h["rh_min"], h["rh_max"] + 1e-9, 0.5)
    z = vpd.vpd_matrix(temps, rhs, kind, offset)
    zlo = float(np.floor(z.min() * 2) / 2) if z.min() < 0 else 0.0
    zhi = float(h["z_max"]) if h.get("z_max") else float(z.max())
    start = float(np.ceil(z.min() / step) * step)
    if start - z.min() < 1e-9:      # a contour on the data minimum is only an edge artefact
        start += step
    label = "Air VPD" if kind == vpd.AIR else "Canopy VPD"
    tkind = h.get("target_kind") or kind          # colours follow `kind`, the target follows `target_kind`
    tlabel = "Air VPD" if tkind == vpd.AIR else "Canopy VPD"
    subtitle_target = ""
    if h.get("target") is not None:
        lo_t, hi_t = h["target"]
        subtitle_target = (("Dashed contour" if vpd.is_point_target(lo_t, hi_t) else "Dashed contours")
                           + ": t" + vpd.target_label(tkind, lo_t, hi_t, 2 if h.get("range_colour") else 1)[1:])      # "target Air VPD ..."
    scale = _R_SCALES.get(h.get("colorscale", "RdYlBu_r"), _R_SCALES["RdYlBu_r"])
    rc = bool(h.get("range_colour") and kind == vpd.LEAF and h.get("target") is not None and tkind == vpd.LEAF)
    if rc:      # same fixed-kPa colour stops as the app; the colour bar shows actual canopy VPD
        lo_c, hi_c = h["target"]
        zlo, zhi = rangecolor.domain(lo_c, hi_c)
        cs = rangecolor.colorscale(lo_c, hi_c)
        scale = ("scale_fill_gradientn(colours = c(" + ", ".join(f'"{c}"' for _, c in cs) + "),\n"
                 "                       values = c(" + ", ".join(repr(p) for p, _ in cs) + "),\n"
                 "                       limits = zlim, oob = scales::squish, labels = function(x) sprintf(\"%.2f\", x))")

    explain = ("\\n" + rangecolor.EXPLANATION) if rc else ""      # a second caption line in R
    L = [
        "",
        "# =====================================================================",
        "# Heatmap (reproduces the app's VPD heatmap; requires ggplot2)",
        "# =====================================================================",
        "library(ggplot2)",
        "",
        f"hm_t_min  <- {_num(h['t_min'])}    # temperature range (degC)",
        f"hm_t_max  <- {_num(h['t_max'])}",
        f"hm_rh_min <- {_num(h['rh_min'])}    # relative humidity range (%)",
        f"hm_rh_max <- {_num(h['rh_max'])}",
        f"hm_kind   <- \"{'air' if kind == vpd.AIR else 'leaf'}\"    # VPD type: \"air\" or \"leaf\"",
        f"hm_offset <- {_num(offset)}    # leaf temperature offset (degC), used when hm_kind == \"leaf\"",
        f"zlim      <- c({_num(zlo)}, {_num(zhi)})    # colour scale limits (kPa)",
        f"contour_breaks <- seq({_num(start)}, {_num(zhi)}, by = {_num(step)})",
        "",
        "grid <- expand.grid(temperature = seq(hm_t_min, hm_t_max, by = 0.25),",
        "                    rh = seq(hm_rh_min, hm_rh_max, by = 0.5))",
        "t_ref <- if (hm_kind == \"leaf\") grid$temperature + hm_offset else grid$temperature",
        "grid$vpd <- es(t_ref) - es(grid$temperature) * grid$rh / 100",
    ]
    if h.get("target") is not None:
        L += [f"hm_target_kind <- \"{'air' if tkind == vpd.AIR else 'leaf'}\"    # VPD type the target refers to",
              "t_ref_target <- if (hm_target_kind == \"leaf\") grid$temperature + hm_offset else grid$temperature",
              "grid$vpd_target <- es(t_ref_target) - es(grid$temperature) * grid$rh / 100"]
    point_in_view = h.get("point") is not None and h["t_min"] <= h["point"][0] <= h["t_max"] \
        and h["rh_min"] <= h["point"][1] <= h["rh_max"]
    L += [
        "",
        "p <- ggplot(grid, aes(x = temperature, y = rh)) +",
        "  geom_raster(aes(fill = vpd)) +",
        f"  {scale} +",
        "  geom_contour(aes(z = vpd), breaks = contour_breaks, colour = \"black\", alpha = 0.55, linewidth = 0.3) +",
    ]
    zero_drawn = kind == vpd.LEAF and vpd.zero_boundary_in_range(z)
    if zero_drawn:      # leaf saturation boundary, drawn only where it crosses the displayed grid
        L += [f"  geom_contour(aes(z = vpd, colour = \"{vpd.ZERO_LABEL}\"), breaks = 0, linewidth = 1.4) +",
              f"  scale_colour_manual(values = c(\"{vpd.ZERO_LABEL}\" = \"{vpd.ZERO_COLOUR}\"), name = NULL) +"]
    if h.get("target") is not None:
        lo, hi = h["target"]
        L += [f"  geom_contour(aes(z = vpd_target), breaks = unique(c({_num(lo)}, {_num(hi)})), colour = \"black\",",
              "               linewidth = 0.9, linetype = \"dashed\") +"]
    if point_in_view:
        t, rh = h["point"]
        L += [f"  annotate(\"point\", x = {_num(t)}, y = {_num(rh)}, shape = 21, size = 5,",
              "           fill = \"white\", colour = \"black\", stroke = 1.2) +"]
    L += [
        "  coord_cartesian(expand = FALSE) +",
        "  labs(x = \"Air temperature (°C)\", y = \"Relative humidity (%)\",",
        f"       fill = \"{label} (kPa)\",",
        f"       title = \"{label} as a function of temperature and relative humidity\",",
        *([f"       subtitle = \"{subtitle_target}\","] if h.get("target") is not None else []),
        f"       caption = \"Saturation vapour pressure: FAO-56 (Allen et al., 1998), Eq. 11"
        f"{'. Negative leaf VPD indicates possible condensation.' if zero_drawn else ''}"
        f"{explain}\") +",
        "  theme_minimal(base_size = 12)",
        "",
        "# Optional contour labels if the metR package is available",
        "if (requireNamespace(\"metR\", quietly = TRUE)) {",
        "  p <- p + metR::geom_text_contour(aes(z = vpd), breaks = contour_breaks, size = 2.8, stroke = 0.15)",
        "}",
        "",
        "# High-resolution exports (written to the working directory)",
        "ggsave(\"vpd_heatmap.png\", p, width = 10, height = 6.5, dpi = 300)",
        "ggsave(\"vpd_heatmap.pdf\", p, width = 10, height = 6.5)",
        "cat(\"heatmap_files: vpd_heatmap.png, vpd_heatmap.pdf\\n\")",
    ]
    return L


def build_r_script(mode_a: bool, t_air: float, rh: float, target_vpd: float, kind: str,
                   t_leaf: float, interval=None, interval_kind: str = vpd.AIR,
                   heatmap: dict | None = None) -> str:
    """R script reproducing the current calculation and, if `heatmap` is given, the heatmap.

    Output lines of the numerical part are 'name: value' so they can be compared with the app.
    `heatmap` keys: t_min, t_max, rh_min, rh_max, kind, offset, colorscale, contour_step, z_max,
    target (low, high) or None, target_kind (VPD type of the target; default `kind`),
    point (T, RH) or None.
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
        what = "target" if lo == hi else "target range"
        L += ["", f"# User-defined {what} for {interval_kind} VPD (kPa); not a validated optimum",
              f"vpd_lo <- {_num(lo)}", f"vpd_hi <- {_num(hi)}"]
        if interval_kind == vpd.AIR:
            L += ["rh_at_vpd_lo <- 100 * (1 - vpd_lo / es(t_air))",
                  "rh_at_vpd_hi <- 100 * (1 - vpd_hi / es(t_air))"]
        else:
            L += ["rh_at_vpd_lo <- 100 * (es(t_leaf) - vpd_lo) / es(t_air)",
                  "rh_at_vpd_hi <- 100 * (es(t_leaf) - vpd_hi) / es(t_air)"]
        L += ["cat(sprintf('rh_range_unclipped: %.6f to %.6f\\n', rh_at_vpd_hi, rh_at_vpd_lo))"]

    if mode_a:
        r = vpd.calculate_vpd(t_air, rh, measured_leaf=t_leaf)
    else:
        r = vpd.calculate_required_rh(t_air, target_vpd, kind, measured_leaf=t_leaf)
    L += ["", "# Values computed by the app at export time:",
          f"# vpd_air: {r.vpd_air:.6f}", f"# vpd_leaf: {r.vpd_leaf:.6f}", f"# rh: {r.rh:.6f}"]
    if heatmap is not None:
        L += _heatmap_block(heatmap)
    return "\n".join(L) + "\n"
