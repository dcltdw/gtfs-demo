# gtfs-dleung — task recipes.
# Run `just` with no args for the list.

# Default: show the list.
default:
    @just --list

# Install all deps (runtime + dev) into a uv-managed venv.
install:
    uv sync --extra dev

# Run the fast test suite (excludes live-marker tests; matches CI).
test:
    uv run pytest -m 'not live'

# Run the live-marker tests (subprocess smoke, real feeds). Slow; not in PR CI.
test-live:
    uv run pytest -m live -v

# Run ruff lint.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-format with ruff (fixes safe lint findings + formats).
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Run mypy in strict mode against the package + tests.
typecheck:
    uv run mypy gtfs_dleung tests

# Run all pre-commit hooks against every file (matches CI's lint + typecheck minus pytest).
precommit:
    uv run pre-commit run --all-files

# Refresh the detect-secrets baseline. Audit results before committing.
secrets-baseline:
    uv run detect-secrets scan --exclude-files 'uv\.lock|\.venv/' > .secrets.baseline
    @echo "Baseline regenerated. Audit with: uv run detect-secrets audit .secrets.baseline"

# Run the Streamlit demo app (the recruiter-demo entrypoint).
demo:
    uv run streamlit run gtfs_dleung/app.py

# Capture a snapshot of all three RT feeds for offline testing (placeholder).
snapshot:
    @echo "TODO: wire up the snapshot CLI once the fetcher lands (#4) and examples/ wiring lands (#13)."
