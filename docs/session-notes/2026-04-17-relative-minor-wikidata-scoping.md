# Session: relative-minor function — Wikidata scoping

Date: 2026-04-17

Goal of the session: start designing a pure-composition,
Wikidata-driven Wikifunctions function that takes a major key and
returns the relative minor. Session ended at the scoping stage — the
function itself wasn't built, because the underlying Wikidata data
needs filling in first. User has the QuickStatements batch to apply;
the function design resumes once that lands.

## The Wikidata model for "relative minor"

It is already modelled — partially. On `Q1022293` (C major):

```
P460 (said to be the same as) -> Q277855 (A minor)
  qualifier P1013 (criterion used) -> Q1500499 (relative key)
```

Verified by pulling the raw entity JSON — exactly that property +
qualifier + qualifier value, nothing else needed. This is the pattern
to apply everywhere.

## Coverage survey

All items typed as `Q58795659` (major mode) or `Q113031009` (major
key) — 22 items total, including pathological enharmonics (A♯ major,
B♯ major, C♭ major, D♯ major, E♯ major, F♭ major, G♯ major).

- 7 items have a `P460 … P1013=Q1500499` claim.
- 15 don't.

All items typed as `Q12827391` (minor mode) — 19 items total.

- 2 have the reverse claim (minor → major).
- 17 don't.

So: the pattern is consistent but the data is ~1/3 populated.

## Typing inconsistency (flagged, not fixed)

Major-key items use three different `P31` values more-or-less
randomly:

- `Q113031009` (major key) — appears only on C major.
- `Q58795659` (major mode) — appears on most others (F, G, D, …).
- `Q192822` (tonal system) — ubiquitous, appears alongside the above.

So you can't write a single SPARQL `?x wdt:P31 wd:Q113031009`
expecting to enumerate all majors. Normalising the typing would be a
separate Wikidata cleanup. Out of scope for this session; noted for
future design considerations.

## The D♯ major → C minor slippage

Before this session: `Q9207730` (D♯ major) → `Q309994` (C minor)
with `P1013 = Q1500499`. Strict music theory says D♯ major's
relative is **B♯ minor** (6th scale degree of D♯ is B♯). The claim
as-found conflates D♯ major with its enharmonic equivalent E♭ major
— whose relative *is* C minor.

`B♯ minor` exists as `Q110297194`. Fix: change the target on the
existing claim to Q110297194.

