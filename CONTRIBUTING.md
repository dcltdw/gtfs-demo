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
uv sync --extra dev          # install runtime + dev deps
uv run pre-commit install    # one-time: wire the local hooks
just test                    # pytest -v
just lint                    # ruff format --check + ruff check
just typecheck               # mypy --strict
just precommit               # pre-commit run --all-files (matches CI's lint + typecheck minus pytest)
```

The same three checks gate every PR in CI ([.github/workflows/pr-tests.yml](.github/workflows/pr-tests.yml)). If a check is red locally, it will be red in CI — fix locally first.

### Pre-commit hooks

`uv run pre-commit install` wires the hooks listed in [.pre-commit-config.yaml](.pre-commit-config.yaml):

- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-merge-conflict`, `check-added-large-files` — file hygiene.
- `ruff` (`--fix`) and `ruff-format` — auto-fix + format on commit.
- `mypy` — strict type-check on the staged files.
- `detect-secrets` — scans the diff against [.secrets.baseline](.secrets.baseline). New high-entropy strings fail the commit; resolve by either fixing the leak or, after audit, running `uv run detect-secrets scan > .secrets.baseline` and committing the regenerated baseline.

To run the hooks against the whole tree: `uv run pre-commit run --all-files`.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file security reports as public issues.
