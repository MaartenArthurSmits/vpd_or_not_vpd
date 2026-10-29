"""Illustrative horticultural VPD ranges and leaf-temperature offset scenarios.

IMPORTANT: these are illustrative values from a grower-oriented guide, NOT scientifically
validated species-specific optima. They are provided only as starting points.

Source for the growth-stage ranges and the typical leaf offset:
    Koverda, P. (2020, February 12). The ultimate vapor pressure deficit (VPD) guide.
    Pulse Grow. https://pulsegrow.com/blogs/learn/vpd
Quoted from that page:
    general rule 0.8-1.2 kPa; seedlings and clones "closer to 0.8 kPa" (night 0.6-1.0 kPa);
    vegetative "around 1.0 kPa" (night 0.8-1.2 kPa); flower 1.2-1.5 kPa (night 1.0-1.5 kPa);
    leaf temperature "typically 1-3 degC ... cooler" than air; chart default 0 degC offset.
Where the page gives a single value for the day (seedlings, vegetative), the preset uses that
value as both limits (zero-width range); widen it yourself if desired.
"""

from __future__ import annotations

SOURCE_APA = ("Koverda, P. (2020, February 12). *The ultimate vapor pressure deficit (VPD) guide*. "
              "Pulse Grow. https://pulsegrow.com/blogs/learn/vpd")
SOURCE_URL = "https://pulsegrow.com/blogs/learn/vpd"

CUSTOM = "Custom"

# stage -> {"day": (low, high), "night": (low, high), "note": str}
GROWTH_STAGES = {
    "Seedlings / propagation": {
        "day": (0.8, 0.8), "night": (0.6, 1.0),
        "note": "Day: source gives a single value, 'closer to 0.8 kPa'. Night: 0.6-1.0 kPa."},
    "Vegetative": {
        "day": (1.0, 1.0), "night": (0.8, 1.2),
        "note": "Day: source gives a single value, 'around 1.0 kPa'. Night: 0.8-1.2 kPa."},
    "Flowering": {
        "day": (1.2, 1.5), "night": (1.0, 1.5),
        "note": "Day: 1.2-1.5 kPa. Night: 1.0-1.5 kPa."},
    "General horticulture": {
        "day": (0.8, 1.2), "night": (0.8, 1.2),
        "note": "General rule of thumb 0.8-1.2 kPa; the source gives no separate night range."},
}

PRESET_NAMES = list(GROWTH_STAGES) + [CUSTOM]

PRESET_DISCLAIMER = (
    "These presets are illustrative horticultural ranges from a grower guide "
    "(Koverda, 2020; Pulse Grow). They are not scientifically validated, species-specific optima, "
    "and no range here has been tested for any particular species or cultivar.")

# Leaf temperature offset scenarios (leaf minus air, degC)
LEAF_OFFSET_PRESETS = [0.0, -1.0, -2.0, 1.0, 2.0]
LEAF_OFFSET_LABELS = {0.0: "0 °C (leaf = air)", -1.0: "-1 °C", -2.0: "-2 °C", 1.0: "+1 °C", 2.0: "+2 °C"}
LEAF_OFFSET_NAMES = [LEAF_OFFSET_LABELS[v] for v in LEAF_OFFSET_PRESETS] + [CUSTOM]
LEAF_OFFSET_DISCLAIMER = (
    "Offsets of 0, -1, -2, +1 and +2 °C are illustrative scenarios, not universal correction factors. "
    "Actual leaf-air temperature differences depend on species, light, airflow, humidity and "
    "water status; measure leaf temperature (for example with an infrared thermometer) when it matters. "
    "Koverda (2020) describes leaves as typically 1-3 °C cooler than air; positive offsets have no "
    "source here and are included only for completeness.")


def stage_range(stage: str, period: str = "day"):
    return GROWTH_STAGES[stage][period]


def match_stage(low: float, high: float, period: str = "day") -> str:
    """Name of the preset whose range equals (low, high), else 'Custom'.

    'General horticulture' is checked first so that identical ranges resolve to the general rule.
    """
    order = ["General horticulture"] + [n for n in GROWTH_STAGES if n != "General horticulture"]
    for name in order:
        d = GROWTH_STAGES[name]
        a, b = d[period]
        if abs(a - low) < 1e-9 and abs(b - high) < 1e-9:
            return name
    return CUSTOM


def resolve_stage(candidate, low: float, high: float, period: str = "day") -> str:
    """Preset to show for restored settings.

    A saved preset identity is kept when it is 'Custom' or when its range for `period` equals (low, high)
    (this preserves which of several identical-range presets was selected). Otherwise the preset is
    derived from the limits. The limits themselves are never changed.
    """
    if candidate == CUSTOM:
        return CUSTOM
    if candidate in GROWTH_STAGES:
        a, b = GROWTH_STAGES[candidate][period]
        if abs(a - low) < 1e-9 and abs(b - high) < 1e-9:
            return candidate
    return match_stage(low, high, period)


def match_offset_preset(offset: float) -> str:
    for v, label in LEAF_OFFSET_LABELS.items():
        if abs(v - offset) < 1e-9:
            return label
    return CUSTOM


def offset_from_label(label: str):
    for v, lab in LEAF_OFFSET_LABELS.items():
        if lab == label:
            return v
    return None
