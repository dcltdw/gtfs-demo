# gtfs-dleung — task recipes.
# Run `just` with no args for the list.

# Default: show the list.
default:
    @just --list

# Install all deps (runtime + dev) into a uv-managed venv.
install:
    uv sync --extra dev

# Run the test suite.
test:
    uv run pytest

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

# Run the Streamlit demo app (placeholder until the presenter ships).
demo:
    @echo "TODO: wire up `uv run streamlit run gtfs_dleung/presenter/app.py` once the presenter lands (#11)."

# Capture a snapshot of all three RT feeds for offline testing (placeholder).
snapshot:
    @echo "TODO: wire up the snapshot CLI once the fetcher lands (#4) and examples/ wiring lands (#13)."
