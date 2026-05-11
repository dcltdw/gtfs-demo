# Retrospective

Written at the close of the 14-PR pre-demo set. Terse and honest — what worked, what didn't, what I'd change next time.

## What I learned

- **GTFS-RT's `schedule_relationship` is actually two enums.** Trip-level (`TripDescriptor.ScheduleRelationship`) and stop-level (`StopTimeUpdate.ScheduleRelationship`) overlap on names but mean different things: a trip's `CANCELED` rolls up to every stop, while a stop's `SKIPPED` doesn't affect its siblings. The parser collapses both into one user-facing enum so the UI can render a single label per row. Several "naive" implementations I've seen online conflate the two — and lose half the signal.
- **Partial StopTimeUpdate propagation is the moat between toy and serious code.** MBTA's TripUpdate feed sends an explicit delay for stop K and expects consumers to propagate it to every downstream stop on the trip. Dropping un-explicit stops would mean half the live arrivals show no delay even when there's a 5-minute backup. Walking the static stop_times in `stop_sequence` order with a `current_delay_seconds` accumulator is the right primitive; ~80 LOC of careful traversal in `tripupdates.py:140`.
- **`vehicle.id` vs `vehicle.label` vs `trip_id` is a beginner trap.** Three id-like strings, three different lifecycles. The parser keeps them separate and the tests assert it explicitly — pinning the bug rather than just hoping no one writes it.
- **Streamlit's `@st.cache_resource` is the right caching primitive for the spike scale.** Process-scoped, survives session reruns, doesn't leak between users. The decorator is one-character cheap; the equivalent in Flask would have been a session-state context I'd have to design.

## What surprised me

- **The conventions doc earned its keep repeatedly.** Multiple times I almost forgot to check the `pre-commit run --all-files` output before pushing; the §4b "verify docs and tests" reminder caught it. The "ticket sizing" rule kept me from bundling things that didn't belong together — twice I split a planned PR mid-implementation because the AC's spec-file list didn't match REQUIREMENTS.md's numbering.
- **Spec-file number drift was a recurring papercut.** Five PRs in a row hit the same shape: the issue body asked for `F-005-streamlit-ui` or `NF-002-inbound-rate-limit` or similar, but those slots were already taken in `REQUIREMENTS.md` by the time the issue was implemented. The fix every time was the same — fold the multiple AC-requested specs into the single correct slot, note the deviation in the PR body. The pattern is *fine*; the AC just wasn't kept in sync with the REQUIREMENTS as numbering settled. Next time: write the issues with reserved slot numbers up front, or accept that issue-AC drift is a normal cost of pre-planning.
- **Pre-commit vs CI version skew kept biting.** Pre-commit's `mirrors-mypy` and `ruff-pre-commit` lag the uv-managed venv by months. Every time I bumped a tool or used a newer language feature (PEP 695 generic syntax, `StrEnum`), pre-commit and CI disagreed. Eventually I added the runtime stack (`pydantic`, `streamlit`, `tenacity`, …) to pre-commit's `additional_dependencies` and bumped the mypy + ruff pins; that closed the gap. Worth documenting in the conventions doc as a "watch for this" entry.
- **`detect-secrets` is aggressive on test sentinels.** It flagged `_TEST_PASSWORD = "test-pass-..."` and `password="not-a-real-secret"` arguments in tests. Three `# pragma: allowlist secret` annotations later, the hook was happy. Worth the noise — the alternative (no detect-secrets) is worse.
- **The Mermaid diagram in README rendered better than I expected** on GitHub's web view. I went in assuming I'd have to fall back to a static PNG; the Mermaid output is browseable directly. (GH Pages with Jekyll defaults also handles it without config.)

## What I'd do differently

- **Pin the spec-number drift earlier.** When I noticed the third or fourth deviation, I should have edited the remaining open issues' AC text to use the correct F-NNN / NF-NNN numbers rather than continuing the per-PR "absorbs NF-X/Y/Z" pattern. A 5-minute edit on each upstream issue would have replaced 20 minutes of per-PR explanation.
- **Establish the `@pytest.mark.live` marker pattern earlier.** I planted it in PR #11 (the Streamlit UI) because that was the natural place to add a subprocess smoke test. But every previous parser PR (#3 through #8) could have used a `@pytest.mark.live` test against the real MBTA feed as a defensive check. Most caught nothing; one or two would probably have surfaced format quirks. The marker is cheap; introducing it in #3 instead of #11 would have given me a free regression net.
- **Cache the pre-commit `additional_dependencies` decisions in the conventions doc.** I rediscovered "you need `streamlit` in pre-commit mypy's deps" twice. A one-line entry in §4b ("when adding a new runtime import that the hook env doesn't see, add it to additional_dependencies") would have saved me the second discovery.
- **The "no-DB" decision is the right one for the spike but had a real cost I underestimated.** Every PR that introduced new state (rate limiters, health tracker, snapshot fallback) had to invent its own `dict[K, V]` + `threading.Lock` pattern. A tiny shared `StateRepository` abstraction would have made the test setup cleaner. Worth a follow-up issue if the project continues.
- **I'd commit a single trimmed `tests/fixtures/static-mini.zip` and reuse it everywhere** instead of building one in #3 and a separate set of trimmed `.pb` files in #4–#7. The fixture-build scripts are similar enough that one shared helper would have replaced four near-duplicates.
- **`streamlit-authenticator`'s API changed enough between versions that I spent ~30 minutes on it.** Reading the changelog before importing would have saved time. Same lesson as anyone who's worked with a mid-version Streamlit ecosystem.

## What I'd say to the next person who picks this up

Read [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md) first. The 9 numbered rules are how the work got done at this pace — small PRs, full bodies, status flips on the board, per-PR diff scans. Treat them as load-bearing.

Then read the three [ADRs](docs/adr/) — those tell you what's locked and what isn't. Anything not in an ADR is up for grabs.

Then read [docs/UPGRADE-PATH.md](docs/UPGRADE-PATH.md). It's specifically about migrating off the spike's "strict GTFS-RT, no DB, single-replica" choices. If the project's about to grow past the spike's shape, that doc is the runway.

The post-demo backlog (issues #15–#41) is intentionally sized to one-PR-each. Pick one, follow the conventions, ship.
