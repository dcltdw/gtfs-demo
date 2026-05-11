"""Marker tests asserting the existence of the type-safety gate.

The actual type-check is performed by the CI ``typecheck`` job (``mypy --strict``
against ``gtfs_dleung`` and ``tests``). These tests document the gate's existence
inside the pytest suite, so a future contributor scanning ``tests/`` sees that
typing is part of the contract.
"""

from __future__ import annotations


def test_strict_mypy_clean_on_package() -> None:
    """Placeholder marker — strict mypy verification happens in CI, not here.

    Kept as a no-op so the contract is visible in the test suite. If this file
    grows into runtime type-introspection tests, drop the docstring caveat.
    """
