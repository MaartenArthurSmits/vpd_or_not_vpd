from pathlib import Path

import pytest

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


@pytest.fixture(scope="session")
def artifacts_dir():
    """Screenshots, downloads and diagnostics land here (git-ignored, uploaded as CI artifacts)."""
    for sub in ("screenshots", "downloads"):
        (ARTIFACTS / sub).mkdir(parents=True, exist_ok=True)
    return ARTIFACTS
