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
- Static GTFS feed loader (`gtfs_dleung.fetcher.static.fetch_static_feed`) with 7-day TTL cache, configurable cache dir + URL via `pydantic-settings`, identifying `User-Agent`, typed `StaticFeedError` on failure.
- Pydantic v2 models for `Stop`, `Route`, `Trip`, `StopTime`, `Shape`, plus a `StaticFeed` container (`gtfs_dleung.models.static`).
- Scope constants for Red Line (Park ↔ Davis) and Green Line E (Park ↔ Ball Sq) corridors (`gtfs_dleung.scope`).
- Route-aware corridor filter (`gtfs_dleung.parser.static.filter_to_scope`) that drops Green-B/C/D trips even where they share platforms with Green-E.
- `tests/fixtures/mbta-mini.zip` — a 7 KB GTFS bundle trimmed from the real MBTA feed; includes one out-of-scope route (the 39 bus) so the filter is exercised both ways.
- `scripts/build_test_fixture.py` — reproducible script for regenerating the fixture from a freshly-unzipped real MBTA feed.
- `docs/agent-spec/F-001-load-static-feed.md` — the spec file for static-feed ingestion.

### Changed

- README Quickstart and CONTRIBUTING now walk through the pre-commit + CI workflow.
- README Architecture section now describes the static-vs-realtime split and points at the corridor filter.
- GLOSSARY adds `route`, `trip`, `stop_time`, `service_id`, `shape`, `parent station`, and "trunk overlap" entries.

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
