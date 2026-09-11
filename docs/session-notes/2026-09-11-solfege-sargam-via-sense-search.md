# Session: Z26184 "solfege to sargam" — pure composition via sense-statement search

Date: 2026-09-11

**Outcome:** goal reached. Z26184's only connected implementation is now
Z41808, a composition whose every node is a generic function and whose
every fact comes from Wikidata (via Z6830 sense-statement search on
P9488). Four reusable helpers were created on the way (Z41793, Z41797,
Z41801, Z41804) and one Wikidata claim was added (L328094-S2 P9488 →
Q638). The upstream "lexemes by lemma" primitive was not needed.

Goal revisited: make Z26184 a composition built only from generic
building blocks, driven by Wikidata, with **no hard-coded
solfège/sargam table**. The blocker since April was the first step —
going from a solfège *string* to the corresponding Wikidata lexeme —
which Z26184 still delegates (via Z30555 → Z29515) to a Python dict /
Z22193 switch table.

## Blocker status: upstream primitive still not merged

- Phabricator **T423781** — still "Open, Needs Triage".
- function-schemata **MR !339** and function-orchestrator **MR !643**
  — both still *Draft*, last touched 2026-06-02. Z6832 / Z6932 do not
  exist on-wiki. (GitLab's notes API needs auth, so the June activity
  couldn't be read from here.)
- No new lexeme built-ins have appeared: the Z68xx/Z69xx range is
  unchanged (Z6820–Z6826, Z6830, Z6831, Z6839, Z6920–Z6939).

So nothing was *removed*. But a different route turned out to be
open all along.

## The discovery: Z6830 is a sense-statement search

Z6830 "Find lexemes for a Wikidata item" (item, property, language) is
a thin wrapper over Wikidata CirrusSearch:
`inlanguage:<code> haswbstatement:P<pid>=Q<qid>` in the Lexeme
namespace, `srlimit=500` (`fetchObject.js findEntitiesByStatements`).
Wikidata indexes **sense-level statements** for that keyword — which is
why Z6830 works with P5137 at all. Nobody had noticed that this makes
Z6830 usable with *any* sense property, not just the concept link.

The eight English solfège senses already carry a sense-level
**P9488 "field of usage"** statement (seven of them; see below), and
the seven sargam senses carry P9488 too:

| field of usage value | lexemes returned (English) |
|---|---|
| Q638 music | 12: the 7 tagged solfège syllables + house, note, temperature, D, A |
| Q1323698 Indian classical music | exactly the 7 sargam syllables (sa re ga ma pa dha ni) |

Verified both with the Wikidata search API directly and by calling
Z6830 through the Wikifunctions API. So a string → sense lookup is:

1. `Z6830(field, P9488, language)` → candidate lexeme references
2. filter those references by lemma == input word
3. fetch the one lexeme, pick the sense whose P9488 is `field`
4. downstream is the April design: Z21577 (P5137 → scale degree),
   Z28787 with P460 (→ svara), Z33668 (→ English noun lemma).

Nothing in the composition names a syllable. The only constants are
the same kind already present in the April design: a property
(P9488, P460), a language (Z1002), a lexical category (Q1084), and a
domain item (Q638 "music").

### Why Q638 (music) rather than Q159563 (solfège)

P9488 has a one-of constraint listing Q638 — but the constraint is
**deprecated-rank** with reason Q99460987 "constraint provides
suggestions for manual input", so any item is permitted. Q159563
would be more specific, but seven of the eight solfège senses already
use Q638 and all seven sargam senses use a genre item, so matching the
established sibling pattern is the better Wikidata citizenship. The
function's precision comes from its input contract, not the field.

## Validation (all via `wikilambda_function_call`, nothing created)

Pipeline run with anonymous inline predicates (see tooling below):

| input | ref | sense | scale degree | svara | output |
|---|---|---|---|---|---|
| do | L319652 | L319652-S2 | Q210411 tonic | Q19813593 Shadja | sa |
| re | L326409 | L326409-S2 (not the sargam S1) | Q2482078 | Q12416644 | re |
| mi | | | | | ga |
| fa | | | | | ma |
| so | | | | | pa |
| la | | | | | dha |
| ti | | | | | ni |
| sol | — | | | | Z516 (empty list): L328094-S2 had no P9488 — **fixed later this session, now → pa** |
| xyz | — | | | | Z516 (empty list) — clean failure |

Matches every existing Z26184 tester (do→Sa, la→dha, mi→ga, re→re)
except sol→Pa, which needs one Wikidata claim (below).

### Gotchas found while validating

- **Do not carry full lexemes through a list filter.** The obvious
  shape — `Z873(Z6825, refs)` then `Z28316` on the 12 lexeme objects
  (~86 KB) — dies with **Z573 "WASM interpreter aborted (unreachable
  executed)"** every time. Filtering the *references* with a
  predicate that fetches one lexeme per call works (the orchestrator
  caches the fetches). Rule of thumb: keep big Wikidata objects out of
  recursive list helpers; move the fetch inside the predicate.
