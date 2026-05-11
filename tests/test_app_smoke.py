"""Smoke + live-marker tests for the Streamlit app entrypoint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_app_imports() -> None:
    """The Streamlit entrypoint imports cleanly without spinning up the app.

    This catches the broadest class of integration breakage — a missing dep,
    a renamed symbol, a circular import — without actually rendering anything.
    """
    # Importing app.py runs the module body but does NOT call main(); calling
    # main() would require a Streamlit runtime. The module body has only
    # imports + decorator-wrapped function definitions, which is safe.
    import gtfs_dleung.app as app

    assert hasattr(app, "main")


def test_main_function_exists_and_callable() -> None:
    """main() is the entrypoint Streamlit invokes; verify it's a callable."""
    from gtfs_dleung.app import main

    assert callable(main)


@pytest.mark.live
def test_streamlit_app_starts_cleanly() -> None:
    """End-to-end check: ``streamlit run`` boots the app without an early crash.

    Runs Streamlit headless for a short window and asserts the process didn't
    exit non-zero before the timeout. Streamlit doesn't exit on its own, so the
    timeout itself is the success signal.

    Marked ``@pytest.mark.live`` so it stays out of the default PR ``test`` job;
    it spawns a subprocess that takes ~5-10 seconds, which is too noisy for the
    fast inner loop. The nightly tier from #49 runs ``-m live``.
    """
    repo_root = Path(__file__).resolve().parent.parent
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "gtfs_dleung/app.py",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        "--server.port=8765",
        "--browser.gatherUsageStats=false",
    ]

    try:
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired as e:
        # Streamlit didn't crash before the timeout — that's success.
        # Inspect the captured stdout (e.stdout may be bytes here, decode defensively).
        stdout = (
            e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else e.stdout
        )
        stderr = (
            e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else e.stderr
        )
        combined = (stdout or "") + (stderr or "")
        assert "Traceback" not in combined, f"Streamlit crashed during startup: {combined}"
        return

    # If streamlit run exits within the timeout, it almost always means a startup error.
    pytest.fail(
        f"Streamlit run exited unexpectedly (rc={proc.returncode}).\n"
        f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )
