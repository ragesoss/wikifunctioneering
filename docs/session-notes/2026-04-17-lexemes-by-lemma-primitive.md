# Session: platform-side "lexemes by lemma" primitive

Date: 2026-04-17

Context: Z26184 ("solfege to sargam") still depends on Z29517's
hardcoded Python dict because we can't go from a solfege *string* to
the corresponding Wikidata lexeme inside a composition. The 2026-04-17
raw-JSON session flagged this as "blocked until Wikifunctions gains
native lexeme search or sandbox egress." This session researches what
the native-lexeme-search side of that would actually look like.

## How Wikifunctions built-ins are wired today

A Z14 implementation has three mutually exclusive slots: **Z14K2**
(composition), **Z14K3** (code), **Z14K4** (built-in). When Z14K4 is
set, the ZObject body itself carries no logic — the ZID is just a key
the orchestrator uses to dispatch to a platform-side handler.

Example: Z6830 "find lexemes for a Wikidata item" (Z6091, Z6092, Z60
→ list of Z6095). Its only implementation, Z6930, has the shape:

```json
"Z2K2": {
  "Z1K1": "Z14",
  "Z14K1": "Z6830",
  "Z14K4": { "Z1K1": "Z6", "Z6K1": "Z6930" }
}
```

Nothing else. The real code lives in the **function-orchestrator**
(Node.js service at
`gitlab.wikimedia.org/repos/abstract-wiki/wikifunctions/function-orchestrator`),
not in the MediaWiki WikiLambda extension:

- `src/builtins.js` — a `builtinFunctions` Map from ZID to handler
  (lines ~1696–1717). Z6920, Z6921, Z6925, Z6926, Z6930, Z6931, Z6939
  are all registered here. Each entry points at a `BUILTIN_*` JS
  function defined in the same file.
- `src/builtins.js` lines 471–476 — `BUILTIN_FIND_LEXEMES_FOR_ITEM_`
  unwraps the three Z-typed args to (QID, PID, language code) and
  calls `invariants.resolver.findLexemesForEntity(...)`.
- `src/fetchObject.js` — class `Resolver`. `findLexemesForEntity`
  (~line 1132) wraps `fetchLexemesForEntity` (~1083), which delegates
  to `findEntitiesByStatements` (~1010).

### How the Wikidata side is actually queried

There is **no in-process Wikibase PHP** in this stack. The orchestrator
talks to Wikidata over HTTP from Node:

- Entity reads: `action=wbgetentities` and
  `Special:EntityData/<ID>.json`.
- Z6830's lexeme search:
  `action=query&list=search&srnamespace=146&srsearch=haswbstatement:P<pid>=Q<qid>`
  (namespace 146 = Lexeme). When a Z60 language is passed, an
  `inlanguage:<code>` prefix is prepended.

So "built-in" here really means "CirrusSearch via the MediaWiki API,
with a thin Node wrapper that unwraps Z-types and re-wraps the result
as a typed list."

## What "lexemes by lemma" should look like