- **Lemma matcher choice.** `Z866(Z27423(lexeme), word)` (first lemma,
  exact) and `Z10539(...)` (case-insensitive) both pass all seven.
  `Z30972(Z19293(lexeme), word)` (any lemma, exact) hit **Z530 "Error
  in the function call API"** for "re" reproducibly (JS evaluator in
  the trace) while working for other words — not investigated; use the
  first-lemma variant.
- P460 on the seven scale-degree items is clean: exactly one value
  each, with qualifier P3831 = Q7380503 (svara). So Z28787
  "best statement" is safe here. The **reverse** direction is not:
  each svara item has two unqualified P460 values (a note name and a
  scale degree), so a sargam→solfège function would need a
  qualifier-/type-aware claim selector.

## Design to build

Four small generic helpers plus a new Z26184 implementation. Spec
files are in `zobjects/`; they were written with `ZNEW_*` placeholders
and rewritten to the real ZIDs as each shell was created (each later
spec references earlier ZIDs). ZIDs below are the ones that were
assigned.

1. **Z41793 — "first lemma of lexeme reference equals string?"**
   (lexeme reference: Z6095, string: Z6) → Z40.
   `Z866(Z27423(Z6825(ref)), string)`.
   Files: `lexeme_ref_first_lemma_equals.{func,comp}.json`,
   `..._true.tester.json`, `..._false.tester.json`.
2. **Z41797 — "lexeme sense is in field of usage?"**
   (sense: Z6006, field of usage: Z6091) → Z40.
   `Z27340(sense, P9488, field)`.
   Files: `sense_in_field_of_usage.*` (+ true/false testers using
   L319652-S2 and the sargam sense L326409-S1).
3. **Z41801 — "lexeme sense in field of usage"**
   (lexeme: Z6005, field of usage: Z6091) → Z6006.
   `Z811(Z28316(Z41797, Z19282(lexeme), field))`.
   Files: `sense_of_lexeme_in_field.*` (+ tester: L326409 → S2).
4. **Z41804 — "lexeme sense for word in field of usage"**
   (word: Z6, language: Z60, field of usage: Z6091) → Z6006.
   `Z41801(Z6825(Z811(Z28316(Z41793, Z6830(field, P9488, language), word))), field)`.
   Files: `lexeme_sense_for_word_in_field.*` (+ testers: "do"/music
   → L319652-S2; "pa"/Indian classical music → L324925-S2, i.e. the
   sargam sense, not "father").
5. **Z26184 new implementation** — `solfege_to_sargam_v2.comp.json`:

```
Z33668: word for concept
├── Z33668K1 (concept):
│   Z28787: item from item and property (references)
│   ├── Z28787K1 (item):
│   │   Z21577: item reference from sense
│   │   └── Z21577K1 (sense):
│   │       Z41804: lexeme sense for word in field of usage
│   │       ├── K1 (word): ← solfege note
│   │       ├── K2 (language): Z1002 (English)
│   │       └── K3 (field of usage): Q638 (music)
│   └── Z28787K2 (property): P460 (said to be the same as)
├── Z33668K2 (language): Z1002 (English)
└── Z33668K3 (lexical category): Q1084 (noun)
```

   Plus three new testers `solfege_to_sargam_{so,ti,fa}.tester.json`.
   `solfege_to_sargam_prototype.comp.json` is the same tree with the
   helpers inlined as lambdas; it runs today via `composition_run.py`.

### Steps still requiring a human

- **Wikidata — DONE 2026-09-11.** `proposals/sol-music-field-of-usage.json`
  applied: statement `L328094-S2$9F2400A2-420A-4EB2-A05A-E53CAA188FC9`
  (P9488 → Q638), summary "Created with AI assistance (Claude Fable
  5.1)". CirrusSearch indexed the sense statement within ~15 s (the
  `haswbstatement:P9488=Q638 inlanguage:en` count went 12 → 13), and
  the prototype pipeline run through Wikifunctions returned
  `sol → pa` immediately — the Z6830 search result was *not* served
  stale from the orchestrator cache in this case, even though the same
  search had been run ~1 h earlier in the session.
