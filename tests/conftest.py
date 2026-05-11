"""Shared pytest fixtures."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mbta_mini_zip() -> Path:
    """Path to the committed minimal MBTA GTFS test fixture."""
    return FIXTURES / "mbta-mini.zip"


@pytest.fixture
def mbta_mini_unzipped(mbta_mini_zip: Path, tmp_path: pytest.TempPathFactory) -> Path:
    """The fixture zip unzipped into a tmp directory for parser tests."""
    target = Path(str(tmp_path)) / "feed"
    target.mkdir()
    with zipfile.ZipFile(mbta_mini_zip) as zf:
        zf.extractall(target)
    return target