CirrusSearch already supports two keyword queries that are the exact
pieces we need (Phabricator T271776 — "Allow limiting lexeme searches
by language"):

- `haslemma:<string>` — matches lexemes whose lemma is exactly
  `<string>`.
- `haslang:Q<id>` — matches lexemes whose language is the Wikidata
  item `Q<id>`.

Lexical category is similarly reachable with `haswbstatement:P31=Q...`
on the lexeme's category property (lexeme category is `P5185` in
practice, but it's the same pattern Z6830 already uses).

That means **every wire-level ingredient we need is already in
production.** A new built-in primitive is a very small delta against
the existing `findEntitiesByStatements` function — not a new subsystem.

### Proposed function shell (on-wiki)

```json
{
  "task": "function",
  "label": "find lexemes by lemma",
  "description": "Search Wikidata for lexemes with a given lemma, optionally filtered by language and lexical category. Returns lexeme references.",
  "inputs": [
    {"label": "lemma",    "type": "Z6"},
    {"label": "language", "type": "Z60"},
    {"label": "category", "type": "Z6091"}
  ],
  "output_type": {"Z1K1": "Z7", "Z7K1": "Z881", "Z881K1": "Z6093"}
}
```

Notes:

- Output is `List<Z6093>` (lexeme reference), not `List<Z6005>` (full
  lexeme). Consistent with the "reference out, caller decides whether
  to fetch" rule in `docs/wikidata-integration.md`. Any caller that
  needs the full lexeme pipes the result through Z6825 (fetch lexeme).
  Sense extraction — the actual downstream need for solfège→sargam —
  goes via Z6830 once you have the item, or via existing
  lexeme-walking helpers once you have the lexeme.
- Z60 for language matches Z6830's signature exactly. The handler
  resolves Z60 to the Wikidata item whose Q-id goes into `haslang:`
  (Z60 already carries that mapping internally).
- Category as Z6091 (item reference — e.g. Q1084 for noun) rather
  than Z6092 (property reference) — it's an *item* in the
  `wikibase-item` datatype of P5185.

Category could reasonably be optional, but Wikifunctions function
signatures don't support optional inputs in a first-class way. The
three-arg mandatory signature is simplest and matches Z6830's
precedent. A caller that doesn't want to filter by category can pass
Q1084 (noun) or whatever the dominant category is; a thinner "any
category" variant can be a second function if needed.

### Proposed built-in ID and handler

Next available `Z69xx` — Z6932, Z6933, Z6934 and neighbours in that
block appear to be reserved for related lexeme built-ins; the
Wikifunctions team would pick the actual ID. Using `Z6932` as a
placeholder here.

In `function-orchestrator/src/builtins.js`:

```js
// Parallel to BUILTIN_FIND_LEXEMES_FOR_ITEM_
async function BUILTIN_FIND_LEXEMES_BY_LEMMA_(Z6, Z60, Z6091, invariants) {
  const lemma    = Z6.Z6K1;
  const langCode = Z60.Z60K1.Z6K1;  // natural-language code
  const catQid   = Z6091.Z6091K1.Z6K1;
  return invariants.resolver.findLexemesByLemma(lemma, langCode, catQid);
}
builtinFunctions.set('Z6932', BUILTIN_FIND_LEXEMES_BY_LEMMA_);
```

In `src/fetchObject.js`, add to the `Resolver` class:

```js
async findLexemesByLemma(lemma, langCode, categoryQid) {
  // Shape mirrors findEntitiesByStatements, but the srsearch
  // combines three CirrusSearch keywords rather than one.
  const langQid = await this.resolveLanguageItemFromCode(langCode);
  const srsearch = [
    `haslemma:"${escapeQuoted(lemma)}"`,
    `haslang:${langQid}`,
    `haswbstatement:P5185=${categoryQid}`,
  ].join(' ');
  const params = {
    action: 'query',
    format: 'json',
    list: 'search',
    srnamespace: 146,
    srsearch,
    srlimit: 50,
  };
  const hits = await this.mediaWikiApiCall(this.wikidataUri_, params);
  return hits.query.search.map((h) => wrapAsZ6093(h.title));
}
```

The `escapeQuoted` / `wrapAsZ6093` helpers are already present in
`fetchObject.js` in shape — the existing `findEntitiesByStatements`
does the same wrap-and-return dance.

### Why this is efficient

- **One API call** per invocation — a single MediaWiki `list=search`
  request, same transport the orchestrator already uses for Z6830.
  Cost is identical to an existing built-in.
- **Caching is free.** The orchestrator already memoises Wikidata API
  responses per request-scope; a new endpoint with the same shape
  inherits that automatically. Whatever memcached layer backs
  Wikidata caching for Wikifunctions (the one CLAUDE.md warns about)
  covers this too.
- **Result set bounded by CirrusSearch.** `haslemma:` hits on a
  specific lemma + language + category are typically O(1)–O(10)
  results, well under the `srlimit=50` ceiling. No pagination
  complexity.
- **Purely additive.** Doesn't touch composition/code runtimes, doesn't
  need sandbox egress, doesn't interact with the Python evaluator.
  Only files changed in `function-orchestrator`: `builtins.js`,
  `fetchObject.js`, plus one unit test file. Plus the two on-wiki
  ZObjects (Z8 shell + Z14 built-in).
- **No new Wikidata-side work.** `haslemma:` / `haslang:` were
  productionised by T271776 and are live today. This primitive is
  purely a thin wrapper exposing existing search capability as a
  first-class Wikifunctions function.

### Why this specific signature instead of the alternatives

- **"Just expose `wbsearchentities?type=lexeme`"** — rejected. That
  endpoint's language filter is known-broken (Phabricator T230833:
  returns `und` for many languages), doesn't let you pin lexical
  category, and matches prefix/fuzzy, not exact lemma. The
  CirrusSearch `haslemma:` path is the one the Wikibase search team
  themselves point to.
- **"Accept Z6091 for language instead of Z60"** — rejected. Z6830
  uses Z60 and resolves language code internally; sticking with the
  Z60 convention keeps both built-ins callable with the same
  `Z1002`/`Z1430`/etc. values and avoids forcing callers to know the
  language Q-id.
- **"Return Z6005 (full lexeme) to save a fetch"** — rejected for
  two reasons. (1) Callers often want to filter the candidate list
  before fetching (e.g. pick the lexeme that has a P5137 sense
  pointing at a specific item). Pre-fetching all candidates wastes
  the work on discards. (2) `findEntitiesByStatements` gives us page
  titles, not full entities, so returning `Z6093` is zero extra cost
  whereas `Z6005` requires N follow-up `wbgetentities` hits. Keep
  the primitive cheap; let composition decide what to fetch.

