"""Range presets for the Acceptable range tab.

The presets adapt published VPD guidance into editable *starting ranges*. Some sources report air VPD, and none
of them is a validated, leaf-temperature-corrected canopy-VPD optimum. Provenance is kept in the source notes.
"""

from __future__ import annotations

CUSTOM = "Custom range"

_RUNKLE_URL = "https://www.canr.msu.edu/floriculture/uploads/files/Water%20VPD.pdf"
_ASHRAE_URL = "https://handbook.ashrae.org/Handbooks/A23/SI/A23_Ch25/a23_ch25_si.aspx"
# (display name, share id, lower kPa, upper kPa, source note in markdown)
_PRESETS = [
    ("General established plants — Lopez et al. (2026)", "lopez", 0.70, 1.30,
     "[Lopez, Chen, Cooley & Vander Weide, *VPD, Temperature & Everbearing Strawberries*]"
     "(https://www.inside-grower.com/Article/?articleid=28096), “Greenhouse VPD ranges.” Original VPD basis: not confirmed."),
    ("General established plants — Runkle (2021)", "runkle-mod", 0.70, 1.50,
     f"[Runkle, *Water Vapor-Pressure Deficit*]({_RUNKLE_URL}), *Greenhouse Product News*, December 2021, p. 34, "
     "“Moderate VPD” (a subjective classification). Original VPD basis: not confirmed."),
    ("Propagation, roots developing — Runkle (2021)", "runkle-low", 0.30, 0.70,
     f"Same [Runkle article]({_RUNKLE_URL}), “Low VPD” (a subjective classification); applies after an initial "
     "root system develops. Original VPD basis: not confirmed."),
    ("Leafy greens and herbs, vegetative — ASHRAE (2023)", "ashrae-leafy", 0.65, 0.90,
     f"[ASHRAE Handbook, Chapter 25]({_ASHRAE_URL}), §3.3 Commercial Indoor Farms → Design Conditions. Original VPD basis: not confirmed."),
    ("Flowering and fruiting, indoor crops — ASHRAE (2023)", "ashrae-fruit", 1.00, 1.40,
     f"Same [handbook section]({_ASHRAE_URL}); includes tomatoes and cucumbers. Original VPD basis: not confirmed."),
    ("Cucumber, winter fruit production — Bayer (2020)", "bayer", 0.40, 0.80,
     "[*Fruit Length in Winter-Grown Cucumbers*](https://www.vegetables.bayer.com/ca/en-ca/resources/"
     "growing-tips/cultivation-insights/fruit-length-in-winter-grown-cucumbers.html), February 12, 2020, "
     "“Regulating humidity.” Original VPD basis: not confirmed."),
    ("Strawberry, greenhouse production — Yamanaka et al. (2025)", "yamanaka", 0.80, 1.20,
     "[Yamanaka et al., *Relationship between Vapor Pressure Deficit Condition and Water-stress Status in "
     "Strawberry*](https://doi.org/10.2503/hortj.SZD-015), Introduction: 8–12 hPa, citing Lieten (2002); "
     "not independently established by their experiment. Their measurements are air-based."),
]

RANGE_PRESETS = {name: {"id": pid, "range": (lo, hi), "source": src} for name, pid, lo, hi, src in _PRESETS}
PRESET_NAMES = list(RANGE_PRESETS) + [CUSTOM]
DEFAULT_PRESET = _PRESETS[0][0]
PRESET_IDS = {v["id"]: k for k, v in RANGE_PRESETS.items()} | {"custom": CUSTOM}

ABOUT_RANGES = (
    "Published VPD recommendations often refer to air VPD. To use their numerical ranges as canopy-VPD targets, this "
    "calculator adopts an explicit reference assumption: leaf temperature equals air temperature. At that reference "
    "condition, air and leaf VPD are identical.\n\n"
    "The selected limits then remain fixed. Your actual measured or estimated leaf temperature is used to calculate "
    "canopy VPD and the humidity needed to reach the target.\n\n"
    "This is a practical starting assumption, not evidence that the original authors assumed equal temperatures or "
    "validated these ranges as canopy-VPD optima. Suitability depends on the crop and growing conditions; you can "
    "edit the limits.")


def preset_range(name: str):
    return RANGE_PRESETS[name]["range"]


def _matches(name: str, day: tuple, night: tuple) -> bool:
    a, b = RANGE_PRESETS[name]["range"]
    return all(abs(a - lo) < 1e-9 and abs(b - hi) < 1e-9 for lo, hi in (day, night))


def match_preset(day: tuple, night: tuple) -> str:
    """First preset whose range equals both the day and night limits, else Custom."""
    return next((name for name in RANGE_PRESETS if _matches(name, day, night)), CUSTOM)


def resolve_preset(candidate, day: tuple, night: tuple) -> str:
    """Preset to show for restored limits: a saved identity is kept when Custom or still matching both periods."""
    if candidate == CUSTOM:
        return CUSTOM
    if candidate in RANGE_PRESETS and _matches(candidate, day, night):
        return candidate
    return match_preset(day, night)
