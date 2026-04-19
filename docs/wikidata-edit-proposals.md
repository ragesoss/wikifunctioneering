# Wikidata edit proposals

When a change to Wikidata comes up in any context — a missing lexeme
sense link, an incorrect P5137 target, a new concept we need to host a
lookup — use this workflow instead of jumping straight to the API.
The workflow gives the reviewer (you) structured context before
posting, and it leaves a paper trail of *why* the edit was made.

## When to reach for this

- You notice a Wikidata item/lexeme/statement that affects our work
  and wants changing (missing, wrong, or could be improved).
- You want to propose a new Q-item or Lexeme sense.
- You want to flag an investigation for later without committing to
  a fix — the proposal format supports "no ops" backlog entries.

If you're just reading Wikidata to understand something, use the
utility scripts directly (`wd_inspect`, `wd_pattern`, `wd_senses`,
`wd_search`) without creating a proposal.

## The data model

A **proposal** is a JSON file at `proposals/<slug>.json`:

```
{
  "slug": "<slug>",                    // matches the filename
  "kind": "<shape>",                   // free-form; e.g. new_concept_item, investigate
  "status": "draft" | "posted",
  "rationale": "Prose. What, why, what we considered.",
  "probes": {                          // optional; see "Probes" below
    "related_lemmas": [...],
    "related_precedents": [...],
    "walk_up_levels": N
  },
  "entities_of_interest": [ ... ],     // for investigate-only proposals
  "ops": [ ... ],                      // the actual writes; see "Op vocabulary"
  "open_questions": [ "..." ],         // design decisions that are not yet settled
  "related_followups": [ ... ]         // notes for future proposals; not done here
}
```

Every field except `slug` and `ops` is optional. Status progresses
`draft → posted` automatically when `wd_apply.py --apply` succeeds.

## Before proposing a new Q-item: don't duplicate

Concept items on Wikidata are frequently labelled as **gerunds or
abstract nouns**, not as the verb form you'd reach for. The concept
behind software "save" is [Q66018493 "file saving"](https://www.wikidata.org/wiki/Q66018493)
— with "save" as an alias. The concept behind "copy" (the UI action)
is Q42282254 "copy" — a noun-form item that happens to share its
label with the verb. Before drafting a `create_item`:

- **Always check `wbsearchentities` with the proposed label.**
  `wd_propose` does this automatically for any `create_item` op, at a
  generous limit, and tags alias matches `[alias]` so they stand out.
  If a match comes back labelled with a gerund (`-ing`, `-tion`,
  `-ment`) or abstract-noun form of your verb, investigate that item
  first — it's probably the concept you want to link to.
- **Check if the concept is the gerund form of your verb.** "save" →
  "saving"; "edit" → "editing"; "delete" → "deletion." The Wikidata
  community often uses these forms as the canonical label even when
  multiple lexemes (verb + noun + gerund) could plausibly host the
  sense.
- **Inspect the candidate.** If its P31/P279 classification is at
  least sane (subclass of "command" / "software feature" / "user
  interface command"), and its description matches the sense you want
  to link, just use it. Creating a second item for the same concept
  is worse than an imperfect classification on the existing one.

Most `create_item` proposals that start with "we need a new Q-item
for X" end up being `add_sense` + `add_claim` to an existing Q once
the alias check runs.

## Workflow

1. **Draft** `proposals/<slug>.json` by copying one of the templates in
   `proposals/examples/`.
2. **Review:** `python scripts/wd_propose.py --slug <slug>`
   - Shows the proposal with every P/Q/L id labelled.
   - Auto-pulls fast context (parent concepts, one-hop classification).
   - Lists available slow probes; opt in with `--with name[,name…]`
     or `--full`.
   - Iterate the proposal file based on what the review surfaces.
3. **Dry-run:** `python scripts/wd_apply.py --slug <slug>`
   - Shows a **semantic diff** — entities/triples that will exist on
     Wikidata after the apply, with labels resolved.
   - Shows raw API payloads below for debugging.
4. **Apply:** `python scripts/wd_apply.py --slug <slug> --apply`
   - Logs in via bot password from `.env`.
   - Posts each op in order; resolves placeholders (e.g.
     `{NEW_CANCEL}`) to real IDs returned by earlier ops.
   - Updates the proposal file with a `posted` block recording
     timestamp, op results, and placeholder resolutions.
   - Retries with exponential backoff on `maxlag` errors.

## Op vocabulary

All ops have an `op` discriminator. The apply script dispatches on it.

### `create_item`

```json
{
  "op": "create_item",
  "placeholder_id": "NEW_X",            // optional; referenced by later ops
  "labels":       { "en": "...", ... },
  "descriptions": { "en": "...", ... },
  "aliases":      { "en": ["...", ...] },
  "claims": [
    { "property": "P31",  "value": "Q..." },
    { "property": "P279", "value": "Q..." }
  ]
}
```

Creates a new Q-item via `wbeditentity new=item`. Returns the new
Q-ID, which is stored in the placeholder environment so subsequent
ops can reference `{NEW_X}`.

### `add_sense`

```json
{
  "op": "add_sense",
  "lexeme": "L13009",
  "placeholder_id": "NEW_X_SENSE",
  "glosses": { "en": "..." }
}
```

Appends a new sense to an existing lexeme via `wbladdsense`. Claims
on the new sense should be added as separate `add_claim` ops.

### `add_claim`

```json
{
  "op": "add_claim",
  "entity": "<Q-ID | L-ID | L-Sn | {placeholder}>",
  "property": "Pxxx",
  "value": "<Q-ID | {placeholder}>"
}
```

Adds a statement via `wbcreateclaim`. Both `entity` and `value`
support placeholders resolved from earlier ops.

## Probes

`probes` declares context-gathering that the review script should
surface. All are SPARQL-based and opt-in:

- `related_lemmas: [...]` — for each lemma, show its English lexeme
  senses and any P5137 targets. Useful to see cross-word patterns.
- `related_precedents: [Q..., ...]` — full render of each Q-item:
  label, description, P31/P279, sample of P5137 backlinks. Useful
  to inspect the items you're modelling your proposal on.
- `walk_up_levels: N` — walk P279 up from each proposed P279 parent
  and from each `entities_of_interest` entry. Useful to catch weird
  upchain inheritance.

Enable with `--with name[,name...]` or `--full`:

```
python scripts/wd_propose.py --slug <slug> --with precedents,walk_up
python scripts/wd_propose.py --slug <slug> --full
```

## Rate limits and politeness

- Every write includes `maxlag=5` — stand Wikidata back-pressure
  signal, respected by default.
- Writes retry with exponential backoff (4 attempts starting at 12s)
  when the API returns `maxlag`.
- We sleep 2s between ops within a proposal.
- All of this works without the "high-volume editing" bot-password
  grant.

## AI disclosure

Every edit summary includes the line:

> Edit drafted with AI assistance (Claude Opus X.Y).

per the draft Wikifunctions/Wikimedia guidelines documented in
`docs/ai-disclosure.md`. Edit summaries also cite the proposal slug
so reviewers on-wiki can ask about it.

## Related utilities

For ad-hoc Wikidata questions that don't warrant a proposal:

- `wd_inspect.py <ID>...` — detail on Q/L/Sense/P entities.
- `wd_pattern.py --p31 X --p279 Y` — pattern-match classification.
- `wd_senses.py <lemma>...` — lexeme senses with P5137 targets.
- `wd_search.py "text"` — label search with noise filtered.

See `proposals/README.md` for the workflow-facing quick reference.
