---
id: NF-012
title: CI pipeline (PR gates + pre-commit hooks)
type: non-functional
status: in-progress
issue: 2
pr: null
depends_on: [NF-001, NF-002, NF-003]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Three CI jobs run on every PR into `main` (and every push to `main`): `lint`, `typecheck`, `test`. Each job sets up Python 3.13 + uv, syncs the project's dev dependencies from the locked manifest, and runs one tool. Locally, contributors install a `pre-commit` config that runs an overlapping set of fast checks before each commit. A `detect-secrets` baseline captures the high-entropy strings the agent already audited (public project-board field IDs); future high-entropy additions trip the hook and require a fresh audit.

## Inputs

- `pyproject.toml` — project metadata, runtime + dev dependencies (locked in `uv.lock`).
- `.python-version` — the Python interpreter pin (`3.13`).
- `.pre-commit-config.yaml` — local hook configuration.
- `.secrets.baseline` — `detect-secrets` audited baseline; pinned in the repo.
- `.github/workflows/pr-tests.yml` — CI workflow definition.

## Properties

1. Every PR into `main` triggers `lint`, `typecheck`, and `test` jobs in parallel.
2. `lint` runs `ruff format --check` followed by `ruff check` against the entire tree.
3. `typecheck` runs `mypy --strict` against `gtfs_dleung/` and `tests/`.
4. `test` runs `pytest -v` against the full test suite.
5. Each job pins Python 3.13 via `uv python install 3.13`.
6. Each job uses `astral-sh/setup-uv@v3` with `enable-cache: true` keyed off `uv.lock` for fast warm runs.
7. `concurrency` cancels in-progress runs on the same PR when a new commit lands (saves CI minutes).
8. Push events to `main` are NOT cancelled by concurrency — every merged commit gets a verifying run.
9. Pre-commit hooks (locally) reproduce the lint + typecheck + secrets-scan subset; the test suite runs only in CI.
10. The `detect-secrets` baseline is the source of truth for "known not a secret"; pre-commit fails the commit if a new high-entropy hit appears.

## Outputs

- GitHub status checks named `lint`, `typecheck`, `test` on every PR.
- Local `pre-commit` exit code 0/non-zero on `git commit`.
- A `.secrets.baseline` file in the repo root with the project's audited findings.

## Edge cases

- **`uv.lock` drift after a dependency change**: `uv sync` regenerates it; if the regenerated lockfile diff isn't committed, `lint`/`typecheck`/`test` may still pass on a developer's machine but fail in CI on a fresh resolution. The pre-commit `check-toml` hook catches malformed `pyproject.toml` but does not catch lockfile drift; rely on `just install` (`uv sync --extra dev`) before commit.
- **Pre-commit version drift**: hook versions in `.pre-commit-config.yaml` are pinned to specific tags. Dependabot's GH-Actions ecosystem doesn't update these — refresh manually or by an explicit issue when a tool's CI behaviour changes meaningfully.
- **A new high-entropy string lands legitimately**: re-run `uv run detect-secrets scan > .secrets.baseline` and commit the updated baseline in the same PR; mention the audit decision in the PR's `Operational impact` section.
- **`mypy` strict-mode noise on a third-party library**: prefer `# type: ignore[<error-code>]` at the use site over disabling strict mode; if the library is unstubbed (no `py.typed`), add a module override to `pyproject.toml`'s `[[tool.mypy.overrides]]` table.

## Out of scope

- Coverage reporting (post-demo #18).
- Mutation testing (post-demo #19).
- Performance benchmarks (post-demo #32).
- Multi-Python-version matrix (the project pins to 3.13 by decision).
- Caching beyond `astral-sh/setup-uv@v3`'s built-in cache.

## Verification

- `tests/test_smoke.py` passes (carried over from the scaffold — confirms the package imports under the CI environment).
- `tests/test_typing.py::test_strict_mypy_clean_on_package` is a placeholder marker; the `typecheck` CI job is the actual gate.
- Manual: open this PR, watch GitHub Actions run `lint`, `typecheck`, `test` — all three should report ✅.
- Manual: `pre-commit run --all-files` exits 0 on a clean checkout.

## Open questions

_None._