- **Connect toggles — on every function, including brand-new ones.**
  I assumed the token could connect on a fresh function (no connected
  implementation yet). Wrong: updating Z41793's Z8K3/Z8K4 was refused
  with Z557 "You don't have permission to connect a Test Case to its
  Function" and, for Z8K4 alone, "...connect an Implementation to its
  Function so it can be run". Connecting is a separate right the OAuth
  consumer lacks. So every helper needs the user's toggle (impl + testers).
  What *does* work headless is `action=wikilambda_perform_test`, which
  runs disconnected testers against a disconnected implementation —
  use it to prove the objects before asking for the toggle.

### Publishing log

- **Helper A "first lemma of lexeme reference equals string?" → Z41793**
  (shell via `wf_emit_function_shell.py`), composition **Z41794**,
  testers **Z41795** (do → true) and **Z41796** (re → false). All three
  created via the OAuth API in one pass; structure verified from
  `?action=raw`. User toggled impl + testers connected; live calls
  confirmed (L319652/"do" → true, L319652/"re" → false, L328094/"sol"
  → true, L326409/"re" → true).
- **Helper B "lexeme sense is in field of usage?" → Z41797**,
  composition **Z41798**, testers **Z41799** (L319652-S2 in music →
  true) and **Z41800** (L326409-S1 sargam sense in music → false).
  Created via the OAuth API. **Gotcha:** `wikilambda_perform_test` run
  within ~30 s of creating the objects reported *both* testers false
  (including the one expecting false, so the call was erroring, not
  inverting); the same request a minute later passed both. Wait a
  minute or retry before concluding a fresh implementation is broken.
  Calling the function as a literal Z8 with `Z8K4 = ["Z14", "Z41798"]`
  (what the UI does for unconnected impls) returned the right values
  throughout. User toggled impl + testers connected; live calls confirmed
  (L319652-S2/music → true, L326409-S1/music → false, L326409-S2/music
  → true, L328094-S2/music → true).
- **Helper C "lexeme sense in field of usage" → Z41801**, composition
  **Z41802**, tester **Z41803** (L326409 + music → L326409-S2, not the
  sargam S1). Body pre-validated live against the connected Z41797 for
  six lexeme/field pairs (incl. pa+music → empty-list error, correct). perform_test showed the same post-creation transient (false at
  ~1–2 min, pass at ~4 min); the literal-Z8 call returned L326409-S2 and
  Z6806 against the fetched sense returned true throughout. User toggled impl + tester connected; live calls confirmed
  (re+music → S2, re+Indian classical music → S1, pa+Indian classical
  music → S2, sol+music → S2).
- **Helper D "lexeme sense for word in field of usage" → Z41804**,
  composition **Z41805**, testers **Z41806** ("do"/English/music →
  L319652-S2) and **Z41807** ("pa"/English/Indian classical music →
  L324925-S2). Body pre-validated live for seven word/field pairs
  (incl. "xyz" → empty-list error). `solfege_to_sargam_v2.comp.json`
  now references Z41804; no `ZNEW_*` placeholders remain. User toggled impl + testers connected; live calls confirmed
  ("do"/music → L319652-S2, "sol"/music → L328094-S2, "re"/Indian
  classical music → L326409-S1, "ni"/Indian classical music →
  L1551697-S1). `solfege_to_sargam_v2.comp.json` then ran live through
  `composition_run.py` with every node a real connected function:
  do → sa, re → re, sol → pa, ti → ni.
