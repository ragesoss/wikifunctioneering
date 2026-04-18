# Session: submitting the Z6832 lexemes-by-lemma primitive upstream

Date: 2026-04-18

Follow-up to the design/research/implementation work captured in
`2026-04-17-lexemes-by-lemma-primitive.md`. This note records what
got filed upstream, in what order, and the decisions made along
the way.

## Artifacts

- **Phabricator T423781** — https://phabricator.wikimedia.org/T423781
  Project tag: **#Abstract_Wikipedia**. Filed with provisional ZIDs
  Z6832 (function) and Z6932 (built-in) and a request for team
  confirmation.

- **function-schemata MR !339** —
  https://gitlab.wikimedia.org/repos/abstract-wiki/wikifunctions/function-schemata/-/merge_requests/339
  Adds the `Z6832.json` function shell, `Z6932.json` built-in
  implementation, and two new `dependencies.json` entries.
  Rebased on latest upstream main at push time (HEAD `37f3909`).

- **function-orchestrator Draft MR !643** —
  https://gitlab.wikimedia.org/repos/abstract-wiki/wikifunctions/function-orchestrator/-/merge_requests/643
  Carries the handler code, unit tests, end-to-end tests, mock
  harness extension, and a dedicated submodule-bump commit pointing
  at the fork's schemata branch HEAD (`37f3909`).

The orchestrator MR is **Draft-state** because its submodule pointer
references a SHA not yet reachable from upstream function-schemata.
CI is expected red until !339 merges; the MR description says so
explicitly. Once schemata merges, we re-point to the merged SHA
and mark Ready — that's tracked as its own task.

## Decisions made during submission

### Proceeding with provisional ZIDs instead of waiting for confirmation

The original plan was "file T423781, wait for the Abstract Wikipedia
team to confirm Z6832/Z6932 (or assign alternates), then push MRs."
We flipped this to "push now with Z6832/Z6932, adjust later if the
team reassigns."

Rationale: Z6832/Z6932 are the next unused slots in the natural range
and parallel Z6830/Z6930 and Z6831/Z6931 numerically — the default is
likely to stick. The search-and-replace cost if they get reassigned
is small (ZID strings appear in ~15 code locations across two repos,
all easy to grep). And the MR being visible to reviewers lets them
evaluate the design end-to-end, which accelerates any back-and-forth.

### Paired-MR strategy (Draft + Draft after) vs strict sequential

Considered strict-sequential (don't open orchestrator MR until schemata
lands) vs opening a Draft orchestrator MR immediately. Went with the
Draft — reviewers can look at both sides together, which matters more
for this particular change because the orchestrator side is the
substantive read (handler, dispatch, tests) and the schemata side is
just two small declaration files.

Durable rule from this: for any Wikifunctions change that spans
`function-schemata` and `function-orchestrator`, open the schemata
MR against upstream and a **Draft** orchestrator MR with the
submodule pointing at your fork's schemata SHA. Reverts to Ready
after the schemata MR lands and you re-bump the submodule.

### Cross-linking convention

- `Bug: T######` on its own line in each MR description. This is
  the Wikimedia idiom that makes the MR show up on the Phab task
  sidebar automatically (CodeReviewBot picks it up).
- Each MR's description links the other MR directly.
- One comment on the Phab task per major state change (MR opened, MR
  ready for review, MR merged) rather than updating the description.

### Credit / disclosure

Phab task description includes a light AI-assisted credit line
matching our `docs/ai-disclosure.md` convention. The submission
comment additionally pointed at https://www.wikifunctions.org/wiki/Talk:Z16684
as prior-art evidence of AI-assisted contributions landing usefully.

No formal policy on AI disclosure exists for Wikimedia code changes
yet — our practice is disclose-early, self-describe, don't bury it.

## What went smoothly

- The three-task-class rebase-test-push loop for a fresh branch.
- `ssh-keyscan gitlab.wikimedia.org | tee -a ~/.ssh/known_hosts` on
  first contact. Host keys verified against the published
  fingerprints the GitLab page shows (not this session; if they're
  ever questionable, cross-check against the banner at
  `https://gitlab.wikimedia.org/help/instance_configuration`).
- `git submodule status` with the `+` prefix to spot the "index
  says X, workdir is at Y" divergence after a submodule rebase.

## What was surprising / non-obvious

### Rebasing the schemata branch moved the SHA the orchestrator submodule recorded

The orchestrator's built-in-handler commit (`fc65576`) was made
before the schemata rebase and recorded the pre-rebase SHA
(`baa01a7`). After the schemata rebase to `37f3909`, the submodule
workdir was at the new SHA but the orchestrator's tree still
pointed at the old one. Needed a dedicated `submodule: Bump
function-schemata for Z6832/Z6932` commit to realign them before
pushing.

Lesson: when you rebase a submodule branch, the superproject
always needs a follow-up bump commit. Don't try to amend the
main feature commit to carry it — a separate commit is clearer in
review and lets you re-bump cleanly when the submodule MR later
squash-merges into a different SHA.

### GitLab's "fork new MR" URL defaults to fork→fork

The URL GitLab returns in the push-output banner
(`/ragesoss/<repo>/-/merge_requests/new?source_branch=...`) opens
the MR-creation page with the *fork's own main* as target, not
upstream. You have to manually change the target project in the
dropdown. Easy to miss.

### CodeReviewBot / Maintenance_bot picked up the right tags automatically

`Patch-For-Review` auto-added from !643's `Bug: T423781` reference,
and `Abstract Wikipedia team` triage tag appended by
Maintenance_bot. No manual project-tag management needed beyond
the initial `#Abstract_Wikipedia`.

## Current state

