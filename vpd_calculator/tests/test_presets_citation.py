"""Presets, condensation guidance maths, citations and content policy checks."""

from pathlib import Path

import pytest

import citation
import presets
import vpd

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


# ---- growth-stage presets (values quoted from Koverda, 2020; Pulse Grow) -------------------
SOURCE_VALUES = {
    "Seedlings / propagation": {"day": (0.8, 0.8), "night": (0.6, 1.0)},
    "Vegetative": {"day": (1.0, 1.0), "night": (0.8, 1.2)},
    "Flowering": {"day": (1.2, 1.5), "night": (1.0, 1.5)},
    "General horticulture": {"day": (0.8, 1.2), "night": (0.8, 1.2)},
}


def test_preset_names_and_values_match_documented_source():
    assert presets.PRESET_NAMES == list(SOURCE_VALUES) + ["Custom"]
    for name, vals in SOURCE_VALUES.items():
        for period in ("day", "night"):
            assert presets.stage_range(name, period) == vals[period]


def test_preset_ranges_are_ordered():
    for d in presets.GROWTH_STAGES.values():
        for period in ("day", "night"):
            assert d[period][0] <= d[period][1]


def test_preset_matching_and_custom_fallback():
    assert presets.match_stage(1.2, 1.5) == "Flowering"
    assert presets.match_stage(0.6, 1.0, "night") == "Seedlings / propagation"
    assert presets.match_stage(0.9, 1.3) == "Custom"


def test_preset_disclaimers_distinguish_illustrative_from_validated():
    assert "not scientifically validated" in presets.PRESET_DISCLAIMER
    assert "species-specific" in presets.PRESET_DISCLAIMER
    assert "not universal correction factors" in presets.LEAF_OFFSET_DISCLAIMER
    assert presets.SOURCE_URL == "https://pulsegrow.com/blogs/learn/vpd"


# ---- leaf offset presets -------------------------------------------------------------------------
def test_leaf_offset_presets_are_the_requested_set():
    assert presets.LEAF_OFFSET_PRESETS == [0.0, -1.0, -2.0, 1.0, 2.0]
    assert presets.LEAF_OFFSET_NAMES[-1] == "Custom" and len(presets.LEAF_OFFSET_NAMES) == 6
    for v in presets.LEAF_OFFSET_PRESETS:
        assert presets.offset_from_label(presets.match_offset_preset(v)) == v
    assert presets.match_offset_preset(0.4) == "Custom"
    assert presets.offset_from_label("Custom") is None


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


def test_no_species_specific_content_in_public_files():
    for p in public_text_files():
        text = p.read_text(encoding="utf-8").lower()
        for word in ("fragaria", "strawberr", "vesca"):
            assert word not in text, f"{word!r} found in {p}"


def test_pulse_grow_attribution_is_not_claimed_for_equations():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "It is not the source of the equations" in app
    assert "Koverda, P. (2020, February 12)" in app
    for readme in (REPO / "README.md", ROOT / "README.md"):
        text = readme.read_text(encoding="utf-8")
        assert "Pulse Grow" in text and "not" in text.split("Pulse Grow", 1)[1][:400].lower()