- **Z26184 new implementation → Z41808** ("via Wikidata sense search,
  no syllable table"), plus testers **Z41809** (so → pa), **Z41810**
  (ti → ni), **Z41811** (fa → ma). Created via the OAuth API. perform_test with all eight testers (Z26185 do→Sa, Z30320 la→dha,
  Z30321 mi→ga, Z33697 sol→Pa, Z36261 re→re, Z41809, Z41810, Z41811)
  against Z41808: all fail at first attempt (transient), all PASS 30 s
  later. User connected Z41808 and disconnected Z33678; Z26184 live
  for all eight syllables: do→sa, re→re, mi→ga, fa→ma, so→pa, sol→pa,
  la→dha, ti→ni. **Goal reached: Z26184 is pure composition over
  generic functions, every fact from Wikidata.** All eight testers are
  connected too (`?action=raw` lagged and still showed five; the
  revisions API `action=query&prop=revisions&rvprop=content` returned
  the fresh Z8 — use that when polling connect state).
- Done as part of the above: Z33678 (the old implementation that
  reaches the hard-coded Z29515) is disconnected. Optional follow-up:
  Z29515 and Z30555 could themselves get pure implementations via
  Z41804 (Z23127(Z23112(sense)) gives the LSID string).

## Reverse function (sargam → solfège): scoping and Wikidata edits

Data survey for the reverse direction:

- word → sense: Z41804 with field Q1323698 (Indian classical music)
  finds exactly the 7 sargam lexemes.
- svara → scale degree: each svara item has **two unqualified P460
  values** (a note name such as "D" and the scale degree), so Z28787
  "best statement" is not safe. Filtering by "instance of degree" also
  fails: supertonic and mediant only have P279 → degree, and the note
  "C" (Q843813) is itself wrongly P31 → degree.
- scale degree → word: tonic, mediant and dominant are also linked from
  theory-term lexemes ("tonic", "mediant", "dominant"), and dominant has
  both "so" and "sol". Wikidata's search order was stable across runs
  ("so" first) but is not guaranteed.

Decisions (user): output is a string, first match; two Wikidata edits.

1. **Role qualifiers (applied 2026-09-11):** P3831 "object of statement
   has role" = Q586277 degree on the seven svara → scale-degree P460
   statements, mirroring the existing degree → svara statements
   (P3831 = svara). Proposal `proposals/svara-degree-role-qualifiers.json`
   (7 × new `add_qualifier` op). Q586277 is a subclass of Q4897819 role;
   P3831's none-of lists don't include it.
2. **Name type (proposed):** a new class item "solfège syllable" (P31
   Q134599141 type of name; P279 Q82799 name, Q1969448 term; P361
   Q159563 solfège), then P14792 "name type" → it on the eight solfège
   senses. Chosen over P9488 → Q159563 because P9488's 985 values are
   almost all disciplines and no system (solfège/solmization/sargam) is
   used as one; P14792's values (toponym, scientific name, color term…)
   are exactly "what kind of name this sense is". Proposal
   `proposals/solfege-syllable-name-type.json` — **applied 2026-09-11:
   new item Q141435500 "solfège syllable"**, P14792 → Q141435500 on the
   eight senses.

Prototype (`zobjects/sargam_to_solfege_prototype.comp.json`, two nested
lambdas for the name-type predicates, everything else existing
functions): with the discriminator temporarily swapped to the cached
P9488 = music statements, sa→do, ga→mi, ma→fa, pa→so, dha→la, ni→ti all
pass; "re" fails only because Rishabha was fetched (and thus cached
stale) before its qualifier was added. With the final P14792 =
Q141435500 literals the same run fails on every input because the
eight solfège lexemes were fetched earlier today and the orchestrator's
entity cache predates the new sense statements — Wikidata's own search
already returns all eight for `haswbstatement:P14792=Q141435500`. So:
structure validated today, data validated on Wikidata, the combined
testers can only go green once the cache expires.

The existing Z31659 "get property statements with qualifier from item"
(composition Z31660 → Z29870 + Z35133) works — the April note that the
qualifier filters were broken applied to Z31655, not this one. Z31108
"Western musical scale degree to Svara" already uses it forward.

### Publishing log (reverse side)

All created via the OAuth API on 2026-09-11; connect toggles pending.

| function | ZID | composition | testers |
|---|---|---|---|
| lexeme sense has name type? | Z41819 | Z41821 | Z41822 (so → true), Z41823 (dominant → false) |
| item from item, property, and object role | Z41820 | Z41824 | Z41825 (Panchama/P460/degree → dominant), Z41826 (dominant/P460/svara → Panchama) — both PASS |
| lexeme reference has sense with name type? | Z41827 | Z41828 | Z41829 (L328069 → true), Z41830 (L319695 → false) |
| word for concept with name type | Z41831 | Z41833 | Z41834 (tonic → do), Z41835 (dominant → so/sol) |
| **sargam to solfege** | **Z41832** | Z41842 | Z41836 sa, Z41843 re, Z41837 ga, Z41838 ma, Z41839 pa (so/sol), Z41840 dha, Z41841 ni |

Gotchas met while publishing:

- **Labels are unique per language across all objects, not per
  function.** The composition label "via Wikidata sense search, no
  syllable table" (already used by Z41808) and the tester label
  "re -> re" (Z36261) were both refused with Z554; renamed to "via svara
  role qualifier and solfège name type" and "sargam re -> solfège re".
- **Descriptions are capped at 500 characters** (Z500 "Description in
  English must be 500 characters or shorter"); `wf_emit_function_shell.py`
  now checks this up front.
- For a tester whose expected value is "one of several", use a validator
  whose **first** argument is the result (the runner fills K1): Z11094
  "string is element of CSV" with K2 = "so,sol" works; Z12696 "contains"
  has the list first and would not.
- `perform_test` only substitutes the implementation of the function
  under test; nested calls to *other* new functions go through their
  connected implementations. So F (calls Z41819), H (calls Z41827) and
  Z41832 (calls Z41820, Z41831, Z41804) cannot pass until the helpers
  below them are connected — their pre-toggle results were `"Z42"`
  (canonical bare Boolean, not an error object). Connect bottom-up:
  E → F → H → function.
- The name-type testers (E, F, H, and the function) also read the eight
  solfège lexemes, which the orchestrator cached before the P14792
  statements were added, so they report false until that cache expires
  even once connected. G's testers pass now. Re-run `perform_test` (or
  look at the on-wiki test table) later before judging them.
- **Control test proving the chain (2026-09-11 19:35 UTC, all five
  connected):** Z41831(Q3257809 purple, English, Q376431 color term) →
  "purple" — a name-type sense never fetched before, so no stale cache.
  E → F → H work end to end; the solfège testers fail only because
  L319652…L329319 are cached pre-edit. Z41832("sa") live → empty-list
  error at Z811 inside Z41831, exactly that cache miss. The on-wiki test
  table can also show results computed *before* a nested helper was
  connected (Z41830 showed red, then passed on re-run once Z41819 was
  connected); reload after connecting bottom-up.

## Tooling changes this session

- **`composition_run.py` / `composition_debug.py`: `{"lambda": ...}`
  nodes.** An inline anonymous Z8 so a design that needs a helper
  predicate that doesn't exist yet can be run end to end *before*
  creating anything. Fake identity ZIDs `Z9999xxxx` work; `"Z0"` is
  rejected by the orchestrator. `composition_debug` skips lambda
  bodies (unbound args). The Ruby emitter refuses lambda nodes with a
  pointer to this workflow.
- **`wf_zobject_emitter.rb`:** literal types now include Z6095, Z6096
  and Z40 (same `{Z1K1: T, TK1: v}` shape as Z6091/Z6092), needed for
  the helper testers.
- **`wd_apply.py`:** had a *hardcoded* "Claude Opus 4.7" disclosure
  string, bypassing the `{model}` machinery in `config.py`. Now imports
  `config.AI_DISCLOSURE`.
- **`wd_propose.py`:** crashed when `related_followups` entries were
  plain strings (the README shows them as free text); now accepts both.

## What went well / missing / wrong

- **Went well:** `cache_query.py functions --input/--output` found
  Z27340, Z30972, Z28316, Z19282, Z21577 in minutes; `composition_run
  --raw` + a 30-line `api_call` wrapper was enough to validate every
  stage; reading the orchestrator source in `upstream/` answered the
  "what does Z6830 actually query" question definitively.
- **Missing:** a way to run compositions with not-yet-existing helpers
  (fixed: lambda nodes); a function-shell emitter for the API path
  (fixed: `scripts/wf_emit_function_shell.py` turns a `.func.json` into
  a Z0-placeholder Z2/Z8 that `wikifunctions_edit.py create` accepts;
  output validated with `zobject_validate.py`).
- **Wrong / misleading:** `docs/future-helpers.md` said string→lexeme
  was "blocked until Wikifunctions gains native lexeme search or
  sandbox egress" — it was blocked only for *lemma* search; searching
  by a sense statement was always possible. `wikidata_explore.py
  --item` for Q207435 / Q1069074 returned unrelated items (Taweret, a
  mountain) — my ZIDs were wrong, but the tool gives no hint when a
  label doesn't match the expectation; a `--search` by label first
  would have saved a step (`--sparql` with `rdfs:label` did the job).
- **Suggestions:** add the "filter references, not fetched objects"
  rule to `docs/wikidata-integration.md`; document Z6830-as-general-
  sense-statement-search in `existing-building-blocks.md` (done);
  the API path now covers shells too (`wf_emit_function_shell.py`).