Twelve of fourteen submission tasks complete. The two outstanding
tasks are both maintainer-side-blocked:

- **#21** waiting for !339 to merge
- **#25** re-bump submodule to merged SHA + mark !643 Ready (blocked on #21)
- **#24** wait for !643 to merge and deploy (blocked on #25)

Nothing more to do from our end until reviewers engage. If !339 sits
more than 3–5 days with no activity, drop a nudge in
`#wikipedia-abstract-tech` on Libera IRC — keep it one sentence.

## Resumption checklist (whenever this comes off the shelf)

When !339 merges:
1. Note the squash-merge SHA on upstream main (GitLab shows it on the
   MR page after merge).
2. `cd upstream/function-orchestrator/function-schemata && git fetch
   upstream && git checkout <squash-sha>`.
3. `cd upstream/function-orchestrator && git add function-schemata &&
   git commit --amend` (amend the `submodule: Bump function-schemata`
   commit in place — the SHA is all that changes).
4. `git push --force-with-lease origin add-find-lexemes-by-lemma`.
5. Click "Mark as ready" on !643.

When !643 merges and deploys:
1. Refresh our local cache so `scripts/cache_query.py` sees Z6832 /
   Z6932.
2. Refresh `docs/future-helpers.md` (remove the blocked-on-platform
   note on the lemmas-by-lexeme entry, link the shipped ZIDs).
3. Add the ZIDs to `docs/existing-building-blocks.md` under
   Wikidata-access primitives.
4. Rewrite Z29517 (Z26184's current Python dict implementation) as
   a composition using Z6832, publish via `scripts/wf.rb`, connect
   it. The existing Z33697 tester ("sol → pa") should pass once
   connected, without the hardcoded `'sol': 'L328094-S2'` entry.

## Appendix: Phabricator task body (as filed)

Preserved here for reference / future resubmission if needed. The
actual filed version had `Z6832` / `Z6932` substituted in for the
`Z????` placeholders below.

```markdown
## Summary

Proposing a new Wikifunctions built-in that maps a lemma string to the
Wikidata lexemes having it as a lemma in a given language. This is the
reverse of the existing Z6830 ("find lexemes for a Wikidata item") and
plugs a gap that currently forces composition functions to fall back on
hardcoded Python dicts.

A tested implementation (orchestrator + function-schemata) is already
complete and ready to submit as MRs pending ZID allocation — see
"Implementation status" at the bottom.

## Motivation

Today there is no way to go from a string to a Wikidata lexeme inside
a composition. Z6830 goes item → lexemes; Z22138, Z21806 and friends
go lexeme → lemma; but nothing goes lemma → lexemes.

Concretely this blocks Z26184 ("solfege to sargam"). Its current code
implementation Z29517 uses a hardcoded Python dict mapping each
solfège syllable to a sense ID (e.g. `'sol' → 'L328094-S2'`). Every new
solfège variant — Italian `do`/`ut`, the `si`/`ti` split, foreign-language
syllables — requires a Wikifunctions code edit, even when the relevant
Wikidata lexeme and sense already exist. With this primitive, Z26184 can
be rewritten as a pure composition: the syllable string resolves to a
lexeme via this new function, its P5137 sense is walked to find the
scale-degree item, and the downstream Z6830 already covers the rest of
the pipeline to the sargam sense. After that, supporting a new
variant is a Wikidata edit only.

## Proposed signature

Z????  find lexemes by lemma
  K1: Z6     (lemma)
  K2: Z60    (language)
  returns: List<Z6095>   (lexeme references)

Parallels Z6830 deliberately: the `K2: Z60` language convention matches,
and the return type is the same list-of-lexeme-refs shape so results
can flow straight into existing lexeme-walking helpers.

## Implementation approach

No new Wikidata-side work required — the CirrusSearch keywords this
needs are already in production via T271776 ("Allow limiting lexeme
searches by language"):

- `haslemma:"<lemma>"` — exact lemma match
- `haslang:Q<id>` — language filter (via the Z60's language item)

The orchestrator handler is a thin wrapper over the same
`findEntitiesByStatements` / `dereferenceWithCaching` path Z6830 uses,
just with a different `srsearch` keyword (`haslemma:` instead of
`haswbstatement:`) and a distinct cache-key prefix in the shared
`ReferenceType.WIKIDATA_SEARCH` namespace.

One MediaWiki API call per invocation, namespace 146, response size
bounded by Cirrus (no pagination needed at the signatures people will
realistically use).

## Scope and non-scope (v1)

**In scope:**
- Exact lemma match only (not prefix / fuzzy).
- Filter by language.
- Returns lexeme references (Z6095); callers fetch full lexemes only
  as needed.

**Out of scope for v1 (can follow as separate primitives):**
- Lexical category filter. v1 returns all matching lexemes across
  categories; composition callers can filter downstream by inspecting
  each candidate's lexical category.
- Prefix / fuzzy matching (`haslemmaprefix:` etc.).
- Form-level lemmas — only head lemma is considered.

## Request

1. Please confirm or assign the user-facing Z8 ZID and the built-in
   Z14 ZID. Slots Z6832 and Z6932 are unused and parallel
   Z6830/Z6930 and Z6831/Z6931.
2. Any concerns about the signature (especially the decision to drop
   category-filtering from v1) best raised here before the MRs land.

## Related

- T271776 — productionised the `haslemma:` / `haslang:` CirrusSearch
  keywords this depends on.
- T370072 — parent task for the existing Wikidata-lexeme built-ins.
- T230833 — wbsearchentities lexeme language-filter bug; the reason
  we go through CirrusSearch rather than wbsearchentities.

Reported by: @Ragesoss. Implementation co-developed with Claude
(AI-assisted).
```
