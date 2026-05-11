"""Smoke test: package and subpackages import cleanly on a fresh `uv sync`."""

from __future__ import annotations


def test_package_imports() -> None:
    import gtfs_dleung

    assert gtfs_dleung.__version__ == "0.0.1"


def test_subpackages_import() -> None:
    import gtfs_dleung.cli
    import gtfs_dleung.fetcher
    import gtfs_dleung.parser
    import gtfs_dleung.presenter
    import gtfs_dleung.store

    for sub in (
        gtfs_dleung.fetcher,
        gtfs_dleung.parser,
        gtfs_dleung.store,
        gtfs_dleung.presenter,
        gtfs_dleung.cli,
    ):
        assert sub.__doc__ is not None
