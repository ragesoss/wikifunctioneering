# Session: word for concept + browser automation fixes

Date: 2026-04-16

## What got built

- **Z26184 (solfege to sargam) design** — decomposed as a pure Wikidata-driven
  pipeline: solfege string → scale degree item (Z30555) → svara item (via P460)
  → English noun sargam lexeme (via P5137) → lemma string. All 7 diatonic
  syllables validated via API.
- **Z33668 "word for concept"** — new reusable function shell. Signature:
  `(Z6091 concept, Z60 language, Z6091 lexical category) → Z6`. Bundles
  `Z33071` + `Z21806` so any "concept → word in language" lookup is one call.
- **Z33677** — composition implementation for Z33668. Published via browser
  automation. **Not yet connected** to Z33668 (the function's Z8K4 list is
  empty); user needs to toggle "connected" in the on-wiki implementations
  table for the runtime to use it.

## What we learned about Wikifunctions data

- Scale-degree items connect to svara items through **P460 "said to be the
  same as"** with qualifier **P3831 "object of statement has role" = Q7380503
  (svara)**. Pattern holds for all 7 degrees.
- All 7 English sargam syllables exist as lexemes with P5137 senses pointing
  to the svara items: sa/re/ga/ma/pa/dha/ni (L1548440, L326409, L1548441,
  L323484, L324925, L1551696, L1551697).
- **Menu items no longer consistently include "(Z#####)" in their text.**
  Older inspects saw `"label (Z33071)"`; newer ones just show `"label"`.
  Matching by ZID substring alone is unreliable now — match by ZID OR label
  prefix (the toolkit now does both).

## Broken helpers found

- **Z22806 "lexeme from item, language, and category"** — declared but has
  no implementations. If someone adds one, it'd be a drop-in pivot point for
  Z33668's internals.
- **Z31655 "item from item with property and qualifier"** (and Z31659) —
  declared types are full objects (Z6002/Z6001) but the implementation builds
  a Z6007 claim expecting references (Z6092/Z6091). Worse, the implementation
  hardcodes `Z6007K3: "Z6021"` (string) while real statements have
  `Z6007K3: {Z1K1: Z6020, Z6020K1: Z6021}` (object) — so the exact-match
  qualifier filter finds nothing. Worth filing.

## Browser automation — all fixes applied to wf_browser.rb / wf_task_composition.rb

This session hardened the browser toolkit significantly. Every bug below is
now fixed; future composition runs should not have to rediscover them.

1. **Profile lock guard (`ensure_profile_free!`)** — refuses to start a
   second chrome on the same profile. Detects ownership via the
   SingletonLock / `lock` symlink target PID and `Process.kill(0, pid)`.
   Handles dead PIDs (stale lock = safe to clean) vs. live PIDs (raise with
   PID in the message). Fixed the "lost the browser profile" incident.

2. **10s cap on every step + screenshot at 4s (`slow_wait` helper)** —
   replaces most `Wait.new(timeout: 30)` usages. Saves a screenshot to
   `/tmp/wf-stuck-<tag>-<time>.png` once a wait runs past 4s, and raises
   TimeoutError at 10s. Exceptions: login (600s) and publish (24h) —
   those wait for manual user action.

3. **Error handler quits browser instead of sleeping forever** — the old
   `rescue ... sleep` meant any failed step stalled the whole run until
   Ctrl+C. Now: final screenshot, quit, `exit 1`.

4. **`select_in_lookup` — aggressive clear + label match**
   - Pre-populated Z7K1 slots (auto-selected by type) required a multi-pronged
     clear: chip-remove selectors, focus-click, JS `el.value = ''` +
     input/change event dispatch, select-all + backspace.
   - Matching by `zid` substring fails when the menu text doesn't include
     the ZID. Fall back to `label.start_with?` where label comes from the
     API metadata fetched at startup.
   - Match items with `.displayed? rescue false` filter off — Selenium
     treats items scrolled out of a scrollable dropdown as not displayed.
     Native click on the matched item scrolls it into view.
   - Hard abort when no match (with a dump of all visible menu-item texts)
     instead of fallback-picking a wrong function.

5. **`switch_mode` — native click, not dispatchEvent**
   - `dispatchEvent(new MouseEvent)` fires synthetic events that Codex's
     Vue `select-item` pipeline ignores. Use Selenium's native `.click()`
     on the element located by `.cdx-menu-item[type='Z7']` (or Z18/Z9).

6. **`expand_at` — universal + icon-class-aware**
   - Detects collapsed state via the
     `ext-wikilambda-app-expanded-toggle__icon--collapsed` class, so it's
     a no-op when already expanded (safe to call from any branch of
     `fill_argument`).
   - Called at the start of `fill_argument` for all node types (call / ref
     / literal), because every fresh arg slot starts collapsed.

7. **`select_arg_ref` — scope to Z18K1 sub-slot**
   - Without scoping, `[role="combobox"]` also matched lingering hidden
     Wikidata-item lookup inputs from the old literal mode. Scoping to
     `{keypath}-Z18K1` reliably finds the `cdx-select-vue__handle`.
   - Open dropdown via `open_codex_select` helper: Actions move+click,
     then native click, JS click, focus+space, focus+enter. First
     strategy to flip `aria-expanded=true` wins.
   - Match menu item by exact `casecmp` on text.

8. **`fill_literal` — scope to value sub-slot + ActionChains**
   - Scope to `{keypath}-{type}K1` (e.g. `-Z6092K1`) not the container —
     otherwise the first input found is the Z1K1 type-marker display, and
     the P-number ends up in the wrong row.
   - Drive input with `@driver.action.move_to(input).click.perform` +
     `@driver.action.send_keys(value).perform`. JS set-value doesn't
     trigger the autocomplete network fetch; `input.send_keys` hits
     "element not interactable" on Codex lookups.
   - Dropdown match is now optional (3s timeout, don't raise) — some
     Wikidata selectors resolve the raw P/Q-number at publish time
     without showing a suggestions menu.

9. **Add input ("function shell" task)** — the "Add another input" button
   has no testid and lives inside the same container as per-row "Remove
   input" buttons. Select by text prefix `^Add/i` instead of first-button.

## Outstanding

- **Connect Z33677 to Z33668.** Until then Z33668 returns Z503 (not
  implemented). Once connected, `solfege_to_sargam.comp.json` (updated this
  session to call Z33668 directly) drops from 5 levels to 4 and is ready
  to publish.
- **Consider shortening the log filename convention** — switched to
  `/tmp/wf_comp_run.log` this session to avoid re-approving each run.
  Worth keeping as the default.

## Workflow rule added

**After publishing a new implementation, always wait for the user to
connect it to its function before returning.** New implementations on
Wikifunctions are created disconnected (not in the function's Z8K4 list);
until toggled "connected" in the on-wiki implementations table, the
runtime returns Z503 (no implementation) and any API/test call fails.

Implemented as `WfBrowser#wait_for_impl_connected(function_zid, impl_zid)`:
polls the function's Z8K4 via the API every 5s until the new impl ZID
appears. Called from `WfTaskComposition#run` after `verify_published`.
24h soft cap to match the publish wait.
