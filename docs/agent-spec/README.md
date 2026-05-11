# Agent spec

Structured specifications, designed to be consumed by both humans and AI agents working on this repository. Files in this directory follow the contract in [schema.md](schema.md).

## Why this exists

Narrative specs (`REQUIREMENTS.md`) are great for context but bad for automation: an agent cannot reliably tell "the relevant section for F-003" from a long prose document. The agent-spec format trades narrative flexibility for machine-readable structure:

- Each file is one requirement.
- Each file has YAML frontmatter declaring its ID, type, scope, and linked issue.
- Each file has the same sections in the same order, so the agent can grep for any of them.

## File naming

- **Functional**: `F-NNN-short-slug.md` — covers user-facing behaviour or system capability.
- **Non-functional**: `NF-NNN-short-slug.md` — covers cross-cutting properties (security, performance, reproducibility, ops).

`NNN` is a three-digit zero-padded sequence number scoped to the type. Slug is kebab-case, ≤ 6 words.

## Workflow

1. New requirement surfaces — file an issue first; add the `pre-demo` or `post-demo` label.
2. Write the F-NNN or NF-NNN file in this directory, linking to the issue in frontmatter.
3. Cross-reference from [REQUIREMENTS.md](../../REQUIREMENTS.md) §3 (functional) or §4 (non-functional).
4. Implementation PR updates the spec's `Status` and adds a "Verified in" link to the PR.

## Current specs

> Populated in later PRs (each pre-demo issue lands its own F-NNN or NF-NNN file). At scaffold time only [schema.md](schema.md) exists.