## How this unblocks Z26184

Current Z29517 logic:

```
input: "sol" (Z6) → hardcoded dict lookup → "L328094-S2" (sense ID)
```

Post-primitive composition:

```
input "sol" (Z6)
  → [Z6932] find lexemes by lemma (lemma="sol", lang=English, cat=noun)
  → [Z6830] for each candidate lexeme's item(?), find senses matching
    scale-degree item via P5137
  → filter to the sense whose P5137 points to the dominant scale degree
  → return sense ID or lemma of the matching sargam lexeme
```

The cleaner shape actually uses Z6830 for the *sargam side* (solfège
string → dominant item → sargam lexeme senses in English), and the
new Z6932 *only* for the English-lemma-string → solfège-lexeme step
at the front. That's exactly what `docs/future-helpers.md` sketched:

1. Z6932(lemma=input, language=Z1002, category=Q1084) → solfège
   candidate lexemes (usually 1–2 — `sol`, `sol-fa`, etc.).
2. Walk senses to find the one whose P5137 points to a scale-degree
   item (Q7365017 etc., subclass of scale degree Q1069074). Existing
   sense-list primitives cover this.
3. From the scale-degree item, walk P460 with qualifier
   `P3831=Q7380503` to land on the svara item — pure composition over
   existing qualifier helpers (Z33573 pattern).
4. From svara item, Z6830 reverse-lookup lexemes+senses with P5137 in
   English → sargam lemma.

With Z6932 in place this is all composition; Z29517 goes away, and
adding a new solfège variant (e.g. Italian `do`/`re`) becomes a
Wikidata-side edit rather than a Wikifunctions code edit.

## Ticket shape for filing on Phabricator

Tag: `Wikifunctions`, `Wikifunctions-Catalogue`, `function-orchestrator`.

Title: "New built-in: find lexemes by lemma (lemma, language, category)"

Body outline:

- **Motivation.** Current Wikifunctions compositions cannot go from a
  string to a Wikidata lexeme. Functions like Z26184 (solfege to
  sargam) fall back to hardcoded Python dicts, which duplicate data
  already in Wikidata lexemes and require code edits to accept new
  variants. A built-in that exposes CirrusSearch's `haslemma:` /
  `haslang:` keywords (already live via T271776) fills the gap.
- **Signature.** `(lemma: Z6, language: Z60, category: Z6091) →
  List<Z6093>`.
- **Implementation.** ~30 lines in `function-orchestrator/src/builtins.js`
  plus a `findLexemesByLemma` method on `Resolver` in
  `fetchObject.js`, parallel to the existing Z6930
  (`findLexemesForEntity`) code path. Plus on-wiki Z8 + Z14K4.
- **Out of scope.** Prefix / fuzzy / partial matching (exact lemma
  only for v1, matching T271776's semantics). Form-level lemmas
  (only head lemma, not form representations).
- **Related tickets.** T370072 (lexeme built-ins umbrella), T271776
  (`haslemma:` / `haslang:`), T230833 (wbsearchentities lang bug —
  the reason we don't use that endpoint).

## What to do on the repo side

Nothing needs to land here until the platform function ships. When it
does:

- Add the new ZID to `docs/existing-building-blocks.md` under
  Wikidata-access primitives.
- Refresh `docs/future-helpers.md` to remove the "blocked" note on
  the lexemes-by-lemma entry and replace with a link to the shipped
  ZID.
- Compose the new Z29517 replacement implementation, publish via
  `scripts/wf.rb`, and connect it to Z26184. Once connected, the
  existing Z33697 ("sol → pa") tester should pass without the
  `'sol': 'L328094-S2'` dict entry.

## Status: submitted upstream

On 2026-04-18 this design was filed and the implementation submitted
as a paired set of MRs. See `2026-04-18-submission.md` for the
submission record, MR + Phab links, and resumption steps. Short
pointers:

- **Phabricator T423781** — design proposal and ZID allocation
  request.
- **function-schemata MR !339** — adds Z6832/Z6932 definition files.
- **function-orchestrator Draft MR !643** — handler, tests, submodule
  bump. Draft until !339 merges (CI needs the schemata SHA reachable
  from upstream).

One subtle implementation detail worth keeping anchored here for
anyone reading the design before the contribution doc — the
`realizeStringMemberOrThrow` helper in `src/transpilation/builtins.js`
assumes the two-level nesting of Z6091/Z6092-style wrappers and
throws Z516 on a bare Z6 argument. For a Z6-typed input, use
`getNestedValueOrThrow(Z6, ['Z6K1'], 'Z6', '<funcK>')` instead. Worth
calling out for anyone who adds the next bare-Z6 builtin.

Durable contribution-process lessons learned during the submission are
in `docs/wikimedia-contribution.md`.
