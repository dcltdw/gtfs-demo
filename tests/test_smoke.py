"""Smoke test: package and subpackages import cleanly on a fresh `uv sync`."""

from __future__ import annotations


def test_package_imports() -> None:
    import gtfs_demo

    assert gtfs_demo.__version__ == "0.1.0"


def test_subpackages_import() -> None:
    import gtfs_demo.cli
    import gtfs_demo.fetcher
    import gtfs_demo.parser
    import gtfs_demo.presenter
    import gtfs_demo.store

    for sub in (
        gtfs_demo.fetcher,
        gtfs_demo.parser,
        gtfs_demo.store,
        gtfs_demo.presenter,
        gtfs_demo.cli,
    ):
        assert sub.__doc__ is not None
