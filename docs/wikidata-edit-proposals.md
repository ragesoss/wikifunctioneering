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
- **Go beyond the exact-label match.** `wd_propose` only shows
  label/alias matches on your proposed label. That's not enough. Also
  search synonyms and related phrasings (`wd_search "dismiss"`,
  `"exit"`, `"close dialog"`, etc.), and scan the existing members of
  the classification family you're proposing under
  (`wd_pattern --p31 Q4485156 --limit 300` then grep). The goal is to
  be confident no fit exists before you draft `create_item` — and to
  record in the proposal's rationale *what you searched and what you
  ruled out*, so the reviewer can see the diligence.
- **Watch for near-miss gerunds that aren't software-specific.**
  A gerund-form item like Q115655908 "closing" (P279 of "action", not
  software) is tempting but wrong as a UI-command target — adding
  P31 of the UI-command umbrella to it would assert that physical
  closing of doors is a UI command. A concept is only reusable if its
  classification is already software-adjacent (compare Q66018493 "file
  saving", which is explicitly a user operation). If the gerund isn't
  in software territory, create a new item.

Most `create_item` proposals that start with "we need a new Q-item
for X" end up being `add_sense` + `add_claim` to an existing Q once
the alias check runs. But not all — when you *do* need a new item,
rationale should explicitly list the candidates you rejected.

## Verb senses vs. noun senses: shape and property

**This is the single most important rule in this doc. It is actively
enforced on-wiki.** Our first two UI-command proposals (cancel,
close) were both reverted within hours by Mahir256 — one of the most
prolific Wikidata lexicographical editors — for violating it.

### The rule

A sense's **gloss shape** and **linking property** are dictated by
the lexeme's lexical category:

| lexical category | gloss shape | link property |
|---|---|---|
| verb (Q24905) | **infinitive predicate** — "to X something" | **P9970** "predicate for" |
| noun (Q1084) | noun phrase — "the act of X", "a thing that X" | **P5137** "item for this sense" |
| adjective (Q34698) | attributive phrase | P5137 |

From [Wikidata:Lexicographical_data/Documentation/Senses](https://www.wikidata.org/wiki/Wikidata:Lexicographical_data/Documentation/Senses):

> **P5137 ("item for this sense"):** "This property is used to link a
> sense representing a *substantive concept (typically on a noun or
> adjective)* to a Wikidata item representing the concept."
>
> **P9970 ("predicate for"):** "This property is used to link a sense
> representing a *predicative concept (typically on a verb or verb
> phrase)* to a Wikidata item representing the concept. In general,
> for some action/event/occurrence X described by an item, if a verb
> for 'to do X' and a noun for 'X' differ in the addition of a light
> verb, then the noun is connected to the item using P5137 and the
> verb is connected to the same item using this property."

The `wbsearchentities` community created P9970 *explicitly* so
P5137's scope didn't need to expand (see
[Property_talk:P5137#Use_on_Verb,_Adjective_and_Adverb_senses](https://www.wikidata.org/wiki/Property_talk:P5137)).
Using P5137 on a verb sense is the precise thing that thread
rejected.

### Anti-examples (our own reverts)

- Gloss **"software feature"** on a verb sense — wrong shape: it
  describes a noun ("a feature"), not an action. The gloss of
  Q42282254-family senses is widely imitated in our proposals, but
  those senses are themselves inconsistent with the rule above and
  may eventually be refined on-wiki.
- Gloss **"software command to dismiss or close..."** — still wrong
  shape ("a command that does X" = noun phrase). Correct verb shape:
  **"to dismiss or close a window, dialog, or panel"**.
- P5137 on a verb sense — wrong property. The correct link is
  **P9970**.

### The dogfooding conflict

Wikifunctions `Z33668 "word for concept"` currently follows P5137
only. Verb-category lookups for concepts linked via P9970 return
empty (Z28170 "the list is empty"). When adding verb senses, you
have two options:

1. Add the sense with the correct property (P9970) and accept that
   `Z33668` won't resolve it until Wikifunctions is updated — either
   by modifying Z33677 to also follow P9970, or by creating a
   parallel "verb for concept" function.
2. If a noun lexeme for the same concept exists, add the sense there
   with P5137 instead. Z33668 already works, and the property is
   correct.

### Gloss length (within the right shape)

Once the shape is right, length is a separate question. Policy sets
no length rule; community norm is disambiguation adequacy. Terse
glosses work well when the linked Q-item carries the encyclopedic
definition — e.g. a one-line verb predicate matching the style of
surrounding senses on the lexeme. Look at the existing senses of
the lexeme you're editing and match their voice.

### Sourcing

Mahir256's edits consistently add **P12510 (OED ID)** or similar
external-ID citations to each sense they touch. Adding a sense
without a source is not a revert trigger on its own, but expect
more scrutiny. If the sense is drawn from a dictionary, include
the citation.

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
   - **Paste the semantic-diff section into the conversation** so the
     user can approve or redirect before you apply. The user is the
     reviewer; hiding the diff behind a summary defeats the paper-
     trail purpose of the dry-run step. Raw API payloads can be
     omitted unless something looks off.
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
