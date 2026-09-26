# 2026-09-26 — Unions representing workers of an organization (Z43460)

Fresh-checkout setup (catalog cache, `.env`) plus a new Wikidata-driven
function: given an organization, return the unions that represent its
workers.

## Result

| Object | ZID |
|---|---|
| **unions representing workers of organization** (Z6091 → List of Z6091) | **Z43460** |
| composition `Z873(Z19308, Z29688(Z872(Z43444, Z29691(Z6821(org), P9239))))` | Z43461 |
| testers: Boston Public Library → AFSCME + AFT; WMF → Wiki Workers United; Google → []; Q5849835 (ended CNT) → [] | Z43462–Z43465 |
| **Wikidata statement has no end time?** (Z6003 → Z40) | **Z43444** |
| composition `Z813(Z28312(statement, P582))` | Z43445 |
| testers: BPL P9239 statement → true; Q5849835 P9239 → false | Z43458, Z43459 |

All connected, all testers pass. Z43462 (Boston) carries a **Z592
advisory warning** ("result exceeded the advisory size threshold in
executor", 12,509 > 10,240 bytes): the full statements (with qualifiers
and references) passed between code-implemented steps are large. It's
harmless. If it matters, fetching with Z30120 limited to P9239 (as Z42503
does) instead of the full-item Z6821 might help, though the statements
themselves stay the same size.

## Wikidata modeling

- **P9239 "affiliated worker organisation"** is the property: on the
  employer, value = union. Maintained by WikiProject Organized Labour.
  Inverse label item Q124253945. Found by counting which properties on
  non-human items point *at* `P31 Q178790` (labor union) items; it
  doesn't show up in label searches for "union".
- P1268 "represents" / P1875 "represented by" look relevant but are
  basically unused for this.
- Union items themselves usually *don't* link back to the employer
  (e.g. Kickstarter United Q112618823 has nothing), so a union → employer
  reverse function would need data work first.
- Coverage is a few hundred employers: lots of US public libraries
  (AFSCME), museums, Amazon, Apple, Microsoft, IBM, Tesla, Kickstarter,
  WMF (Wiki Workers United, Q138920568).
- Qualifiers in use: P580 start time, P1932 object named as (local
  names), P3005, P1310/P5102. **Only one** P9239 statement on Wikidata
  has P582 end time, and it's on a *person* (Q5849835). That's the only
  available test of the end-time filter.
- Misuse: some Spanish historical people carry P9239 → their union;
  McDonald's / Samsung point at topic items ("McDonald's and unions").
  The property's own example, USPS, has no P9239.

## Design notes

- First prototype was just `Z42503(org, P9239, best only = true)`. It
  works, but Z42503 returns values, so qualifiers are gone. The user
  wanted former unions excluded, so the design moved to statements.
- The end-time filter runs **before** best-rank selection (Z29688).
  Otherwise a preferred-rank former union would push out current
  normal-rank ones.
- Prototyped the helper as a `{"lambda": ...}` node in composition_run,
  as CLAUDE.md suggests. Worked first time.
- The typed `List of Z6091` output declaration is accepted by the runtime
  even though Z873 returns an untyped list.

## What went well

- One SPARQL query counting predicates into Q178790 items found P9239
  immediately.
- composition_run with lambda nodes, and `wikilambda_perform_test` for
  checking before connecting.
- `wf_emit_function_shell.py` handles a typed-list output_type object.

## What was missing / wrong

- **`python` isn't on PATH on this machine, only `python3`.** Every command
  in CLAUDE.md says `python`.
- **No `.env` means an anonymous User-Agent, and Wikidata (API and WDQS)
  returned 429s quickly.** Adding `CONTACT_EMAIL` fixed it. WDQS was also
  under an outage rule (1 req/min). CLAUDE.md should say to set
  `CONTACT_EMAIL` first on a fresh checkout.
- **Cache build and live tools share the Wikifunctions rate limit.** While
  `wikifunctions_cache.py --full` ran (~1h+ for 34k pages),
  composition_run and fetch hit 429s. The cache only appears on disk when
  the build finishes, so `cache_query.py` is unusable until then. Idea:
  write the index incrementally, or say in CLAUDE.md to expect this.
- `wikifunctions_cache.py` died on a transient `Errno 101` during page
  enumeration with no retry at that stage; a rerun worked. The network
  here also had DNS blips.
- **`selenium-webdriver` gem wasn't installed.** `wf.rb` needs it; no
  Gemfile documents it.
- **`wf.rb` login wait hides a dead browser:** `check_username` rescues
  every error as "not logged in", so a closed Chrome window burns the full
  10-minute timeout. It should re-raise on
  `Selenium::WebDriver::Error::InvalidSessionIdError`.
- The login didn't persist in `.browser-profile/` across runs until the
  user ticked "Keep me logged in".
- **Tester results are cached per revision, not per dependency.** After
  connecting the helper Z43444, `wikilambda_perform_test` for Z43460 kept
  replaying the old Z503 ("Z43444 has no connected implementation") for
  several minutes. Connecting Z43460 (new revision) cleared it. Running
  the composition directly via composition_run showed the real behaviour.
  Worth a line in CLAUDE.md's step 8.
- Process: a Bash call that the user rejected had already created Z43445
  via the API before the rejection landed. After any rejected
  outward-facing command, check usercontribs.
