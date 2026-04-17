# Strategies that worked (and ones that didn't)

Date: 2026-04-17

Notes distilled from two long sessions of building Wikifunctions via
browser automation + API prototyping. Bias is toward concrete patterns
that future-me (or a future agent) should reach for first — and ones
that ate the most time.

## API prototyping is the high-leverage first step

Running a composition via the `wikilambda_function_call` API with
`composition_run.py` is essentially free and almost always faster than
any UI work. Every function designed this session ran correctly via API
before its composition was created on-wiki. The only surprises at
on-wiki time were UI quirks, never logic bugs. Workflow:

1. Write the `.comp.json` spec (`"function_zid": "TBD"`).
2. Feed it to `composition_run.py` with realistic inputs.
3. When it returns the expected output for several cases, only *then*
   create the shell on-wiki.

Don't skip step 2 to "save time" — the failure mode is running the UI
build, hitting a logic bug three levels deep, then having to delete or
edit an implementation, which is slower than any prototyping round.

## Verify Wikidata items before using them in tests

Spent a while wondering why `Q17087764` gave 256 Hz for MIDI 60 when I
expected 440. `Q17087764` is "scientific pitch" (C4 = 256), not A440.
The actual A440 item is `Q2610210`.

Always `wikidata_explore.py --item <QID>` (or the SPARQL search used
here) before using an unfamiliar Q-number in a test fixture. Don't
trust the ZID shape alone.

## Use the local ZObject cache for reverse deps / signature searches

The `wikilambdasearch_labels` API only hits English labels of the
function's name, so "find every impl that uses Z866" or "find all
Z40-returning functions with Z6 inputs" requires either a slow per-zid
loop or guessing. The local cache at `cache/` + `cache_query.py` makes
those queries trivial (`references Z866 --type Z14` finds all impls
citing it).

Worth the ~100 MB. Rebuild occasionally (`--incremental`).

## Wikifunctions UI quirks that ate time

### Codex menus ignore synthetic events

`dispatchEvent(new MouseEvent('click'))` from JS opens+closes menus
without committing a selection. Vue's `select-item` pipeline requires
real DOM-level events. **Use Selenium native `.click()` or
`ActionChains(move + click).perform`** — never JS `dispatchEvent` for
Codex menu items or select handles. JS `.click()` is only for plain
anchors / buttons whose handler reads synthetic events.

### Menus don't always show ZIDs

Menu items sometimes render as `"label (Z#####)"`, other times as
`"label"` alone — inconsistent across runs and slot types. A match
function needs **both** strategies in order:

1. Text contains the exact ZID string.
2. First line of text equals the known label (from API metadata).

Substring match on label alone is dangerous (`"English"` is a substring
of `"Australian English (English)"`). Either ZID or exact first-line
label match.

### Scrolled-out menu items fail `.displayed?`

Selenium's `displayed?` returns false for items scrolled out of a
`overflow: auto` dropdown container, even though they're in the DOM
and text-searchable. When picking a menu item, filter by text match
only, then let `scroll_to` + native click bring it into view. Filtering
by displayed first will often miss the right answer.

### Pre-populated slots in Z7K1

When switching an argument slot to function-call mode, the UI often
auto-picks a type-compatible default (e.g. a Z6005-returning function
for a lexeme slot). A plain `input.clear` does *not* reset the
component's internal model state — subsequent `send_keys` gets appended
to the default. Clear reliably with: click to focus → JS
`el.value = ''` + dispatch `input`/`change` → select-all + backspace.
That combination has worked for every pre-populated lookup we've hit.

### Collapsed-by-default slots

After switching to any mode (Z7, Z18) or after an argument appears,
the slot starts **collapsed**. Mode selectors and other affordances
are visible, but the actual `Z7K1` / `Z18K1` child isn't rendered until
you click the expand toggle. `expand_at` has to be called before any
interaction in that slot. It's cheap and idempotent (checks the icon
class) so apply it universally at the top of any fill.

### Scope narrowly when searching for inputs

The outer slot's DOM contains leftover hidden inputs from modes you've
already navigated away from. A broad `input.cdx-text-input__input`
search picks up a hidden Wikidata-lookup input from the old literal
mode instead of the `Select argument` dropdown in the new Z18 mode.
**Scope by sub-slot id** (`{keypath}-Z18K1`, `{keypath}-Z6092K1`, etc.)
before looking for inputs.

## Disconnected-by-default is load-bearing

New implementations AND new testers land in Wikifunctions as
**disconnected** — not in the function's `Z8K4` / `Z8K3` list. The
runtime returns `Z503 "no implementation"` until the user toggles them
connected on the function page. The browser scripts now wait for that
connection (up to 24h) after publish; without that wait the user
misses the step and the function silently fails at test time.

If you add a new ZObject type that can be connected to a function,
plumb it through `wait_for_function_field`.

## Types with structured editors (Z16683, Z20838)

A couple of Wikifunctions types look like "scalars" but have expanded
editors with multiple sub-fields:

- **Z16683 (Integer)** — sign dropdown (Z16659) + absolute-value text
  (Z13518). Decomposition is cheap: parse as int, pick
  positive/negative/neutral, type `abs(n)` digits.
- **Z20838 (Float64)** — sign + biased exponent + 52-bit mantissa +
  special-value. IEEE-754-ish. **Do not fill by hand.** Use `Z20915`
  "string to float64 (Python conventions)" as a wrapper function
  inside your spec: `{"call": "Z20915", "args": {"Z20915K1": {...Z6
  string...}}}`. The test runner evaluates the wrapper at test time
  and the slot becomes the parsed float. Much easier than filling the
  IEEE parts.

If you hit a third type with a similar editor, see if there's an
equivalent string-parsing function before implementing a decomposer.

## Screenshots at 4s, 10s cap — don't back off these

The two biggest single-diff wins for productivity this session were:

- Cap every UI step at 10s with auto-screenshot at 4s
  (`slow_wait(tag:) { ... }`).
- Fail-closed: raise instead of falling back to a guess that silently
  picks the wrong thing.

Before these changes we spent long stretches watching a browser freeze
and guessing why. After, every failure mode produces a dated screenshot
that usually shows the cause in one glance. Keep this — do not raise
the timeout "for flakiness". If a step legitimately takes >10s, the UI
has a deeper problem and hiding it won't help.

## When a function "already exists, mostly"

Several times the work was to build a function we already had 80% of:

- `Z33668 "word for concept"` was basically `Z33071` + `Z21806` glued
  together.
- `Z33682 "frequency of MIDI note"` shares its entire outer composition
  with `Z33605 "frequency of pitch in 12-TET"`.

Default to searching `cache_query.py functions --output <type>` or
`--input <type1>,<type2>` before deciding to compose. The cache makes
this almost free, and existing functions come with free testers and
connected implementations.

## Things that did NOT work / avoid

- **Leaving the browser open after error** (original `wf.rb` did a
  `sleep`). Fixed — quits on error with a final screenshot. Anything
  that blocks forever on failure is worse than losing state.
- **`arrow_down + Enter` fallbacks** for menu selection. They
  frequently pick a wrong function while appearing to succeed, which
  cascades into confusing downstream "argument fields didn't appear"
  timeouts. We replaced these with hard aborts. Do not bring them back.
- **Substring label match without anchoring** (hit on the English/
  Australian-English incident). Always anchor to first-line-equals or
  ZID-in-text.
- **Trying to `switch_mode` to `Z9 (Reference)` for a typed slot like
  Z60** when the slot's default literal editor IS a reference picker.
  The mode selector often doesn't even list Z9 for those slots; just
  type into the existing picker and match the menu item.
