# 2026-07-10 — Sentence segmentation (Z18522): 52 Golden Rules + pragmatic v1

Implemented **Z18522 "segment sentences"** (which had been an
implementation-less shell returning `Z24`) and built a 52-case,
wiki-themed benchmark ported from the pragmatic_segmenter Golden Rules.

## What shipped (all on-wiki, connected to Z18522)

- **Z37556** — pragmatic-v1 implementation, **Python code** (Z14/Z16,
  language `Z610`). Regex "protect non-boundary periods, then split"
  approach. Source mirrored in `zobjects/z18522_segment_sentences.impl.py`.
- **Z37557–Z37608** — 52 Z20 testers, one per Golden Rule. The tester for
  rule *n* is **Z(37556 + n)**. Validator = `Z889` list-equality with
  `Z866` string-equality as the element comparator; expected `List(Z6)`
  supplied as a literal.
- **Score: 38/52** (verified by executing the live function via the API,
  identical to local). Beats spaCy (52%) / NLTK (56%) on the original
  set; matches stanza (73%).

Red (the 14 v1 gaps, left connected as a progress tracker):
`16` (U.S. Government collocation), `18` (Holy Grail a.m./P.M.),
`31–39` (lists — 9 cases), `41`/`42` (newline conventions), `51`
(four-dot ellipsis continuation).

## Repo artifacts

- `zobjects/sentence_segmentation_golden_rules.json` — source of truth
  (52 rules; wiki/vandalism-themed: Willy on Wheels, ClueBot NG, AIV,
  blanking, page-move vandalism). `on_wiki` block records the ZID map.
- `scripts/gen_segmentation_testers.rb` — data file → 52 tester ZObjects
  (`--list` / `--rule N` / `--validate`).
- `scripts/score_segmentation.py` — re-score the deployed function against
  all 52 (run after any v2 impl edit).
- `scripts/wf_zobject_emitter.rb` — extended with a `{"list": [...],
  "type": "Z6"}` node for literal typed lists.
- `zobjects/sentence_seg_test_gr01.tester.json` — the reviewed GR1
  exemplar (the pattern the generator follows).

## Techniques worth reusing

- **Validate code implementations on-wiki BEFORE publishing** by executing
  them *inline* via the function-call API: build a `Z7` whose `Z7K1` is the
  function's `Z8` with `Z8K4 = ["Z14", <inline Z14 code impl>]`, and send it
  with the OAuth bearer token (needs `wikilambda-execute-unsaved-code`,
  which the token has). This ran all 52 against the real Python evaluator
  and matched local exactly — no guesswork about evaluator differences.
- **Code impl shape**: `def Z<id>(Z<id>K1): ...`; a returned Python `list`
  of `str` maps to `List(Z6)`; `import` inside the function is fine;
  language ZID `Z610` = Python, `Z600` = JavaScript.
- **Batch publish** via one authenticated `WikifunctionsSession`
  (`scripts/publish_testers.py` pattern) — 52 creates on one csrf token.

## Connecting is still manual (and this time it was 52 toggles)

Consistent with the OAuth findings: the token **cannot** connect
impls/testers (editing a function's `Z8K3`/`Z8K4` is denied — even for
Z18522, which we didn't create, and even before it had any connected
impl). The user connected the impl + all 52 testers by hand. If we do
another large tester batch, warn about the toggle count up front.

## v2 shipped — list-mode (38 → 47/52)

Same session: added a **list mode** to Z37556 and redeployed. If the text
begins with a list marker (`•`/`⁃` bullet, `1.`/`1)`/`1.)`, or `a.`), it's
treated as a list — split only *before* each marker instead of doing
prose sentence-splitting. Key guard: list mode triggers only when the text
*starts* with a marker, so the 38 prose cases are untouched. A negative
lookbehind `(?<![•⁃])` keeps the space inside a "• 9." marker from
splitting off a stray bullet. Now passes Golden Rules 31–39.

**Deploy gotcha:** editing a *connected* implementation is denied to the
OAuth token (`Z557`: "you don't have permission to edit Implementation
that is connected to a Function"). Workflow that worked: user disconnects
the impl → we edit Z37556's `Z16K2` via API → user reconnects. (Creating a
second impl and swapping also works but leaves a stray object.)

Remaining red (5): 16 (U.S. Government), 18 (Holy Grail), 41/42 (newline
conventions), 51 (four-dot ellipsis continuation).

## v3+ opportunities (biggest win first)

1. **Lists (GR31–39, +9)** — the single biggest gain. Needs a list-mode:
   detect leading markers (`1.`/`1)`/`1.)`/`a.`/`•`/`⁃`) and split *before*
   each marker instead of after the marker's period. Would take v1 from
   38 → ~47/52.
2. **Newline normalization (GR41/42, +2)** — decide Z18522's contract for
   `\n`: collapse errant mid-sentence newlines (GR41), split bare
   newline-separated items (GR42). Currently newlines pass through.
3. **Holy Grail (GR18) / U.S. Government (GR16)** — need context/word
   lists; low priority (even pySBD calls #18 the "Holy Grail").
4. **Four-dot ellipsis continuation (GR51)** — niche.
