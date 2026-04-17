# Session: raw-JSON userscript + API route

Date: 2026-04-17

Goal of the session: investigate whether the `wikilambda_edit` API (as
exposed by the Feeglgeef "Edit Raw JSON" userscript on Wikifunctions)
can replace or augment the Selenium-driven UI flow. Result: yes, and
the new path is now the default for compositions and testers.

## What got built

- **Forked userscript at `userscripts/wikilambda-edit-source.js`**
  (based on User:Feeglgeef/wikilambda_editsource.js). Fixes a handful
  of upstream bugs: `mw.config.get('wgPageContentModel')` instead of
  property access, real error surfacing (`mw.Api` rejection's `(code,
  data)` pair rendered via `describeError`), client-side `JSON.parse`
  before POST, `assert: 'user'` so expired sessions fail loudly,
  `preventDefault()` on the portlet click. Adds a **Create Raw JSON**
  portlet alongside the existing Edit Raw JSON — opens an empty
  editor and Save omits the `zid` param, and on success navigates to
  the server-assigned new ZID. All DOM elements have stable IDs
  (`#wf-raw-json-textarea`, `#pt-wf-raw-json-edit`, etc.) for
  automation.

- **`scripts/wf_api_probe.rb`** — a standalone probe that launches
  Chrome, fetches a Z-object via `?action=raw`, and POSTs it back
  unchanged via `mw.Api().post({action: 'wikilambda_edit', …})` using
  the session's CSRF token. Confirmed round-trip works cleanly and
  revealed the response shape.

- **`scripts/wf_api.rb`** (mixed into `WfBrowser`) — `api_fetch_raw`
  and `api_wikilambda_edit`, both executed inside the browser via
  `driver.execute_async_script`. Kept for diagnostics even though the
  task handlers ended up driving the userscript instead of POSTing
  directly.

- **`scripts/wf_zobject_emitter.rb`** — plain Ruby module that turns
  the existing `.comp.json`/`.tester.json` spec-tree format (call /
  ref / literal nodes) into canonical ZObject JSON. Handles Z6, Z9
  (bare string), Z6091/Z6092, Z13518, Z16683 integer (expanded sign
  + digits form). Also has `new_persistent(content, label:)` that
  wraps content in a Z2 with `Z2K1 = {Z1K1: Z6, Z6K1: "Z0"}` (the
  create placeholder).

- **Userscript-driver helpers on `WfBrowser`**:
  `drive_raw_json_edit(zid:, summary:) { |zobj| ... }` and
  `drive_raw_json_create(zobject_json:, summary:, landing_zid:)`.
  Navigate, wait for the userscript's portlet (proxy for script
  loaded), click, wait for the textarea, then (for edits) yield the
  fetched-and-parsed Z2 for the caller to mutate — or (for creates)
  set the textarea directly. Does **not** click Save. The user
  reviews and saves themselves, then presses Enter in the terminal
  to close the browser.

- **Rewrote `run_api` on `WfTaskComposition` and `WfTaskTester`** to
  use the userscript driver. Both now handle edit and create
  uniformly. `wf.rb` gets `--mode=api|ui|auto` (auto default; only
  function-shell creates still require UI mode).

## What we learned about `wikilambda_edit`

- **Auth:** the API action requires a user session. Bot passwords and
  OAuth both fail with Z557 (wikilambda-* rights aren't in
  `$wgGrantPermissions`). But `mw.Api` running inside a real logged-
  in browser session works fine — that's why the userscript succeeds
  where our earlier Python edit script didn't.

- **Read form = write form = canonical.** `?action=raw` returns
  canonical JSON (bare strings for Z6/Z9 references in unambiguous
  slots, `["Z11", …]` list head-typing). The server accepts the same
  form on write. Our emitter uses the wrapped Z6 form
  (`{Z1K1: Z6, Z6K1: "sol"}`) and the server normalises it back to a
  bare string on storage — both work.

- **Response shape** (on a successful no-op round-trip):
  `{wikilambda_edit: {articleId: 80476, page: "Z33682",
  success: "", title: "Z33682"}}`. For creates, `page`/`title` are
  the newly-assigned ZID — that's how the userscript knows where to
  navigate on success.

- **Creates via API work** — confirmed end-to-end by landing Z33697
  ("sol -> Pa" tester) without ever touching the UI composition
  editor. Convention: omit `zid` from the POST params, set
  `Z2K1 = {Z1K1: Z6, Z6K1: "Z0"}` in the zobject, and the server
  assigns the real ZID on save. Matches what the old Python
  `wikifunctions_edit.py` script anticipated.

