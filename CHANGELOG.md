# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI pipeline (`.github/workflows/pr-tests.yml`) with parallel `lint` / `typecheck` / `test` jobs on Python 3.13 + uv; cancel-in-progress on PR commits, every push to `main` verified.
- `.pre-commit-config.yaml` with ruff, mypy, `detect-secrets`, and file-hygiene hooks; `.secrets.baseline` checked in.
- `pre-commit` + `detect-secrets` added to dev deps; `just precommit` recipe runs the full hook suite.
- `docs/agent-spec/NF-012-ci-pipeline.md` — the spec file for the CI gate.
- `tests/test_typing.py::test_strict_mypy_clean_on_package` — placeholder marker (the CI `typecheck` job is the real gate).

### Changed

- README Quickstart and CONTRIBUTING now walk through the pre-commit + CI workflow.

## [0.0.1] — 2026-05-11

### Added

- Initial project scaffold: package layout (`gtfs_dleung/{fetcher,parser,store,presenter,cli}`), uv-managed dependencies on Python 3.13, MIT licence, `.gitignore`.
- Documentation skeletons: `README.md`, `REQUIREMENTS.md`, `docs/agent-spec/` (`README.md`, `schema.md`), `docs/SECURITY.md`, `docs/GLOSSARY.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- `docs/AI-COLLABORATION-CONVENTIONS.md` ported from the annotated-maps project — universal rules only (ticket sizing, status lifecycle, default board, PR body sections, commit co-author, public-repo diff scan, doc-as-master, stale-cache refresh). Wave / cadence / midpoint / burst rules dropped as spike-inappropriate.
- `.env.example` with bcrypt-hashed demo credential (rotation policy in `docs/SECURITY.md`).
- `.github/` templates (issue, PR, CODEOWNERS, dependabot).
- `justfile` recipes (`install`, `test`, `lint`, `typecheck`, `demo`, `snapshot`).
- `tests/test_smoke.py` smoke test confirming the package imports cleanly.

[Unreleased]: https://github.com/dcltdw/gtfs-dleung/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/dcltdw/gtfs-dleung/releases/tag/v0.0.1
