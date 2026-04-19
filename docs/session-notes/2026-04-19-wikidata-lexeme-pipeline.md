# 2026-04-19 — Wikidata lexeme contribution pipeline

## What we built

A conversational CLI workflow for proposing, reviewing, and applying
Wikidata edits — motivated by the zblocks dogfood-i18n work, but
designed as a general tool for any Wikidata change that comes up in
any context.

### Scripts (under `scripts/wd_*.py`)

- `wd_common.py` — shared helpers: batched `wbgetentities`, SPARQL,
  `wbsearchentities`, label/description/claim extraction, ANSI styling.
- `wd_inspect.py <ID> [...]` — full detail on one or more Q/L/Sense/P
  entities, including a sample of lexeme senses that link via P5137.
- `wd_pattern.py --p31 X --p279 Y` — items matching a classification
  pattern, ordered by P5137 backlink count. Shows the parent item's
  own label/description as a header.
- `wd_senses.py <lemma> [...]` — for each English lemma, what senses
  exist and which concepts they link to via P5137.
- `wd_search.py "text"` — label search with a noise filter (templates,
  scholarly articles, patents, taxa, music releases, etc.)
- `wd_propose.py proposals/<slug>.json` — render a proposal: ops
  labeled, rationale, open questions, follow-up notes, and context
  that's either auto-inferred or declared in the proposal's `probes`
  block. Default is fast (entity labels only); opt into slow SPARQL
  probes with `--with name[,name…]` or `--full`.
- `wd_apply.py --slug <slug>` — dry-run by default, producing a
  **semantic diff** (entity-level changes, labels resolved) followed
  by the raw API payloads. `--apply` actually posts to Wikidata, with
  maxlag=5 + exponential-backoff retry on maxlag errors.
- `wikidata_session.py` — bot-password session module (reads
  `WD_BOT_USERNAME` / `WD_BOT_PASSWORD` from `.env`).

### Data files

- `proposals/` — session-local working artifacts (.gitignored).
  - `proposals/examples/` — curated worked-example templates checked
    into git. Cover the three main shapes: simple `create_item`, a
    three-op chain (`create_item` + `add_sense` + `add_claim` with
    placeholder resolution), and an investigate-only (no-ops) proposal.
  - `proposals/README.md` — workflow documentation.

### Wikidata edits landed

- **Q139480165** "user interface command" — new umbrella concept,
  dually classified as P279 of Q4485156 "software feature" and
  Q1079196 "command."
- **Q139480774** "cancel" — UI-action concept item, P31 of the new
  umbrella.
- **L13009-S4** — new English sense on the "cancel" lexeme, linked to
  Q139480774 via P5137. (The gloss was refined on-wiki from our
  proposed "software feature" to "software command to stop or abandon
  an initiated or pending action" — improvement.)

## Design decisions worth remembering

**Proposals as a data model.** Each proposal is a JSON file with
`ops`, `rationale`, optional `probes`, `open_questions`, and
`related_followups`. Status lifecycle: `draft → posted`. The
`related_followups` field is how we capture "we noticed this other
thing that could become its own proposal" without scope-creeping the
current proposal — the human decides when to spawn a new proposal
file from a follow-up note.

**Proposals are session-local, not source.** Check them into git only
if they become exemplar templates. This prevents the `proposals/`
directory from becoming a graveyard of posted/abandoned work.

**Fast by default, slow on request.** SPARQL aggregation queries can
take seconds each; default proposal rendering is under a second by
skipping them. Probes are opt-in via `--with` / `--full`. This is
essential for the chat-driven iteration pace.

**Semantic diff > API diff for review.** The default `wd_apply`
dry-run output shows "what changes on Wikidata" (new Q, new sense,
new triple — with labels) rather than "what POST requests will be
sent." Raw payloads still appear below the semantic view for
debugging, but the semantic view is what the human reads to decide.

**Placeholder chaining across ops.** `{NEW_CANCEL}` and
`{NEW_CANCEL_SENSE}` let later ops reference entities that don't
exist yet at proposal-writing time. `wd_apply` resolves them after
the earlier op posts, substituting into both the `entity` and `value`
fields of subsequent ops. The dry-run view makes placeholders
visible with brace syntax.

**maxlag retry is not optional.** First live post hit
`mwoauth-invalid-authorization-wrong-wiki` (wrong consumer scope —
switched to bot password), then `maxlag: 6.18s lagged` (cluster
was backed up). Added exponential-backoff retry (4 attempts starting
at 12s). Second post succeeded on retry 2. Keep this in `wd_apply.py`.

**Dedicated lexeme senses for UI meanings.** Precedent from Q42282XXX
family (copy/cut/find): each has a dedicated "software feature" sense
on its English lexeme, separate from the broader verb sense. Initial
inclination was to link L13009-S1 directly via P5137, but S1 is too
broad ("to cause something to no longer have effect" covers contract
cancellation, event unscheduling, revocation, …). Adding a new sense
is the cleaner lexicographic model and matches established practice.

## Lessons / things to fix later

**The terse "software feature" gloss is probably bad UX.** We
proposed it to exactly match the Q42282XXX precedent, but a real
editor immediately refined L13009-S4 on-wiki to "software command
to stop or abandon an initiated or pending action." Future proposals
should use richer glosses by default rather than matching a terse
precedent.

**Read-only scripts don't benefit from bot-password auth.** Anonymous
rate limits are generous for our workload; SPARQL rate limits are
IP-based and bypass auth entirely. Don't add auth to `wd_inspect` /
`wd_pattern` / `wd_senses` / `wd_search` / `wd_propose`.

**Backlog proposal captured:** `investigate-command-sources-of-law`
(ignored from git). Q1079196 "command" transitively inherits
Q846882 "sources of law" via Q1665268; affects every UI-command
concept under our umbrella. Low-priority but worth investigating.

**Existing zblocks bug surfaced:** `zblocks/i18n/mappings.json` uses
Q3305941 for "save," but Q3305941 is the soccer-goalkeeper sense. Will
need a new "save (software feature)" Q-item in the Q42282XXX family
+ mappings update. Captured as a follow-up in the umbrella proposal.

## Pointers for future sessions

- Run `python scripts/wd_propose.py --slug <slug>` to review any
  proposal fast. Add `--full` once you want the SPARQL-heavy context.
- Start a new proposal by copying one of `proposals/examples/*.json`
  to `proposals/<your-slug>.json` and editing. The README in
  `proposals/` documents the op vocabulary.
- The umbrella proposal's `related_followups` section lists 5
  follow-on proposals worth considering next — reclassifying the
  Q42282XXX family, reclassifying Q513420, per-language cancel links,
  the sources-of-law upchain, and the zblocks save mapping fix.
