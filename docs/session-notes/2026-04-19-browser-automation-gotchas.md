# 2026-04-19 — Browser automation gotchas

Two recurring issues with `scripts/wf.rb` that ate time this session.
Both are easy once you know them; both are invisible otherwise.

## `--mode=api` requires an interactive terminal

Since commit b1eec47 (2026-04-17), `wf.rb` defaults composition and
tester tasks to **API mode** — it opens the raw-JSON userscript,
populates textarea + summary, then blocks on `$stdin.gets` waiting
for you to click Save in the browser and press Enter in the
terminal. When invoked through Claude's Bash tool, stdin is EOF at
start, so the `gets` returns immediately, the browser closes, and
nothing gets saved.

**Symptoms:** publish command appears to succeed, no new ZID on the
function page. Script ended at `Press Enter here when you are
done (this closes the browser).` with no further output.

**Fix options:**
- When Claude drives the command: pass `--mode=ui`. The UI path
  (still intact at `wf_task_composition.rb:88` and
  `wf_task_tester.rb`) drives Blockly-style widgets end-to-end and
  auto-clicks Publish. No stdin prompt.
- When the human drives the command: run from your own terminal
  (via the `!` prefix in Claude Code, or a separate shell window).
  API mode works fine there — that's how Z33697 was first created
  on 2026-04-17.

## Browser profile doesn't retain login across runs

`.browser-profile/` is persistent (`--user-data-dir`), but the
Wikimedia session cookie is not. By default, MediaWiki logins set a
session-only cookie that dies when Chrome quits.

**Symptoms:** every `wf.rb` run prints `Not logged in. Please log
in in the browser window.` even though nothing's changed about the
profile.

**Fix:** when you log in, tick the "stay logged in for up to 365
days" (or similar) checkbox on the Wikimedia login form. That
issues a persistent cookie instead of a session cookie. After that,
the profile retains login across launches.

If login still doesn't persist, the most likely secondary cause is
a prior Chrome instance that didn't shut down cleanly — the
`ensure_profile_free!` check blocks a second Chrome on the same
profile, but a crash can leave the cookies file half-written.
Recover by renaming the profile directory and starting fresh:

```bash
mv .browser-profile .browser-profile.old-$(date +%Y%m%d-%H%M%S)
```

## Related landed work

Z33775 (`word for predicate`) function shell + Z33776 composition
published this session, using `--mode=ui` after the API-mode dead
end. UI mode worked cleanly for both the shell and the composition
once we stopped fighting the stdin issue.
