# ADR 0001 — Streamlit, not Flask (or FastAPI)

- **Status**: Accepted
- **Date**: 2026-05-11
- **Author**: dcltdw

## Context

A 4–6h spike has a budget problem: every hour spent on web-app plumbing (templates, routing, asset bundling, login forms) is an hour not spent on the GTFS-RT competence that's actually being demonstrated. The recruiter audience is a transit-systems team; the page exists to make the parser work visible, not to showcase web-framework choices.

## Decision

Use [Streamlit](https://streamlit.io/) as the presenter layer. The Streamlit page is the single entrypoint (`gtfs_dleung/app.py`) and composes the existing typed-Python surface with no HTML, no JS, no separate API tier.

## Consequences

**Gained:**

- Zero scaffolding cost for the auth widget, layout, sidebar, and live-refresh — `streamlit_authenticator.Authenticate(...)` + `st.columns(...)` + `st_autorefresh(interval=15_000)` is the whole UI shell.
- Pure-Python testability is preserved because every helper the page calls into is Streamlit-free. `gtfs_dleung.presenter.formatters` has 41 unit tests; the Streamlit page itself only has an import-smoke + a `@pytest.mark.live` subprocess test.
- The recruiter sees the live data path during a screen share — no demo deploy required.

**Lost:**

- **No public HTTP listener.** A real production deployment that needs to accept webhook callbacks or expose an API can't use Streamlit. The post-demo HTTP/Prometheus surfaces (#21 health endpoint, #33 metrics endpoint) will require a Flask or FastAPI sidecar.
- **Session-only state.** Streamlit's `st.session_state` is process-local and per-tab. Inter-user features (a shared alert feed, multi-tenant authz) need a real backend.
- **Coarse re-render model.** Every interaction or autorefresh tick reruns the whole page top-to-bottom; pre-Streamlit-1.30 there was no fragment-level partial rerun. Cheap at the spike's scale (one user, no large datasets); a real production page would care.
- **Less flexibility for visualisation.** Custom interactive maps or charts beyond Streamlit's built-ins require `streamlit-components` shims with React boilerplate.

## Alternatives considered

- **Flask + Jinja**: 2–3h of routing/template setup before the first GTFS surface renders; pays off only if the project continues past the spike.
- **FastAPI + a separate React SPA**: 8h+ of scaffolding; out of scope for a 4–6h spike.
- **Jupyter notebook**: rejected as the only deliverable — the recruiter audience expects to see a *live* app, not a static rendered notebook. A notebook is shipped *alongside* per [REQUIREMENTS.md](../../REQUIREMENTS.md) §1, but isn't the demo surface.

## When to revisit

If the project ever serves more than one concurrent user, exposes a programmatic API, or needs to receive inbound webhooks. At that point split into: a FastAPI service for the API + a Streamlit dashboard for ops-internal monitoring. See [docs/UPGRADE-PATH.md](../UPGRADE-PATH.md).