## Content bug surfaced (Z26184)

The first real run via the new flow — `zobjects/solfege_to_sargam_sol.tester.json`
— created Z33697 successfully but the test *failed at execution
time*: Z26184 returns `Z507: 'sol'` because its Python implementation
(`Z29517`) uses a hardcoded dict keyed on solfège syllable strings,
and only `'so'` is in the dict, not `'sol'`.

Wikidata side: lexeme **L328094** ("sol", English noun) existed but
had **no senses**. The obvious slot for the solfège sense was missing.
Fix: added sense **L328094-S2** (note: S2, not S1 — Wikidata doesn't
reuse deleted sense IDs) with gloss "solfège syllable representing
the dominant of a musical scale or key" (matching L328069-S2's exact
wording) and `P5137 → Q899391` (dominant).

Wikifunctions side: added `'sol': 'L328094-S2'` to Z29517's Python
dict. End-to-end verified: `Z26184("sol") → "pa"`. Z33697 itself is
still disconnected — needs the normal toggle on Z26184's testers
table.

## Investigated: can user Python impls make HTTP calls?

Prompted by: could we replace Z29517's hardcoded dict with a
Wikidata-driven composition? That needs a lemma-string → lexeme
primitive, which on Wikidata requires SPARQL or `wbsearchentities`.
Could we build it as a code function that hits `action=wbsearchentities`
at runtime?

**Answer: probably no, given current platform.** The Python runtime
is **RustPython on wasmedge** (confirmed via the
`programmingLanguageVersion` / `wasmedgeTotalExecutionTime` metadata
on every Z26184 invocation). WASM sandboxes have no outbound network
by default. Only 13 Z-objects in the cache reference `requests` /
`urllib.request` / `api.php`, and all the ones I inspected are either
broken (Z32046's unquoted URL), sandbox experiments (Z10119
"Sandbox-Function"), or disconnected (Z18720 "English Wiktionary HTML
page content" — 0 connected impls, returns Z503 on call). Couldn't
find a single connected production function that makes outbound HTTP
and runs.

Filed the lemma→lexeme primitive in `docs/future-helpers.md` as
**blocked until Wikifunctions gains either native lexeme search or
sandbox egress.** Once it lands, the Z29517 composition rewrite is
short assembly.

## Gotchas worth remembering

- The userscript's "No changes detected" guard compares the current
  textarea value to the initially-fetched content (closure). When the
  Ruby driver overwrites the textarea, the closure's `initialContent`
  is still the original — so our writes don't trigger the guard.
  Good behavior; flagged here only because it's subtle.

- `mw.Api`'s `.then(success, failure)` rejection gives `(code, data)`,
  and **awaiting it collapses the pair to just `code`.** The probe and
  the userscript both use the explicit two-arg failure callback
  instead of await. This matters because the useful detail
  (`data.error.info`) lives in the second arg.

- `execute_async_script` needs the script-timeout set explicitly —
  Selenium's default is 0 / None. `wf_api.rb` sets 30s for fetch and
  60s for POST.

- VS Code flags the userscript's `fetch(...).then(...)` chain as "may
  be converted to an async function." Ignore — the `.then(success,
  failure)` shape is the deliberate choice for mw.Api compatibility.

## Files added / changed

- `userscripts/wikilambda-edit-source.js` (new)
- `scripts/wf_api_probe.rb` (new)
- `scripts/wf_api.rb` (new)
- `scripts/wf_zobject_emitter.rb` (new)
- `scripts/wf_browser.rb` (added driver helpers, `ai_summary`)
- `scripts/wf_task_composition.rb` (rewrote `run_api`)
- `scripts/wf_task_tester.rb` (rewrote `run_api`)
- `scripts/wf.rb` (added `--mode`, wait-for-Save prompt)
- `zobjects/solfege_to_sargam_sol.tester.json` (new — Z33697)
- `docs/future-helpers.md` (added lemma→lexeme primitive note)
- Memory: `feedback_copypaste_format.md` (don't format pasteable
  values in tables/backticks/bullets)

## What's next

- Toggle Z33697 connected on Z26184's testers table.
- Let the userscript-driven API route bed in over a few more edits/
  creates; collect any new gotchas.
- Keep an eye out for Wikifunctions releasing a native lexeme-search
  primitive; revisit the Z29517 composition rewrite if it lands.
