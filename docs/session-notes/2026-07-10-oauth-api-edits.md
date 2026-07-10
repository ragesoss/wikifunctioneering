# 2026-07-10 — OAuth API edits work now (browser mostly optional)

Built the **Flesch Reading-Ease score** function (Z37551) and, in the
process, discovered that the long-standing "you must edit through the
browser" constraint is largely gone.

## Headline: `wikilambda_edit` via OAuth token now works

`scripts/wf_api.rb` had a note claiming wikilambda-* rights weren't in
`$wgGrantPermissions`, so OAuth/bot tokens got `Z557` and everything had
to go through a logged-in browser session. **That's no longer true.**

Probing the token's granted rights:

```
action=query&meta=userinfo&uiprop=rights  (Authorization: Bearer $WF_OAUTH_TOKEN)
-> wikilambda-execute, wikilambda-create, wikilambda-create-function,
   wikilambda-create-implementation, wikilambda-create-tester,
   wikilambda-edit, wikilambda-edit-implementation, wikilambda-edit-tester,
   wikilambda-edit-user-function, ... (full set)
```

Confirmed with **real creates**, no browser:

```bash
ruby scripts/wf_emit_zobject.rb zobjects/flesch_reading_ease_test_2.tester.json \
  | CLAUDE_MODEL=claude-opus-4-8 python scripts/wikifunctions_edit.py create --summary "..."
# -> Success: Z37554     (tester 2)
# -> Success: Z37555     (tester 3)
```

`scripts/wikifunctions_edit.py` (OAuth bearer + csrf) had existed but was
apparently never exercised because of the stale Z557 belief. It works.

## The one thing the token still can't do: connect

Editing a function to add a tester/impl to `Z8K3`/`Z8K4` — i.e. the
"connected" toggle — is refused:

```
update Z37551 (append Z37554,Z37555 to Z8K3)
-> "You don't have permission to edit Function that has a connected Implementation."
```

The UI toggle works because it runs in the user's full session, which
carries a right the OAuth grant doesn't. **Connecting stays a manual
step** (the user toggles on the function page). This is fine — it was
always manual in our flow; `wf.rb` only ever *waited* for the user to
click.

Untested via API: **function-shell creation** (Z8 with arg list + labels
+ output type). `wf_emit_zobject.rb` only emits Z14/Z20 so far. Z37551's
shell was made via the browser (`wf.rb --mode=ui`). Emitting Z8 shells is
the obvious next tooling gap to close.

## New / changed tooling this session

- **`scripts/wf_emit_zobject.rb`** (new) — headless emitter. Reads a
  `.comp.json` / `.tester.json` spec, reuses `WfZObjectEmitter`, fetches
  arg labels via `?action=raw` to resolve `{"ref": ...}` nodes, prints a
  server-ready Z2. Pipe into `wikifunctions_edit.py create`.
- **AI-disclosure `{model}` placeholder** — `.env` `AI_DISCLOSURE` was
  hardcoded to "Claude Opus 4.7" (wrong; caused manual edit-summary
  fixes). Now `AI_DISCLOSURE=Created with AI assistance ({model})`, and
  both `wf_browser.rb` (Ruby) and `config.py` (Python) fill `{model}`
  from `CLAUDE_MODEL` / `AI_MODEL`, dropping the parenthetical if unset.
  **Pass `CLAUDE_MODEL=claude-opus-4-8` (your model id) on every build
  invocation.** There is no harness env var exposing the model, so the
  driver must supply it.
- **`wf.rb --mode=api` auto-save** — api mode used to block on
  `$stdin.gets` for a manual Save, which is EOF under Claude (browser
  closed before saving). Now `wf.rb` auto-clicks Save when stdin is not a
  TTY (`save_raw_json` in `wf_browser.rb` + `commit_api` on the tasks),
  and still waits for the human review+save when interactive. This is now
  moot for compositions/testers (use the API path), but kept for shells.

## Flesch function, for reference

- Z37551 — function shell (words, sentences, syllables : Integer → Float64)
- Z37552 — composition: `206.835 - (1.015*W/S) - (84.6*Y/W)` via float64
  arithmetic (Z21031 subtract / Z20849 add / Z21032 multiply / Z21033
  divide / Z20937 int→float64 / Z20915 string→float64)
- Z37553 / Z37554 / Z37555 — testers (100/10/150→69.785, 120/8/180→64.71,
  60/3/120→17.335), validator Z31090 float64-within-tolerance (0.001)

All connected and verified live via `wikilambda_function_call`.

## Suggestion for next session

Close the function-shell gap: extend `wf_emit_zobject.rb` (or add
`wf_emit_function.rb`) to emit a Z8 shell from a `.func.json` spec, so the
*entire* create flow (shell → composition → testers) is browser-free and
only the connect toggle needs a human. Then `wf.rb`/Selenium/the Chrome
profile become truly optional.