For the *other* pathological majors (A♯, B♯, C♭, E♯, F♭, G♯), the
strict relative minors would sit on double-sharp / double-flat roots
(F## minor, C## minor, A♭♭ minor, D♭♭ minor, …) — none of which
exist as Wikidata items. So there's nothing to honestly claim. Leave
them unclaimed.

## Constraint check

Before writing, verified via P460's `P2302` (property constraint)
claims that P1013 is an approved qualifier:

- P460 `Q21510851` (allowed-qualifiers constraint) lists P1013,
  P1480, P828, P459, P1310. ✅
- P460 also has a `Q21510862` (symmetric constraint) — meaning when
  A P460 B with qualifier X, ideally B P460 A with qualifier X too.
  Non-blocking, but the constraint gadget will nag about
  half-populated symmetry until reverse (minor → major) claims are
  added. Open choice whether to fill those in.

## QuickStatements quirk

The V2 CSV format rejects qualifier property column headers of shape
`qalNNNN` for P1013 ("invalid qualifier property p1013"), despite
the docs saying that's exactly the syntax. The V1 tab-separated
format works fine: paste into the "V1 commands" textarea at
https://quickstatements.toolforge.org/ . Worth remembering if the
next batch hits the same wall.

## The batch (for the user to run)

One UI edit on Q9207730 (fix the slippage: swap target from Q309994
to Q110297194). Then 7 new V1 commands (+ 1 optional enharmonic
twin for C♯ major). Lines are tab-separated:

```
Q277793	P460	Q283910	P1013	Q1500499
Q719309	P460	Q283741	P1013	Q1500499
Q1132862	P460	Q11160262	P1013	Q1500499
Q1125102	P460	Q283749	P1013	Q1500499
Q934895	P460	Q309994	P1013	Q1500499
Q507255	P460	Q283874	P1013	Q1500499
Q5728362	P460	Q283880	P1013	Q1500499
Q1093180	P460	Q287469	P1013	Q1500499
```

All 18 item ZIDs verified against SPARQL labels; all 9 target
intervals (major sixth from source) verified by hand.

## Resumption plan (whenever this comes off the shelf)

1. Confirm the Wikidata batch was applied (7 or 8 new claims, D♯
   fix merged).
2. Design the composition. Expected shape: input `Z6091` for the
   major-key item ref, walk the P460 claim whose qualifier
   `P1013=Q1500499`, return the value as `Z6091`. Building blocks
   likely needed:
   - `Z28787` "item from item and property (references)" — if we
     want "first P460 value" only (not qualifier-filtered). Risky
     because a key could in principle have multiple P460 claims
     with different qualifiers.
   - The qualifier-filtered variant from `docs/future-helpers.md`
     ("qualifier value of item property claim matching value") —
     modeled for a different use case but the same shape might
     work. Or a simpler qualifier-filtered-claim-extraction helper
     specifically for "value of property claim with qualifier=X".
3. Testers: one per standard major key — 12 to 15 testers.
4. Optional follow-up: fill in reverse (minor → major) claims so
   the symmetric constraint is satisfied, then add a sibling
   function for the reverse direction.

## Also in this session (smaller)

- Confirmed via Wikidata entity JSON fetch that `Q1022293`'s P460
  claim really does carry `P1013=Q1500499` as its only qualifier,
  not something else. The "is this the right qualifier" question
  came up enough times that it's worth having the verification
  recipe in notes:

  ```
  curl -s 'https://www.wikidata.org/wiki/Special:EntityData/Qxxxxx.json' |
    python3 -c "import json,sys;d=json.load(sys.stdin);e=d['entities']['Qxxxxx'];
                [print('P460->', c['mainsnak']['datavalue']['value'].get('id'),
                       'quals=', {p:[q['datavalue']['value']['id'] for q in qs] for p,qs in c.get('qualifiers',{}).items()})
                 for c in e['claims'].get('P460', [])]"
  ```

  Useful for any future "does Wikidata really have this modelled the
  way I think it does" check.

- `wikidata_explore.py --property Pxxx` output is truncated — doesn't
  include `P2302` (property constraint) claims cleanly. Had to drop
  to a curl + Python one-liner to surface constraint data. Minor tool
  gap; not urgent.

## What didn't get built

- The function shell itself (Z8 for "relative minor of major key").
- Its composition.
- Any testers.

All deferred until Wikidata has the claims. Once the batch runs,
resumption is mostly assembly.

## Follow-up: Wikidata editing support in the repo

Motivation surfaced this session: every time a Wikifunctions function
needs a piece of Wikidata data that turns out to be missing
(L328094's solfege sense, relative-minor claims on the major keys),
we bounce out to the Wikidata UI or QuickStatements. That's tolerable
for a one-off, but it's becoming a recurring pattern and it breaks
the "propose change → apply directly" loop we have for Wikifunctions
itself. Worth bringing Wikidata edits into the toolkit the same way
we did for Wikifunctions.

Things to research / decide before building:

1. **Is AI-driven Wikidata editing acceptable?** (Researched this
   session — answer in short: *yes, under our pattern.*) Wikidata's
   bot policy defines a bot as "tools used to make edits without the
   necessity of human decision-making." Our workflow has human
   decision-making per edit, so we're not a bot under that
   definition. The proposed Wikidata:Requests for comment/Mass-editing
   policy (under discussion, not adopted) defines mass editing as
   changes made "without being reviewed individually by the person
   making the edits and which could not reasonably be done manually"
   — again, our pattern explicitly passes individual review and
   stays small enough to do manually. There is currently **no
   Wikidata-specific LLM policy**; the WikiProject Large Language
   Models talk page confirms the project is exploratory, not
   prescriptive. So: no approval required, no disclosure required
   — but we adopt disclosure anyway for consistency with our
   Wikifunctions practice, forward-compatibility with Meta's
   anticipated baseline policy, and because it's cheap insurance.
   Full write-up (with links and quoted passages) now lives in
   `docs/ai-disclosure.md`.

2. **Edit summary convention.** Disclosure format is now documented
   in `docs/ai-disclosure.md` — three-element format matching our
   Wikifunctions practice (that AI was used, which AI, what it
   contributed), adapted to claim/sense/qualifier work. For
   QuickStatements, use `/* AI-assisted, Claude */` in the batch
   summary. For API-driven tooling, build the disclosure string
   into the helper so it can't be forgotten.

3. **OAuth setup.** Unlike the Wikifunctions `wikilambda_edit` API
   (which needed a logged-in browser session because its rights
   weren't in `$wgGrantPermissions`), standard Wikidata editing
   (`wbeditentity`, `wbsetclaim`, `wbcreateclaim`,
   `wbsetqualifier`) uses normal MediaWiki grants, so an OAuth
   owner-only consumer should work without the "drive the browser"
   workaround. Register a consumer at
   [[Special:OAuthConsumerRegistration]] on wikidata.org, owner-only,
   request grants for editing items (the exact grant names we'll
   need to pin down during first build — probably `editpage` plus
   a Wikibase-specific one). Also: respect `maxlag` (abort when
   replication lag > 5s per the standard MediaWiki convention),
   serial not parallel, ~1 edit per 3–5 seconds as QuickStatements'
   default throttle. Store the token like the previous
   `WF_OAUTH_TOKEN` attempt did in `.env`.

4. **Tooling shape.** Options:
   - A Python script similar to the old `wikifunctions_edit.py`, but
     using `wbcreateclaim` / `wbsetqualifier` rather than
     `wikilambda_edit`. One-off batches, straightforward scripts.
   - A Ruby counterpart inside this repo's `scripts/` alongside
     `wf_api.rb`, if we want the same "stage changes, user presses
     Enter to apply" flow.
   - For batch work where the data is already structured, generating
     QuickStatements input from a template might still be the
     pragmatic path — it's just annoying when the data isn't
     pre-formatted or when we hit validator quirks like today's
     CSV-qualifier failure.

5. **Read-side integration is already solid.** `wikidata_explore.py`
   uses the public SPARQL/entity endpoints with no auth — those keep
   working for reconnaissance. Only the write path needs new tooling.

When it comes off the shelf: #1 (policy research) is done this
session and captured in `docs/ai-disclosure.md`. The path is clear
for building — start with #3 (OAuth consumer registration) as the
only real setup step before coding the helper.
