# Future Helper Functions

Reusable Wikidata helper functions identified during design sessions but not yet created.

## qualifier value of item property claim matching value

Selects a claim by its **main value** rather than by rank, then extracts a qualifier. Needed when an item has multiple claims for the same property (e.g., Obama has five P39/position held claims).

**Signature:**
- `item` — Z6001 (Wikidata Item)
- `property` — Z6092 (e.g., P39)
- `value` — Z6091 (e.g., Q11696 / President of the United States — selects which claim)
- `qualifier` — Z6092 (e.g., P1365 / replaces)
- **Output:** Z1

**Composition tree:**
```
Z28297: value of claim
└── Z28297K1 (claim):
    Z811: head
    └── Z811K1:
        Z28312: qualifiers with predicate
        ├── Z28312K1 (statement):
        │   Z811: head
        │   └── Z811K1:
        │       Z28316: filter with second common element
        │       ├── Z28316K1 (two-argument function): Z33103 (literal ref)
        │       ├── Z28316K2 (list to filter):
        │       │   Z29691: get statements for property from item
        │       │   ├── Z29691K1 (item): ← input: item
        │       │   └── Z29691K2 (property): ← input: property
        │       └── Z28316K3 (second argument common): ← input: value
        └── Z28312K2 (predicate to match): ← input: qualifier
```

**Key building blocks:**
- Z29691 (get statements for property from item) — gets all claims for a property
- Z28316 (filter with bound argument) — filters a list using a two-argument predicate with one arg fixed
- Z33103 (statement value is reference to item?) — the filter predicate: checks if a statement's value matches a given item reference
- Z28312 / Z811 / Z28297 — qualifier extraction chain (same as Z33573)

**Test case:** Obama (Q76), P39 (position held), Q11696 (President), P1365 (replaces) → Q207 (George W. Bush)

**Relationship to Z33573:** Z33573 selects a claim by highest rank — sufficient when there's only one claim for the property (or one with preferred rank). This function selects by value match — needed when multiple claims exist for the same property.

## lexemes by lemma (language, category)

> **Update 2026-09-11 — no longer blocking Z26184.** Z6830 "Find lexemes
> for a Wikidata item" is a general *sense-statement* search
> (`haswbstatement:P=Q` over lexemes, sense statements included), so a
> string→sense lookup can be composed today when the target senses share
> a sense-level statement such as P9488 "field of usage": search by that
> statement, filter the returned references by lemma, pick the sense. See
> `docs/session-notes/2026-09-11-solfege-sargam-via-sense-search.md`; the
> resulting helper is **Z41804 "lexeme sense for word in field of usage"**
> (with Z41793 / Z41797 / Z41801 underneath). A true
> lemma search (below) is still worth having upstream for words with no
> shared statement; T423781 / MR !339 / MR !643 remain Draft.


Platform-level primitive needed to rewrite string→lexeme lookups (like Z29517) as pure compositions instead of hardcoded Python dicts.

**Signature:**
- `lemma` — Z6 (String)
- `language` — Z60
- `category` — Z6091 (lexical category item, e.g. Q1084 for noun)
- **Output:** list of Z6005 (lexemes)

**Why it's needed:** The catalog has lexeme→lemma helpers (Z22138 "English lemma string", Z21806 "lemma string from lexeme and lang", etc.) but nothing goes the reverse direction. Z6830 does reverse-P5137 (item → lexemes) and Z33415 filters a lexeme list by target lemma, so once you *have* a list of candidate lexemes you can find one by lemma — but there's no way to get the list from a lemma string in the first place. On Wikidata this would be a SPARQL or `wbsearchentities&type=lexeme` query.

**Why it's blocked:** Wikifunctions' Python runtime is RustPython on wasmedge — a WASM sandbox with no outbound network. A handful of Z14s in the catalog reference `requests.get` / `urllib.request` but they're all sandbox experiments, broken examples, or disconnected. So a code implementation that queries Wikidata from inside a function is not a current platform capability. Until native lexeme search lands (or sandbox egress is added), this primitive can't be built as a user-contributed function.

**Once it exists, Z29517 rewrite becomes:**
1. Call this primitive with `(lemma=input, language=English, category=noun)` → candidate lexemes.
2. Apply `Z33415` ("best lexeme from list with label") with the candidates, the scale-degree item, and the input lemma → a single lexeme.
3. Walk its senses to find the one whose `P5137` points to the scale-degree item → return that sense's ID. (Step 3 may want its own small helper, "sense of lexeme matching P5137 target", but that's pure composition over existing sense-list primitives.)

**Benefit:** all solfege variants (sol/so, ti/si, do/ut, etc.) resolve automatically after a Wikidata sense addition on the relevant lexeme — no Wikifunctions code edit required.

## Public domain family (follow-ups to Z44736)

Planned 2026-10-09 alongside Z44736 "public domain in US by publication date".

- **public domain by life + 70** — work: Z6091, reference year: Z20159 →
  Boolean. Collect P86 + P676 statements (Z29691, Z18755), keep creators
  who did *not* die ≥ 71 years before the reference year (new helper:
  person ref + year → Boolean, false when there is no P570), and require
  that list to be empty **and** the creator list non-empty (else a work
  with no creators is vacuously PD). Watch for `somevalue` creators
  (Happy Birthday's lyricist is "unknown value" with P3831 = anonymous).
  Expected: Take Me Out to the Ball Game false until 2030, Happy Birthday
  true (matches its P3893 = 2017-01-01 for pma-70 countries), Yesterday
  false (living creator).
- **earliest publication year** — work → Gregorian year, from the minimum
  over all non-deprecated P577 statements. Z28777 takes the first
  best-ranked value; 156 songs have 2+ non-deprecated P577s with
  different years. Needs a "minimum of list of years" (only
  natural-number max exists: Z29429).
- **current Gregorian year** — `Z24948(Z23833())`; plus "…as of this
  year" wrappers. Not for testers (result is clock- and cache-dependent).
- **layered public-domain check** (work, jurisdiction, year): explicit
  P3893 public domain date for the jurisdiction → explicit P6216
  copyright status (non-deprecated, P1001 jurisdiction, P580 start) →
  computed rule (Z44736 for the US, life + 70 for Q59542795 "countries
  with 70 years pma or shorter"). Needs jurisdiction → group membership.
  A separate checker should flag disagreement between explicit statements
  and the computed rule — e.g. the 65 songs with P6216 = public domain,
  P459 = Q47246828 "published more than 95 years ago".
