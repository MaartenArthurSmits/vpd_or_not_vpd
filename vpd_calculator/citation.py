"""Software citation strings (APA 7, BibTeX, IEEE). No DOI is claimed; none has been minted."""

from __future__ import annotations

AUTHOR_GIVEN = "Maarten Arthur"
AUTHOR_FAMILY = "Smits"
ORCID = "https://orcid.org/0009-0004-1315-0822"
TITLE = "VPD Calculator"
VERSION = "1.0.0"
YEAR = "2026"
REPO_URL = "https://github.com/MaartenArthurSmits/vpd_or_not_vpd"
APP_URL = "https://vpd-or-not-vpd.streamlit.app/"


def apa() -> str:
    return (f"{AUTHOR_FAMILY}, M. A. ({YEAR}). *{TITLE}* (Version {VERSION}) [Computer software]. "
            f"GitHub. {REPO_URL}")


def bibtex() -> str:
    return (
        "@misc{smits2026vpdcalculator,\n"
        f"  author       = {{{AUTHOR_FAMILY}, {AUTHOR_GIVEN}}},\n"
        f"  title        = {{{TITLE}}},\n"
        f"  year         = {{{YEAR}}},\n"
        f"  version      = {{{VERSION}}},\n"
        "  howpublished = {Computer software, GitHub repository},\n"
        f"  url          = {{{REPO_URL}}},\n"
        "}"
    )


def ieee() -> str:
    return (f"M. A. {AUTHOR_FAMILY}, \"{TITLE},\" version {VERSION}, {YEAR}. [Computer software]. "
            f"Available: {REPO_URL}")


def apa_footer_plain() -> str:
    """Recommended APA 7 citation shown in the footer (plain text, for copying)."""
    return (f"{AUTHOR_FAMILY}, M. A. ({YEAR}). {TITLE} (Version {VERSION}) [Computer software]. {APP_URL}")


def apa_footer_markdown() -> str:
    """The same citation with the software title in italics."""
    return apa_footer_plain().replace(TITLE, f"*{TITLE}*", 1)


def footer_markdown() -> str:
    """Shared footer note: copyright and code licence (the licence applies to the code only)."""
    return f"© {YEAR} {AUTHOR_GIVEN} {AUTHOR_FAMILY} · Code: [MIT licence]({REPO_URL}/blob/main/LICENSE)"
