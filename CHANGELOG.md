# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
