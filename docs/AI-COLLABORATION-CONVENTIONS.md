# AI-Agent Collaboration Conventions

Process conventions for working with an AI coding agent (Claude Code, Cursor, Aider, etc.) on this repository. Ported from the `annotated-maps` project, with project-specific rules dropped:

- §7 (long-running branches), §7a (wave branches), §10 (midpoint audits), and §11 (burst mode) were dropped: this is a 4–6h spike with one-issue-per-PR all landing into `main`. Section numbering preserves the gap so memory-entry pointers stay valid.
- Project-board IDs in §2 are gtfs-dleung's, not annotated-maps's.
- Examples have been adapted to the spike's stack (uv / Streamlit / pytest) where the annotated-maps versions assumed Docker / Vite / Playwright.

These conventions overlap meaningfully with three established frameworks — **Definition of Done** (Scrum/Agile), **Google's "Small CLs" guidance** ([eng-practices](https://google.github.io/eng-practices/review/developer/small-cls.html)), and **Trunk-Based Development**'s feature-branch guidance ([trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/)). Where relevant, that overlap is noted under each rule.

---

## Quick reference (portable rule list)

Copy these statements verbatim into another project's CLAUDE.md / system prompt / agent instructions:

1. **Size every ticket to fit a single PR.** Split aggressively up front; many small tickets beats a few "natural" ones that don't land cleanly.
2. **Move ticket status as work progresses:** Todo → In Progress when the PR opens; In Progress → Done when the PR merges.
3. **Add every new issue to the project's default board** (whichever board represents "what we're working on now").
4. **Every PR body must include the following sections** (each detailed below): `Files changed` (§4a, alphabetical), docs/tests updates verified (§4b), `Test expectations` table only when failures are expected (§4c), `Work breakdown` mirroring the agent's task-tracker (§4d), and `Operational impact` (§4e, restart / rebuild / migration needs, or "none"; skip for pure doc/test PRs).
5. **Stamp commits with the current AI model name** (not a previously-used string) in the `Co-Authored-By:` trailer.
6. **Scan the actual diff for secrets, PII, and internal references before opening every PR** in a public repository.
7. _Intentionally absent — annotated-maps §7 (long-running-branch CI extension) and §7a (wave naming convention) do not apply here._
8. **This document is the master record; agent-memory entries are thin replicas pointing back here.** When a rule changes, edit the doc; the memory pointer's frontmatter is updated to match.
9. **When a cached operational value fails with a staleness-pattern error (404 / "not found" / "no such resource"), re-derive from the live source and update the cache before retrying.** Don't blindly retry, don't ask the user — refresh on first failure, escalate only if the fresh value also fails.

---

## Ticket and project-board hygiene

### 1. Size tickets to fit a single PR

> **Rule:** When filing tickets that will later be implemented by an AI agent, size each one so the work fits comfortably in a single PR without risking streaming-API idle timeouts. Split aggressively up front rather than mid-implementation.

**Why:** During the `nodes-rebuild` work on the annotated-maps project, the first oversized ticket hit the streaming-API idle timeout mid-implementation and had to be retroactively split, after which a re-evaluation of the surrounding tickets surfaced five more needing the same treatment. Predictable shapes that bite: backend tickets touching multiple controllers, anything with recursive CTEs, anything mixing backend + frontend, wholesale UI rewrites. Splitting up front saves the mid-PR rework.

