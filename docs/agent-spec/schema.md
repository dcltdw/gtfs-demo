# Agent-spec file schema

Every file in `docs/agent-spec/` (other than this one and `README.md`) is one requirement and conforms to the contract below. The contract is enforced by review, not by tooling — the format exists so an AI agent can grep predictable section headers, not so a validator can fail a CI job.

## Filename

- Functional requirement: `F-NNN-short-slug.md` (e.g. `F-003-trip-updates.md`).
- Non-functional requirement: `NF-NNN-short-slug.md` (e.g. `NF-005-public-repo-posture.md`).
- `NNN` is zero-padded, three digits, monotonically increasing per type.
- Slug is kebab-case, ≤ 6 words, no trailing punctuation.

## Frontmatter

YAML at the top of every file:

```yaml
---
id: F-003                 # matches filename prefix
title: TripUpdates → arrivals board
type: functional          # one of: functional | non-functional
status: proposed          # one of: proposed | in-progress | shipped | deferred
issue: 5                  # tracking GitHub issue number
pr: null                  # the implementing PR number (set when work lands)
depends_on: [F-001, F-002]  # other spec IDs; empty list if none
owner: dcltdw
last_updated: 2026-05-11
---
```

Required keys: `id`, `title`, `type`, `status`, `issue`, `owner`, `last_updated`. Optional: `pr`, `depends_on`.

`status` transitions:

- `proposed` → `in-progress`: the implementing PR is open.
- `in-progress` → `shipped`: the implementing PR is merged.
- `proposed` → `deferred`: rolled to a post-demo issue; spec file retained for history.

## Body sections

Every spec body has the following H2 sections, in this order, with these exact titles:

1. `## Summary` — one-paragraph plain-language description.
2. `## Inputs` — bullet list of inputs to the system component (data, configs, env vars, upstream feeds).
3. `## Behaviour` — numbered list of observable behaviours. Each item is a single sentence.
4. `## Outputs` — bullet list of outputs (UI surfaces, log lines, files, downstream signals).
5. `## Edge cases` — bullet list of named edge cases, each with a one-line handling rule.
6. `## Out of scope` — explicit non-goals (helps future readers understand why the spec is small).
7. `## Verification` — how this is verified: which tests, which manual smoke check. Cross-link to test files.
8. `## Open questions` — bullet list, or `_None._`.

A non-functional spec replaces `## Behaviour` with `## Properties` (the cross-cutting invariants) and otherwise follows the same shape.

## Cross-linking

- Cite other specs as `[F-NNN](./F-NNN-short-slug.md)`.
- Cite the implementing issue as `#NNN` (GitHub auto-links).
- Cite source-of-truth conventions as `§N` against [docs/AI-COLLABORATION-CONVENTIONS.md](../AI-COLLABORATION-CONVENTIONS.md).

## Lifecycle

- The spec file lands in the same PR as the implementation (per §4b: docs and tests alongside code).
- The spec is updated when the corresponding code changes; if the spec falls out of sync, that is a bug worth filing.
- The doc-as-master convention (§8) applies: this schema is the master; any memory or other replicas point back here.

## Example skeleton

```markdown
---
id: F-NNN
title: <short title>
type: functional
status: proposed
issue: <issue number>
pr: null
depends_on: []
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

<one paragraph>

## Inputs

- <input 1>
- <input 2>

## Behaviour

1. <behaviour 1>
2. <behaviour 2>

## Outputs

- <output 1>

## Edge cases

- **<name>**: <handling>

## Out of scope

- <non-goal>

## Verification

- `tests/test_<area>.py::<test_name>` covers <scenario>.
- Manual: run `just demo` and confirm <observable>.

## Open questions

_None._
```
