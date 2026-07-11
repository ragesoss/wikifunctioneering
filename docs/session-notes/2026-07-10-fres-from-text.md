# 2026-07-10 — Flesch Reading-Ease of text (Z37609) + library comparison

Built the full "FRES from a raw string" function on top of the earlier
count-based Flesch core (Z37551) and the new sentence segmenter (Z18522).

## What shipped

- **Z37609** — "Flesch Reading-Ease of text" (text: Z6 → Z20838), shell
  created via `wf.rb --mode=ui` (function shells still need the browser).
- **Z37610** — its composition implementation (created via API, connected
  by the user). Single function, everything inline. Specs:
  `zobjects/flesch_from_string.func.json` / `.comp.json`.

Composition (no new helper functions needed):
```
Z37551(                                   # 206.835 - 1.015*W/S - 84.6*Y/W
  words     = Z17101(Z12681(Z13402(text))),        # nat->int(len(words))
  sentences = Z17101(Z12681(Z18522(text))),        # nat->int(len(sentences))
  syllables = Z17101(Z20089(Z13521,                # nat->int(sum(...))
                Z13436(Z13036, Z29940, Z13402(text)), 0)))
```

**The map trick (no `map` primitive exists on-wiki):** `Z13436` ("apply a
2-param function to a common first arg + a list") + `Z13036` ("apply",
`f(x)`) gives a map — `Z13436(Z13036, Z29940, words)` = `[Z29940(w) ...]`.
Then sum with `Z20089` (reduce) + `Z13521` (add naturals). Note: `Z13436`
returns `List(Z1)` (generic), so `Z14038` "sum list of naturals" REJECTS it
(wants `List(Z13518)`); reduce+add works because it just folds the elements.

Also note fold/reduce here use the **first list element as the initial
accumulator** (no seed) — fine for a homogeneous number list, but it means
you can't reduce a heterogeneous `(Nat, Str)` combiner over the raw words;
you must map to numbers first.

Validated via `composition_run.py`: "The cat sat. The dog ran fast!" →
118.6825; "Wikipedia is a free online encyclopedia. Anyone can edit it." →
-1.28 (both match the formula on the pipeline's own counts).

## Comparison vs. `textstat` (pip install textstat)

`textstat.flesch_reading_ease` uses the same formula with its own
word/sentence/**syllable** counts (pyphen). Findings across 5 texts:

- **Word counts and sentence counts matched textstat exactly** in every
  case — strong validation of `Z13402` + `Z18522`.
- **All score divergence is syllable counting**, and neither is ground
  truth. Per-word: textstat/pyphen **undercounts** proper/technical terms
  (it scored **"Wikipedia" = 1 syllable**, "organelle" 2, "eukaryotic" 4,
  "triphosphate" 2), while Z29940 **over-counts** a few ("anyone" → 4).
- Net: on Wikipedia-domain vocabulary Z29940 is often the *more* accurate
  of the two; the two libraries fail in opposite directions.

Comparison harness lives only in scratch this session; re-derivable with
`textstat` + the deployed Z37609.

## Z29940 over-count pinned as a test

Created **Z37611** — tester `Z29940("anyone") == 3` (validator `Z13522`,
natural-number equality; mirrors Z29940's existing testers). Z29940 returns
4, so it's a **red** regression test documenting the over-count (green once
the syllable heuristic is fixed). Z29940 is a community function, so this is
a collaborative bug-flag; connecting it is up to us/them.

## Follow-ups

- Function-shell creation via API is still untooled (self-referential arg
  keys) — Z37609's shell went through the browser. Closing this would make
  the whole build headless.
- A more accurate syllable counter (cmudict-backed, or fixing Z29940's
  over-counts) would tighten FRES agreement with references.
