# Browser automation strategies

Durable rules for driving the Wikifunctions UI via `scripts/wf.rb` and
its Selenium-based helpers in `scripts/wf_browser.rb`. This is
debugging-oriented — you don't need it for a happy-path run, but reach
for it whenever a UI step is slow, fails, or silently produces the
wrong result.

See also: `docs/session-notes/` for dated incident logs that motivated
each rule below.

## Rules that produce the biggest wins

### Cap every UI step at 10s with a 4s screenshot

`WfBrowser#slow_wait(tag:) { ... }` is the standard for any UI wait.
Screenshots at `/tmp/wf-stuck-<tag>-<time>.png` land at 4s, and the
wait raises at 10s. Do NOT bump the timeout higher to "deal with
flakiness" — a step that legitimately takes >10s signals a deeper
problem (wrong selector, unexpected state, lingering hidden element)
that a longer wait masks.

### Fail-closed, never fallback-guess

When a menu-item or arg-ref match can't be found, raise — don't fall
back to `arrow_down + Enter` or similar. The fallback regularly picks
a *wrong* function that looks right at the log level, and the error
surfaces N steps later as an unrelated timeout. The old behavior cost
many hours of wrong-path debugging before this rule.

### Prototype via API before touching the UI

Every composition created this project ran through `composition_run.py`
first. Logic bugs at the API level are cheap; logic bugs at UI-build
time waste an entire browser session. No exceptions.

### Prefer the cache for reverse-deps and signature search

`python scripts/cache_query.py references Z866 --type Z14` beats
anything the label-search API can do. Use it any time you need "what
uses X?" or "what Z8 functions have signature Y?". The label-search
API is only useful for live "did someone add this in the last hour?"
checks.

## Codex / Vue UI quirks

### Synthetic events don't commit selections

`element.dispatchEvent(new MouseEvent('click'))` from JavaScript opens
a Codex menu and then closes it without committing a selection. Vue's
`select-item` pipeline reads real DOM events. Always use:

- **Selenium native `.click()`** for menu items, or
- **`@driver.action.move_to(el).click.perform`** (ActionChains) for
  anything where native click throws `ElementNotInteractableError`.

JS `.click()` is only valid for plain anchors / buttons with trivial
handlers.

### Menu items don't reliably include the ZID

Menu rows sometimes render `"label (Z33071)"` and sometimes just
`"label"`. A match function must try both, in this order:

1. Text contains the exact ZID string.
2. First line of text equals the known label (from API metadata), not
   a substring match.

**Substring label match is dangerous.** `"English"` is a substring of
`"Australian English (English)"` and will pick the wrong language.
Always anchor to first-line-equals or ZID-in-text.

### `displayed?` filters out scrolled-out menu items

Selenium treats items scrolled below the visible portion of a
scrollable dropdown as not displayed — even though they're in the DOM
and `.text` returns correctly. When picking a menu item, filter by
text match only; `scroll_to` + native click scrolls the match into
view before clicking.

### Pre-populated lookups need aggressive clearing

When a slot is switched to function-call mode, Wikifunctions auto-
picks a type-compatible default. A plain `input.clear` does not reset
the Vue model, so later `send_keys` gets appended to the default. Use
`clear_lookup_field` (already the default in `select_in_lookup`):

1. Click any `.cdx-chip__close`-style remove button in the container.
2. Click the input to focus.
3. JS: `el.value = ''` + dispatch `input` + `change`.
4. Ctrl-A + Backspace.

### Slots start collapsed after mode switch or function select

Every freshly-appeared argument slot is collapsed. Mode selectors and
labels are visible, but `Z7K1` / `Z18K1` / value sub-slots aren't in
the DOM until you click the expand toggle. `expand_at` handles this
and is idempotent (checks the `…--collapsed` icon class), so call it
liberally at the start of any `fill_argument`.

### Scope finds to sub-slot IDs, not the outer slot

The outer slot's DOM keeps hidden inputs from modes you've navigated
away from. A broad `input.cdx-text-input__input` search will happily
return a lingering Wikidata lookup from the old literal mode instead
of the `Select argument` dropdown in the new Z18 mode. Always scope
by keypath: `{keypath}-Z18K1`, `{keypath}-Z6092K1`, etc.

## Structured literal types

### Z16683 (Integer): sign + absolute value

The expanded editor exposes:

- `Z16683K1` (Z16659 sign) — a Codex select with `positive` /
  `negative` / `neutral` options.
- `Z16683K2` (Z13518 natural number) — a text input for the digits.

`fill_integer_literal` handles this automatically. Specs pass a
regular string like `"69"` or `"-69"`; the helper parses it,
picks the sign, and types `abs(n)`.

### Z20838 (Float64): don't fill by hand

Z20838 is stored IEEE-754-style (sign + unbiased exponent + 52-bit
mantissa + special-value). The UI exposes all those fields. Filling
them by hand requires actual float-bit decomposition — worth avoiding.

**Workaround for tests:** wrap a Z6 string with `Z20915` (`string to
float64`) inside your spec:

```json
"Z31090K2": {
  "call": "Z20915", "name": "string to float64",
  "args": { "Z20915K1": {"literal": "440.0", "type": "Z6"} }
}
```

The test runner evaluates the wrapper at execution time, so the slot
becomes the parsed float with no IEEE decomposition needed in the UI.
Same trick works for tolerances, target values, and any other Z20838
you need in a validator.

## Disconnected-by-default

New implementations (Z14) and new testers (Z20) land in Wikifunctions
as **disconnected** — not present in the function's `Z8K4` / `Z8K3`
list. The runtime raises `Z503` until the user toggles them connected
on the function page. The toolkit already waits for connection after
publish via `wait_for_impl_connected` / `wait_for_tester_connected`,
up to 24h.

If you add a third kind of connectable ZObject, plumb it through
`wait_for_function_field(function_zid, field, wanted_zid, noun)`.

## Anti-patterns to avoid

- **Raising timeouts past 10s.** Masks real problems; see above.
- **`arrow_down + Enter` fallbacks.** Silently pick wrong items.
- **Substring label match.** Picks sibling functions with shared
  prefixes.
- **Leaving the browser open indefinitely on error.** `wf.rb` quits on
  any exception with a final screenshot; do not reintroduce a
  `sleep`-forever rescue block.
- **Switching a typed-picker slot (e.g. Z60 language) to `Z9`
  Reference mode.** The default literal editor already IS a reference
  picker; just type into it and match the menu entry.
