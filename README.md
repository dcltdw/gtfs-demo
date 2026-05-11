# gtfs-dleung

A focused GTFS-RT exploration of the MBTA Red Line (Park St ↔ Davis Sq) and the Green Line E branch (Park St ↔ Ball Sq), built as a 4–6 hour spike to demonstrate transit-data competence.

## What and why

This project exists as a focused, time-boxed demonstration of GTFS-RT competence:

- Subscribe to MBTA's GTFS-RT feeds (TripUpdates, VehiclePositions, ServiceAlerts).
- Parse them against the static GTFS bundle, scoped to the Red Line and the Green Line E branch.
- Render an arrivals board, alerts panel, and feed-health panel via Streamlit.
- Ship two artifacts: a rendered notebook (read-only, hostable) and a live Streamlit app.

The deeper goal is to demonstrate the agent-and-human collaboration conventions in [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md) — small, well-scoped tickets with disciplined PR hygiene.

## Quickstart

```bash
uv sync --extra dev           # install runtime + dev deps into a uv-managed venv
uv run pre-commit install     # wire ruff / mypy / secrets-scan / file hygiene hooks
just test                     # run the test suite (pytest -v)
just lint                     # ruff format --check + ruff check
just typecheck                # mypy --strict against gtfs_dleung + tests
```

The same three checks (`lint`, `typecheck`, `test`) run in CI on every PR into `main` — see [.github/workflows/pr-tests.yml](.github/workflows/pr-tests.yml) and [docs/agent-spec/NF-012-ci-pipeline.md](docs/agent-spec/NF-012-ci-pipeline.md). Streamlit and CLI surfaces land in later PRs.

## Architecture

> ADRs, Mermaid diagram, and upgrade-path notes land in PR #12. The package layout is:
>
> - `gtfs_dleung/fetcher/` — static + realtime feed I/O. `static.fetch_static_feed()` downloads + caches the MBTA bundle.
> - `gtfs_dleung/parser/` — Protobuf and CSV → domain models. `static.load_feed_from_dir()` produces a `StaticFeed`; `static.filter_to_scope()` narrows to the demo corridors.
> - `gtfs_dleung/models/` — Pydantic v2 models, the canonical typed boundary.
> - `gtfs_dleung/store/` — snapshots and cached state (#26).
> - `gtfs_dleung/presenter/` — Streamlit UI (#11).
> - `gtfs_dleung/cli/` — one-shot scripts.
> - `gtfs_dleung/scope.py` — corridor constants.
> - `gtfs_dleung/config.py` — settings via `pydantic-settings`.

**Static vs. realtime split**: `gtfs_dleung.fetcher.static` handles the weekly-updated GTFS-static bundle from `cdn.mbta.com/MBTA_GTFS.zip` with a TTL-based cache. The realtime fetchers (TripUpdates, VehiclePositions, ServiceAlerts) land in #4 and poll their own endpoints on a polite interval (≤1 fetch / 10 s per feed). Each layer is independently testable: static via the committed `tests/fixtures/mbta-mini.zip`; realtime via captured protobuf snapshots (#13).

## Design decisions

> Locked decisions are tracked in [REQUIREMENTS.md](REQUIREMENTS.md) and refined as ADRs land. Highlights:
>
> - Strict GTFS-RT (not the MBTA V3 REST API). Trade-off captured in `docs/UPGRADE-PATH.md` (PR #12).
> - Python 3.13, uv-managed deps, MIT licence, public repo.
> - Two MBTA branches only (Red + Green E).

## Security

See [SECURITY.md](SECURITY.md) for the disclosure process and threat model. Demo-credential rotation policy lives in [docs/SECURITY.md](docs/SECURITY.md).

## Operational notes

> Runbook lands as `DEMO.md` in PR #14. Until then, treat this section as a placeholder for restart / rebuild / migration mechanics.

## Future work

The `post-demo` issues (#15–#41) sketch the natural follow-ons: live vehicle map, Docker packaging, observability, real auth, persistence, anomaly detection. They are explicitly out of scope for the spike.

## Demo script

> Two-paragraph runbook for the recruiter call lands in `DEMO.md` (PR #14) and `RECRUITER-NOTES.md` (same PR).

## Repository conventions

- All work routes through GitHub issues + PRs. See [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md).
- One issue per PR, sized to land in a single streaming-context turn.
- Public repo: pre-PR secret/PII diff scan is mandatory.

## Licence

MIT — see [LICENSE](LICENSE).