This overlaps with [Google's "Small CLs"](https://google.github.io/eng-practices/review/developer/small-cls.html) guidance — same conclusion, different motivation (their version is review-quality-driven; ours is timeout-driven).

**How to apply:**

- **Calibration point:** for a streaming-context AI agent, a PR around 25–30 files / +1100 / -2200 lines runs close to the timeout. Anything bigger, or anything with extra build/test iteration cycles, is risky.
- **Default split heuristics:**
  - "Data + management API" tickets (CRUD + members + auth helper + bootstrap) → split CRUD vs. supporting ops.
  - Tickets that mix Pydantic schema work + UI + tests → at least three tickets.
  - Anything that touches both fetcher and parser and presenter → split unless trivially small.
- **One module + its tests** is usually a safe single-ticket unit. Anything beyond that, ask: does this need splitting?
- Cross-link the splits in ticket bodies ("`.b` depends on `.a`"); trim the parent's task list when splitting; mark out-of-scope items.

### 2. Update ticket status on the project board

> **Rule:** When working on tickets tracked on a project board, move the Status field through Todo → In Progress → Done as work progresses. Default cadence: In Progress when the PR is opened; Done when the PR merges.

**Why:** The board is the canonical view of "what's happening right now." Leaving stale statuses there means the human collaborator can't trust it for at-a-glance status, and they end up doing manual cleanup that should have been the agent's job. Cheap habit fix; avoids a recurring papercut.

This is essentially a Kanban WIP-discipline rule.

**How to apply:**

- **Todo → In Progress:** when the PR opens. Earlier transitions ("starting to think about it") aren't useful — open-PR is a clear, observable trigger.
- **In Progress → Done:** when the PR merges. Usually triggered by the human saying "PR merged"; that's the cue to flip the status.

**How to make this interruption-resistant:**

A "PR merged" message often arrives in the same turn as a "proceed to the next task" instruction. The natural failure mode is to jump straight into exploring the next ticket and forget the cleanup — *especially* if the next task triggers a clarifying question that diverts the conversation. The cleanup steps live entirely in the agent's head until they're done, so any interruption can drop them.

**The fix:** when a "PR merged" message arrives, the *first* tool call must be a `TodoWrite` capturing the cleanup checklist *before* any exploration of the next task. Concretely:

1. **First action**: `TodoWrite` with the cleanup item(s) at the top:
   - "Move #NNN board status to Done."
   - "Delete local branch `feat/NN-...` (remote was auto-deleted on merge)."
2. Execute those items, marking each completed as you go.
3. *Then* start the next task (which may itself open with a clarifying question — fine, the cleanup is already done).

Why this works: the todo list survives across model responses. Even if the next-task work triggers a clarifying question, even if the user replies with something unrelated, the unchecked cleanup items remain visible at the top of every turn.

**Skip the TodoWrite only if** the merged PR was into `main` AND the issue auto-closed (visible in the user's message or trivially confirmable). In that case the only manual step is the board flip — fine to do as a single direct tool call.

**Always verify after any `gh` command that affects the project board.** Multiple `gh` invocations can silently no-op the board side-effect: exit code 0, no output, no actual change. Confirmed instances on annotated-maps:

- **`gh project item-edit ...`** — the first board flip during a post-merge cleanup returned cleanly but the status stayed at In Progress; spotted only when the user noticed the wrong state on the next turn.
- **`gh issue create --project "..." ...`** — the project assignment silently dropped during a post-merge ticket file; required a follow-up `gh project item-add` and a verification read.

The fix is cheap: every board-affecting `gh` invocation should be paired with an immediate read-back. Either chain them in one shell command (`gh project item-edit ... ; gh project item-list ... --jq '.items[] | select(.content.number == NNN) | .status'`) or run a follow-up read tool call. The board's eventual-consistency window is short — a synchronous check in the same turn is sufficient.

Apply the same pattern to **any new board-affecting `gh` invocation** encountered going forward — silent no-ops appear to be a generic property of this CLI surface, not isolated to the two commands above. Don't mark the corresponding TodoWrite item completed until the read-back returns the expected state.

**Delete the local feature branch after the PR merges.** When merging PRs that auto-delete the remote branch, the local branch persists with a `: gone` upstream marker (visible in `git branch -vv`). These accumulate and clutter both `git branch` output and the agent's mental model of "what's still in flight." Add to the post-merge TodoWrite list:

- "Delete local branch `feat/NN-...` (remote was auto-deleted on merge)."

Run `git branch -D <name>` (force, since git can't always confirm the merge happened — the remote is already gone, and the commits are in `main` already if the PR merged). Skip if the branch is the current checkout — switch to `main` first.

To bulk-prune at any point, the safe one-liner is:

```bash
git fetch --all --prune                         # update : gone markers
git branch -vv \
  | awk '/: gone\]/ { print $1 }' \
  | xargs -r -n1 git branch -D
```

**Project-specific binding (gtfs-dleung "gtfs-dleung" board, project #2):**

```bash
PROJECT_ID="PVT_kwHOAAdfes4BXZQn"
PROJECT_NUMBER=2
PROJECT_OWNER="dcltdw"
STATUS_FIELD="PVTSSF_lAHOAAdfes4BXZQnzhSmX3c"
TODO_OPT="379cf780"
IN_PROG_OPT="c521ebc4"
IN_REVIEW_OPT="3efeeab7"
DONE_OPT="bf440fe6"
```

These IDs were captured 2026-05-11 at project creation. If they ever drift (project rename, etc.), re-derive via:

```bash
gh api graphql -f query='
{ user(login: "dcltdw") {
    projectV2(number: 2) {
      id
      field(name: "Status") {
        ... on ProjectV2SingleSelectField { id options { id name } }
      }
    }
} }'
```

#### 2a. Project-board operations — destructive-mutation traps

Two failure modes from the annotated-maps work, captured here so they aren't re-discovered the hard way:

**Trap 1: `updateProjectV2Field` regenerates *all* option IDs.** The mutation:

```graphql
updateProjectV2Field(input: {
  fieldId: "..."
  singleSelectOptions: [
    { name: "Todo", color: GRAY, description: "" }
    { name: "In Progress", color: GRAY, description: "" }
    ...
    { name: "Done", color: GRAY, description: "" }
  ]
})
```

…regenerates the `id` of *every* option in the list, even when names are unchanged. Every previously-tagged item then references a stale option ID and shows as untagged on the board. Issues themselves are unaffected; only the project field-value linkage breaks. Recovery requires re-tagging every item from session memory or git history.

There is no `updateProjectV2Field` variant that *appends* an option without rewriting the list. The safe path:

- **Use the GitHub web UI** (Project settings → field → "Add option"). The web UI preserves existing IDs.
- The CLI / GraphQL path doesn't have an additive equivalent (verified 2026-05-08).
- If the GraphQL path is unavoidable (e.g., automated provisioning), pre-snapshot all item-tag bindings (`gh project item-list ... --jq '.items[] | "\(.content.number)|\(.fieldValues...)"'`) before the mutation, then re-apply tags from the snapshot afterward.

**Trap 2: GraphQL is rate-limited at 5000/hour with a tighter secondary per-minute limit.** Every `gh project item-list`, `item-edit`, and `gh issue create` call hits the GraphQL quota. A burst of ~25 mutations during a recovery attempt can trigger the secondary limit; the historical reset window was 42 minutes.

How to stay under:

- **Snapshot, then iterate.** Do one `gh project item-list` to dump all item IDs into a local file, then loop edits — never re-query inside the loop.
- **Throttle destructive bursts.** If doing more than ~50 mutations in a sitting, add `sleep 2` between item-edits. Each `sleep 2` costs nothing; each rate-limit recovery costs ~42 minutes.
- **Don't combine** mass re-tagging with other destructive board work in the same hour.
- **Check before bursting:** `gh api rate_limit --jq '.resources.graphql'` shows remaining + reset epoch; aim for ≥ (intended_mutations + 100) headroom.

When rate-limited mid-burst, the safest move is to stop, log what was done, and return after the reset — cascading retries against a limited quota turn a 42-minute wait into a multi-hour one.

**Workarounds that don't use GraphQL.** During a rate-limit window the following still work because they hit the REST API:

- `gh issue close` / `gh issue reopen`
- `gh issue edit --body / --title` (label edits route through GraphQL — beware)
- `gh api -X POST repos/{owner}/{repo}/issues -f title=... -f body=...` (REST issue create — bypasses `gh issue create`'s GraphQL path; project membership has to be added later)
- All git operations
- All doc edits

### 3. Add every new issue to the default project

> **Rule:** Whenever creating a new issue, add it to the project's default "what we're working on" board afterward.

**Why:** All issues should live on one board by default; otherwise, drift between "filed" and "tracked" creates a backlog of orphan issues that no one is looking at.

**How to apply:**

```bash
gh issue create --title "..." --body "..."     # produces issue URL
gh project item-add 2 --owner dcltdw --url <issue-url>
```

For this repo: project number `2`, owner `dcltdw`.

---

## PR body conventions

### 4. Every PR body must include the following sections

> **Rule:** Every PR body must include the sections listed below. Each sub-section has its own conventions detailed in §4a–§4e:

| Sub | Section | When to include |
|---|---|---|
| §4a | `## Files changed` | Always |
| §4b | docs + tests verified | Always (state "no docs/tests needed" explicitly if so) |
| §4c | `## Test expectations` | Only when some CI checks are expected to fail |
| §4d | `## Work breakdown` | Always |
| §4e | `## Operational impact` | Always except pure doc-only / test-only / CI-only PRs |

Each sub-rule below carries its own **Rule / Why / How to apply** block.

#### 4a. PR body must include a "Files changed" section

> **Rule:** Every PR body has a `## Files changed` section — a bullet list of each file (sorted alphabetically by path) with a one-line summary of changes.

**Why:** Reviewers (and future archaeologists) get a clear at-a-glance map of what the PR touches without having to click into the diff. The one-line summaries also serve as a sanity check that the agent understood each file's purpose.

This is loosely covered by GitHub's own ["Writing a pull request"](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/best-practices-for-pull-requests) guide, but spelling it out as an alphabetical list with summaries goes further than most defaults.

**How to apply:** Place the section between the PR's Summary and the rest of the standard sections.

```markdown
## Files changed

- **gtfs_dleung/fetcher/static.py** — Adds the loader for the static GTFS bundle.
- **gtfs_dleung/parser/trip_updates.py** — Parses TripUpdates protobufs to domain models.
- **tests/test_parser_trip_updates.py** — New 8-assertion suite covering the parser.
```

#### 4b. Always update docs and tests with code

> **Rule:** Every PR must include relevant documentation and test updates. Verify both explicitly before opening the PR; don't conclude readiness without the check.

**Why:** Docs and tests are easy to skip on refactor PRs (where there's no behavior change but often new conventions worth documenting), and on "obviously" simple PRs where the agent's reflex is to declare the work done once the code compiles. A routine check is cheaper than re-prompting.

This is a classic Definition of Done item — most Scrum/Agile DoD checklists include both "tests updated" and "documentation updated" near the top.

**How to apply:**

Before opening the PR, run through both questions:

- "What docs reference the area I changed? Do they still match?"
- "Are there tests covering the area I changed? Do any need updating?"

For refactors with no behavior change, new shared helpers/patterns still often warrant a conventions doc. If truly nothing needs updating, **say so explicitly** in the PR description — e.g., "No docs/tests updated — refactor preserves behavior exactly and no convention docs exist yet."

**Two specific gaps the "alongside" wording does NOT catch by default — treat both as binding extensions of this rule:**

**§4b-1. Cross-cutting docs when adding a new top-level concept.** Adding a new domain primitive, a new Streamlit page, a new top-level API surface, or a new dependency — the SAME PR must update **README.md** (project structure, surface map) and **REQUIREMENTS.md** (§3 functional list and §5 routes table) for anything those docs name. Each individual sub-PR may feel narrowly scoped ("I'm just adding the TripUpdates parser"), but README/REQUIREMENTS describe the whole system; if no one updates them per-PR, they rot in aggregate. The annotated-maps closeout (PR #178) had to rewrite five top-level docs in a single PR because every sub-PR had been *locally* compliant with §4b while the system was *globally* non-compliant. Avoid that.

**§4b-2. New presenter surfaces need at least an import-and-render smoke check.** Backend / parser tests verify the data contract; they do not verify that a Streamlit page actually loads. When a PR adds a new presenter surface (page, panel, sidebar widget), ship a test in the same PR that at minimum imports the module and exercises any pure rendering helpers. If the surface is interactive (auth flow, form submit), consider scripting a `streamlit run` smoke check via `subprocess.run(..., timeout=10)` to catch import-time failures. A page that breaks at import time silently passes parser tests but breaks the demo.

**Verify lint and typecheck per-file on the touched files**, not just project-wide. The annotated-maps source called out ESLint's daemon-cache staleness specifically; the gtfs-dleung stack has no equivalent daemon, but the general principle still applies — when in doubt, run the linter directly on the diff:

```bash
git diff --name-only --diff-filter=AM main...HEAD \
  | grep -E '\.py$' \
  | xargs -r uv run ruff check
```

And for mypy:

```bash
git diff --name-only --diff-filter=AM main...HEAD \
  | grep -E '\.py$' \
  | xargs -r uv run mypy
```

The cold per-file invocation matches what CI will see.

#### 4c. PR Test Expectations section (only when failures are expected)

> **Rule:** When some CI checks are expected to fail (e.g., mid-rebuild on a long-running branch where one part of the system has outpaced another), include a `## Test expectations` table in the PR body listing each CI job/sub-step with its expected outcome and a one-line reason. Skip the section entirely when everything is expected to pass.

**Why:** Without an explicit expectations table, a reviewer (or future-self) sees a red CI run and has to reconstruct the design context to figure out whether it's "fine and expected" or "actual bug." A pre-declared table makes the review fast: scan, confirm reality matches, move on. Conversely, an "all green expected" table on every PR would be pure noise — the green checks themselves convey it.

For this spike (one issue per PR, all into `main`, all checks expected green), the section will rarely apply. Included for completeness; expect to omit it in practice.

**How to apply:**

- Use a small markdown table per CI job. Columns: **Job | Expected | Why**.
- Use ✅ pass / ❌ expected fail / 🟡 partial emojis to make the scan fast.
- For each ❌, give a one-line reason that points at the ticket / phase that will fix it.

#### 4d. Capture the agent's task-tracker breakdown in the PR body

> **Rule:** When opening a PR, include a `## Work breakdown` section that mirrors the agent's task-tracker list (e.g., Claude Code's TodoWrite) used while implementing the change. The list captures the work sequence next to the diff itself, so it stays durable after the originating conversation ends.

**Why:** The agent's internal task list captures planning and progress tracking during a ticket — what was sequenced first, what got added mid-implementation, where blockers led to course corrections. By default that list disappears when the conversation ends. Promoting it to the PR body preserves the trail next to the diff, which is more durable and more discoverable than the conversation transcript.

**How to apply:**

- Place the section between the PR's **Summary** and **Files changed** sections.
- Render as a numbered or bulleted list of the task contents in the order they were tackled. Match the granularity the agent actually used internally — don't rewrite for the PR. The point is showing the real sequence, not a cleaned-up post-hoc narrative.
- By the time the PR opens, every item is done; status emojis are redundant. If a task was deferred or abandoned, note it explicitly: `~~Add X~~ — deferred to follow-up #NNN`.
- For tasks added mid-implementation (after the initial plan), include them in their actual position so the trail reflects reality, not the original plan.

#### 4e. Surface operational impact (restart / rebuild / migration needs)

> **Rule:** When a change requires anything beyond a clean re-run of `uv sync` and `streamlit run`, explicitly state that step in (a) the conversation report when handing back to the user, AND (b) a `## Operational impact` section of the PR body. When a code/config change requires NO restart, say so explicitly too. Skip the convention entirely for doc-only or test-only PRs.

**Why:** A dependency change requires `uv sync` before the imports resolve. A Streamlit code change requires the running app to be stopped and restarted (Streamlit's hot-reload is not always reliable across module boundaries). A `.env.example` change reminds the user to update their local `.env`. Without these called out, the user hits "I changed something but my app shows the old behavior" — and a future reader of the PR loses context if the restart needed isn't recorded next to the diff. Saying "no restart needed" when none is needed is also valuable: it explicitly acknowledges the agent considered the question.

**How to apply:**

In the **conversation report** when handing back work:

- Always include a one-liner about what (if anything) needs restarting.
- Examples:
  - "No restart needed — pure parser change picked up on next `pytest` run."
  - "`uv sync` needed: new `pydantic-settings` dependency."
  - "Streamlit restart needed: stop and re-run `just demo` after pulling."
  - "`.env` update needed: `GTFS_INBOUND_RATE_LIMIT_REQUESTS` is new — add to local `.env` from the example."

In the **PR body**, add the section:

```markdown
## Operational impact

- **Deps**: run `uv sync --extra dev` (new test-only dep `pytest-httpx`).
- **Streamlit**: restart `just demo` after pulling.
- **Env**: no new vars.
```

If no operational impact at all, a single line is fine:

```markdown
## Operational impact

No restart, rebuild, or migration needed.
```

**When the rule does not apply:**

- **Pure doc PRs** (`docs/*.md`, README updates, comment-only edits).
- **Pure test PRs** that don't touch production code paths (e.g. test additions where the module under test is unchanged).
- **Workflow / CI-only PRs** (`.github/workflows/*.yml`) where the change only affects future CI runs.

For everything else (code, dependency changes, env-var changes, `pyproject.toml` changes), include the line.

**Branch switches count too.** When the agent switches the local checkout to a different branch, the running dev environment may change immediately. State explicitly: "switching from `branchA` to `branchB` — the Streamlit dev server (if running) will pick up `branchB`'s presenter on next file change." This prevents the "old code referencing missing dep / new dep not yet installed" surprise.

---

## Commits and repo-level practices

### 5. Stamp commits with the current AI model name

> **Rule:** When adding a `Co-Authored-By:` trailer to commits, use the actual current model name from the runtime environment — don't copy a previously-used string from earlier commits.

**Why:** Stale trailers misrepresent which model produced the change, which matters for later archaeology ("did we regress after model upgrade X?"). The agent's reflex is to copy the previous commit's trailer verbatim; that's wrong after any model upgrade.

**How to apply:**

- Before writing the commit-message HEREDOC, check the runtime environment for the line that names the active model and use that exact name.
- Format: `Co-Authored-By: Claude <ModelName> (<context-size>) <noreply@anthropic.com>` — e.g., `Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- If unsure, ask before guessing.

### 6. Public-repo diff scan before every PR

> **Rule:** This repository is public. Scan the actual diff (`git diff main...HEAD`) for secrets, PII, internal references, and debugging leakage before opening every PR.

**Why:** Public repos are visible to the world, indexed by search engines, and may be cloned by automated bots within minutes of pushing. Doing a small diff-scan once per PR is cheap; finding a leaked credential in commit history later is expensive (history rewrite + credential rotation).

This aligns with [OpenSSF Scorecard](https://github.com/ossf/scorecard) and the broader "secrets in commits" hygiene that tools like [gitleaks](https://github.com/gitleaks/gitleaks) automate. Treat the manual scan as defense-in-depth, not the only line of defense.

**How to apply:**

Before `gh pr create`, scan the diff and check for:

- **Live credentials:** `sk_live_`, `AKIA*`, `xoxb-`, `ghp_`, `glpat-`, real passwords (anything that's not a documented dev placeholder), real JWT secrets, OAuth `client_secret` values, SSH/TLS keys.
- **PII:** real names other than the project owner's public identity, real email addresses (other than the documented disclosure address), phone numbers, physical addresses.
- **Internal references:** internal hostnames (`*.internal`, `*.local`), private-range IPs (10.x, 172.16-31.x, 192.168.x), references to internal Slack/JIRA/Linear/etc.
- **Debugging leakage:** `print` / `pprint` / `logger.debug(...)` calls that dump secrets, tokens, request bodies, or full user objects.
- **Embarrassing content:** profanity, hot-takes about specific named people/companies, internal-team-only humor.

If anything ambiguous turns up, ask before pushing.

**The committed bcrypt hash in `.env.example` is intentional** — it is one-way and the underlying plaintext (`gtfs-demo-2026`) is documented in `docs/SECURITY.md` as the rotated-each-cycle demo credential. Don't try to "scrub" it; it's the example value.

**Beyond pre-PR scanning:**

- Confirm new files are added to `.gitignore` *before* they're created; don't rely on remembering later.
- Document third-party code attributions in code comments and project manifests.
- Avoid committing temporary debug files (`*.log`, `tmp_*.txt`, etc.).

### 7. _Intentionally absent._

In the annotated-maps source, §7 (long-running-branch CI extension) and §7a (wave-branch naming) covered multi-PR efforts that merged back to `main` as a unit. This spike uses one issue per PR with every PR landing into `main` directly, so neither rule applies. Section number is preserved here so memory-entry pointers to other sections remain stable.

---

## Meta — keeping these conventions current

### 8. Doc is the master record; memory entries are thin replicas

> **Rule:** This document is the authoritative source for the working agreements. The agent's per-project memory entries (e.g., `feedback_*.md` files under `~/.claude/projects/<project>/memory/` for Claude Code) are thin replicas — they exist so the agent's relevance matcher fires on the right rule, and their bodies just point back to the relevant section here.

**Why:** Two parallel sources of truth drift; one of them needs to win. The doc is the better master because: (a) it's reviewable in PR diffs, (b) it has structure (categories, cross-references, examples, the porting guide) that loose memory files don't, and (c) it's what a new collaborator or another project would actually consume. Memory's job is narrower — it just needs the frontmatter + filename + description so the relevance matcher can surface the right rule, then the agent reads this doc for the actual content. Treating doc as master eliminates the "did I update both?" discipline cost and removes the "which is right?" ambiguity when a drift is discovered.

**How to apply:**

When adding / modifying / removing a rule:

1. **Edit this document** — both the **Quick reference** one-liner *and* the per-rule expanded section (Rule / Why / How to apply). Renumber later rules if inserting; remove the entry if deleting; update the "Adapting" section if portability semantics changed.
2. **Update the memory pointer** — write/edit/delete the corresponding `feedback_*.md` so its frontmatter (`name`, `description`) matches the doc, and the body points to the new doc section. For new rules, also add the pointer line to `MEMORY.md`.
3. **Commit the doc change.** The memory update happens locally — memory lives outside the repo and isn't part of any PR.

**Memory body shape (thin replica):**

```markdown
---
name: <human-readable rule name>
description: <one-line description used by relevance matcher>
type: feedback
---
See [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md) §N for the full rule, why, and how to apply.
```

When the relevance matcher surfaces this entry, the agent reads the doc section to get the actual rule content — one extra Read, negligible cost.

**Operational-cache exception:** A few rules carry project-specific operational data that benefits from being in memory directly (no extra read needed mid-task) — e.g., cached GraphQL IDs for the project board. Those stay in the memory body alongside the pointer:

```markdown
---
name: ...
---
See [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md) §N for the full rule.

**Project-specific operational cache** (kept here for fast reuse):
- Project ID: PVT_xxx
- Status field ID: PVTSSF_xxx
- Option IDs: Todo=..., In Progress=..., Done=...
```

The split rule: **rule content → doc; project-specific operational caches → memory body.**

### 9. Refresh stale operational caches on failure (don't ask, don't retry blindly)

> **Rule:** When a cached operational value (e.g., a project board ID, a resource UUID, a known file path) is used in an operation and the operation fails with an error pattern consistent with cache staleness (404 / "not found" / "no such resource" against an ID that previously worked), re-derive the value from the live source, update the cache in the relevant memory file, then retry the operation. Don't blindly retry with the stale value, and don't ask the user — the operational cache is the agent's responsibility to maintain.

**Why:** Per §8 (doc as master), project-specific operational caches live in memory bodies (not the doc) — they're local shortcuts that bypass repeated API queries. They drift silently when the underlying resource changes (board rename, workflow file moved, ID-bearing entity recreated). Without a refresh-on-failure rule, the agent's options are: (a) retry blindly and fail again, (b) ask the user "what's the new ID?", or (c) silently skip the operation. All three are bad. A "stale → refresh → retry once" pattern catches drift loudly, self-heals, and doesn't burn user attention.

**Why not refresh proactively at every task start?** Most tasks don't touch the cached resource, so a proactive refresh is wasteful — both in API calls and in conversation context. First-failure refresh is the sweet spot: cheap when the cache is valid (the common case), self-healing when it isn't.

**How to apply:**

When using a cached value in an operation:

1. Run the operation with the cached value.
2. If it fails with a staleness-suggesting error:
   - Re-derive from the live source (specific command depends on what type of value — see the table below).
   - Update the cached value in the relevant `feedback_*.md` memory file.
   - Retry the operation with the fresh value.
3. If the fresh-derived value also fails: escalate to the user (the problem isn't cache staleness).

**What counts as a staleness-pattern error:**

- 404 / "not found" against a known-cached ID.
- "Project not found" / "field not found" against a project-board operation.
- "No such file or directory" against a known-cached path.
- Permission errors that suggest the resource was recreated under different ownership.

**NOT** staleness-pattern errors (different handling needed):

- Rate limiting (429) — back off and retry.
- Network timeouts — retry, no cache change.
- Validation errors (400) — fix the input, no cache change.
- Auth-token expiry — re-auth, no cache change.

**Common cache types and their re-derive sources:**

| Cache | Re-derive command |
|---|---|
| Project board IDs (Project, field, option) | `gh api graphql` query (see §2 for shape) |
| GitHub repo metadata | `gh api repos/<owner>/<repo>` |
| File paths in the project | `find` / Glob |
| External service IDs | each service's API |

---

## Adapting these conventions to other projects

When porting to another project:

- **§1 (ticket sizing), §4a (Files changed), §4b (docs+tests), §4c (Test expectations)** are fully tooling-agnostic — the rule statements transfer directly.
- **§4d (Work breakdown)** transfers as a concept; the specific name of the task-tracker tool (`TodoWrite` here) is Claude Code-specific. For other agents, swap in the equivalent tracker name.
- **§4e (Operational impact)** transfers as a concept; the specific restart/rebuild commands assume the gtfs-dleung stack (uv + Streamlit). Substitute your stack's equivalents.
- **§8 (doc as master)** transfers as a concept, but the specific memory-file format (`feedback_*.md` with frontmatter) is Claude Code-specific. For other agents, adapt the "thin replica" pointer shape to whatever per-rule storage that agent uses.
- **§2 (status lifecycle)** carries a project-board GraphQL ID block in **How to apply** that needs replacement with the new project's IDs.
- **§3 (default project)** has the project number / owner hardcoded — swap for your project's equivalents.
- **§5 (Co-Authored-By trailer)** assumes Claude; for other agents adjust the trailer format to match what the agent identifies as.
- **§6 (public-repo scan)** only applies if the repo is public. Skip it for private repos, but consider keeping the secrets-scan portion anyway — leaked credentials in private-repo history are still a risk if the repo's visibility ever changes.
- **§9 (refresh stale caches)** transfers as a concept; the specific re-derive commands depend on what type of cache value is at stake.

For long-running-branch and multi-PR-burst workflows (annotated-maps §7, §7a, §10, §11), see that project's `docs/AI-COLLABORATION-CONVENTIONS.md` directly — those rules are kept out of this doc because they don't fit the spike's one-issue-per-PR shape.
