# Session: Z44736 "public domain in US by publication date"

Date: 2026-10-09

**Outcome:** Z44736 created and connected (composition Z44737, testers
Z44738–Z44743, all passing except Z44743 Happy Birthday until the
Wikifunctions item cache expires). Along the way: Wikidata cleanup on
Q167545 "Happy Birthday to You", a new item Q141681571 for the 1935
Summy piano arrangement, and `wd_apply.py` gained time values,
`create_item` qualifiers/references, and placeholder qualifiers.

Context: the session started from a dobro recording of "Red Wing"
(Q7305233) uploaded to Commons, then brainstormed song/recording
functions. Public domain status won: simple core, real use (Commons
needs it for every recording of a composition), and it surfaces gaps
in Wikidata (Red Wing had no P577 at all; 447 songs with dead creators
lack P577).

## Design

```
Z10174 and
├── Z17173 (Z20219(Z28777(work, P577), reference year) >= 96)
└── Z17140 (Z20257(Z28777(work, P577)) < 1978)
```

- **96** = 95-year term + 1, because terms run to the end of the
  calendar year (1930 works entered US PD on 2026-01-01).
- **The 1978 guard was found in review, not in the first prototype.**
  "Published 96+ years ago ⇒ PD" only holds for pre-1978 publication;
  later works are usually life + 70. Since the reference year is an
  input, the unguarded version would have said "Another One Bites the
  Dust" (1980) is PD in 2080. Lesson: when a function takes a year
  input, test far-future years, not just the current one.
- Reference year is an input (deterministic, stable testers). A
  "current year" exists via Z23833 → Z24948 but is clock- and
  cache-dependent; keep it to thin wrappers.
- Named narrowly: false = "this rule doesn't establish PD".

User decisions: best-ranked P577 via Z28777 for v1 (not earliest);
errors on missing P577 / coarse precision are acceptable; note the
pre-1978 record-release caveat in the description rather than handle it.

## Wikidata findings and edits

- **Happy Birthday had two normal-rank P577s (1911 sourced, 1935
  unsourced); Z28777 picked 1935.** The 1935 date is the Summy
  copyright on Orem's piano arrangement (Marya v. Warner/Chappell: that
  copyright covered only the arrangement). User deprecated it with
  P2241 = Q106980928 "refers to narrower subject". We created
  Q141681571 for the arrangement and added P8327 "intended subject of
  deprecated statement" → Q141681571 on both the deprecated P577 and the
  deprecated P6216 = copyrighted. Proposal:
  `proposals/happy-birthday-1935-arrangement.json` (gitignored).
- 156 songs have 2+ non-deprecated P577s with different years: a
  cleanup list for this function.
- Georgia on My Mind (Q1420007): P577 says 1931, its own description
  says 1930 — one year either side of the 2026 PD boundary. Left out of
  the testers until resolved.
- Coverage on P31 = song (16,211 items): P577 11,007; P86 2,806; P676
  3,244; P6216 277; P3893 3. The most common PD determination method on
  songs is Q47246828 "published more than 95 years ago" (65), i.e.
  exactly this function's rule — a ready validation target.

## What went well

- `composition_run.py` prototyping caught the Happy Birthday data
  problem and the far-future guard before anything was created.
- The OAuth create path (`wf_emit_function_shell.py`,
  `wf_emit_zobject.rb`, `wikifunctions_edit.py`) created the function,
  composition, and six testers headlessly.
- `wikilambda_perform_test` on the disconnected implementation: all
  testers passed before the user toggled the connections.
- `wd_apply.py` dry-run diff + statement pre-check; the pre-check later
  doubled as a regression test (it refused re-adding posted qualifiers).

## What was missing / wrong

- **The local clone was 3 commits behind origin.** I extended
  `wd_apply.py` on a stale copy, duplicating the 2026-09-26 work
  (string values, qualifiers/references on add_claim, `--maxlag`,
  patient retries) with a different value syntax, and had to port the
  remainder onto origin. **`git fetch` before touching shared tooling.**
- **Stale Wikifunctions item cache again.** Q167545 was fetched ~18:00,
  deprecated at 18:37; Z44736 kept returning false for it. Same issue as
  the CLAUDE.md warning; tester Z44743 will fail until it expires.
- **`wf_emit_function_shell.py` caught a 601-char description** (limit
  500) before posting — good. CLAUDE.md mentions the ~50-char label
  limit but not the 500-char description limit.
- **The emitter has no Z20159 (Gregorian year) literal.** Workaround:
  wrap a Z6 with Z20198 "String as Gregorian Year" in tester specs, the
  same convention as Z20915 for floats.
- **`wikilambda_perform_test` reported every tester FAIL with
  `"pending"` metadata** ~75 s after creation; all passed ~3 min later.
  Check the metadata for `pending` before treating a FAIL as real.
- **maxlag on writes includes query-service lag**, which the
  `siteinfo&siprop=dbrepllag` read doesn't show (0.2 s DB lag vs
  8–15 s write maxlag). The old 4-retry local copy gave up repeatedly;
  origin's 16-retry/`--maxlag` version would have coped.
- Process: a background "wait for lag, then apply" job was stopped
  mid-apply; usercontribs confirmed nothing had posted before retrying.
  After interrupting any outward-facing command, check usercontribs.
- WDQS timed out (504) on a P2241 usage aggregate; listing the
  instances of Q27949697 (reason for deprecated rank) worked instead.

## Concrete suggestions

- CLAUDE.md step 8: note the 500-char description limit, and that
  `perform_test` can return `pending` FAILs for a few minutes.
- `wf_zobject_emitter.rb`: support `{"literal": "2026", "type":
  "Z20159"}` directly (era Z17814 + natural number), so testers don't
  need the Z20198 call.
- `wd_apply.py`: a `set_rank` op (deprecate with P2241 / P8327 in one
  edit) — that was the one manual Wikidata step this session.
- A small "multiple best-ranked values" checker would turn the 156-song
  P577 list into a reusable Wikidata cleanup tool.
