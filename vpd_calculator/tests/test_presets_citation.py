"""Presets, condensation guidance maths, citations and content policy checks."""

from pathlib import Path

import pytest

import citation
import presets
import vpd

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


# ---- range presets (values quoted from the cited sources) -------------------------------------------
EXPECTED = {
    "General established plants — Lopez et al. (2026)": (0.70, 1.30),
    "General established plants — Runkle (2021)": (0.70, 1.50),
    "Propagation, roots developing — Runkle (2021)": (0.30, 0.70),
    "Leafy greens and herbs, vegetative — ASHRAE (2023)": (0.65, 0.90),
    "Flowering and fruiting, indoor crops — ASHRAE (2023)": (1.00, 1.40),
    "Cucumber, winter fruit production — Bayer (2020)": (0.40, 0.80),
    "Strawberry, greenhouse production — Yamanaka et al. (2025)": (0.80, 1.20),
}


def test_preset_names_values_and_default_match_the_requested_table():
    assert presets.PRESET_NAMES == list(EXPECTED) + ["Custom range"]
    for name, rng in EXPECTED.items():
        assert presets.preset_range(name) == rng and rng[0] <= rng[1]
        assert presets.RANGE_PRESETS[name]["source"].count("http") >= 1
    assert presets.DEFAULT_PRESET == "General established plants — Lopez et al. (2026)"


def test_preset_matching_and_custom_fallback():
    assert presets.match_preset((0.8, 1.2), (0.8, 1.2)).startswith("Strawberry")
    assert presets.match_preset((0.8, 1.2), (0.8, 1.3)) == presets.CUSTOM


def test_adaptation_statement_is_explicit_and_sources_are_in_the_references():
    assert "leaf temperature equals air temperature" in presets.ABOUT_RANGES and "validated these ranges as canopy-VPD optima" in presets.ABOUT_RANGES
    assert "limits then remain fixed" in presets.ABOUT_RANGES
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    for needle in ("Yamanaka, R.", "Lopez, R.", "Runkle, E. S. (2021", "Runkle, E. S. (2022", "Wollaeger, H.", "ASHRAE. (2023)", "Bayer. (2020"):
        assert needle in app, needle
    for needle in ("0.069 hPa/min = 0.0069 kPa/min", "no upper night-time limit", "not a universal transition-speed limit"):
        assert needle in app, needle


# ---- condensation guidance ------------------------------------------------------------------------
@pytest.mark.parametrize("t,off", [(22, -1), (17, -2), (30, -3.5)])
def test_condensation_rh_is_where_leaf_vpd_reaches_zero(t, off):
    rh_c = float(vpd.condensation_rh(t, t + off))
    assert rh_c < 100
    assert abs(vpd.vpd_leaf(t, rh_c, t + off)) < 1e-12
    assert vpd.vpd_leaf(t, min(rh_c + 1, 100), t + off) < 0


@pytest.mark.parametrize("off", [0.0, 1.0, 2.0])
def test_no_condensation_limit_when_leaf_not_cooler(off):
    assert float(vpd.condensation_rh(22, 22 + off)) >= 100.0 - 1e-9


# ---- citations --------------------------------------------------------------------------------------
def test_citation_formats_contain_required_elements_and_no_doi():
    for text in (citation.apa(), citation.bibtex(), citation.ieee()):
        assert citation.REPO_URL in text and "Smits" in text and "2026" in text and "1.0.0" in text
        assert "doi" not in text.lower() and "zenodo" not in text.lower()
    assert citation.apa().startswith("Smits, M. A. (2026). *VPD Calculator* (Version 1.0.0) [Computer software].")
    assert citation.bibtex().startswith("@misc{") and citation.bibtex().rstrip().endswith("}")
    assert citation.ieee().startswith("M. A. Smits, ")


def test_citation_cff_has_orcid_and_matches_module():
    cff = (REPO / "CITATION.cff").read_text(encoding="utf-8")
    assert 'orcid: "https://orcid.org/0009-0004-1315-0822"' in cff
    assert citation.ORCID == "https://orcid.org/0009-0004-1315-0822"
    assert f'version: "{citation.VERSION}"' in cff
    assert citation.REPO_URL in cff
    assert "doi:" not in cff.lower().split("references:")[0]       # no DOI minted for the software itself


# ---- content policy -------------------------------------------------------------------------------------
def public_text_files():
    skip_dirs = {".venv", ".git", "tests", "__pycache__", "artifacts", ".pytest_cache"}
    for base in (ROOT, REPO / "docs"):
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".md", ".txt", ".yml", ".cff", ".ini"} \
                    and not (set(p.relative_to(REPO).parts) & skip_dirs):
                yield p
    for name in ("README.md", "CITATION.cff"):
        yield REPO / name


def test_no_scientific_species_names_in_public_files():
    for p in public_text_files():
        text = p.read_text(encoding="utf-8").lower()
        for word in ("fragaria", "vesca"):
            assert word not in text, f"{word!r} found in {p}"


def test_pulse_grow_attribution_is_not_claimed_for_equations():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "It is not the source of the equations" in app
    assert "Koverda, P. (2020, February 12)" in app
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "Pulse Grow" in text and "not" in text.split("Pulse Grow", 1)[1][:400].lower()
