# Contributing

This is a personal recruiter-demo spike; the work is sequenced in [GitHub issues](https://github.com/dcltdw/gtfs-dleung/issues). External contributions are not solicited during the spike phase, but constructive review comments and security reports are welcome.

If you want to engage anyway:

1. Open an issue first to discuss scope. The maintainer's bandwidth is small.
2. Conventions live in [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md). Read those before opening a PR.
3. The repository uses one issue per PR. Sized to land in a single streaming-context turn.
4. Every PR body must follow the §4 section conventions (`Files changed`, docs/tests, `Work breakdown`, `Operational impact`).
5. Tests and linting are gated by CI. Run `just test`, `just lint`, `just typecheck` locally before opening a PR.

## Local setup

```bash
uv sync --extra dev
just test    # runs pytest
just lint    # ruff
just typecheck  # mypy --strict
```

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file security reports as public issues.
