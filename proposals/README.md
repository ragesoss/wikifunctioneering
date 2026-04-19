# Wikidata edit proposals

This directory holds **proposed Wikidata edits** — one JSON file per
proposal. A proposal describes what change(s) we want to make on
Wikidata, captures the rationale, surfaces context for review, and
(once approved) drives the actual edits via `scripts/wd_apply.py`.

Proposals are **session-local working artifacts**. The `.gitignore` in
the repo root excludes every file in this directory except what's
under `examples/` and this README. When you start a new proposal,
write the JSON here; don't commit it unless you promote it to a
template.

## Workflow

```
draft  →  (review with wd_propose.py)  →  (approve in conversation)
       →  (apply with wd_apply.py)     →  posted
```

- **Review:** `python scripts/wd_propose.py --slug <slug>` renders the
  proposal with labels resolved, auto-pulled context, and a list of
  SPARQL-heavy probes you can opt into via `--with name[,name…]` or
  `--full`.
- **Dry-run:** `python scripts/wd_apply.py --slug <slug>` shows the
  semantic diff (what changes on Wikidata, in entity/triple terms) plus
  the raw API payloads that would be posted.
- **Apply:** `python scripts/wd_apply.py --slug <slug> --apply` logs in
  via the bot password in `.env`, posts each op, substitutes new IDs
  for placeholders, and writes back the resolved result into the
  proposal file.

## Supported op kinds

- `create_item` — new Q-item with labels/descriptions/aliases/claims
- `add_sense` — append a new sense to an existing lexeme
- `add_claim` — add a statement on any entity (Q, L, or L-Sn for senses)
- `update_description`, `add_alias`, `update_label` — planned; thin
  wrappers

Ops can reference placeholders created by earlier ops in the same
proposal (e.g. `{NEW_CANCEL}` resolves to the Q-ID returned from the
first `create_item`). Apply resolves placeholders in both the `entity`
and `value` fields.

## Examples

See `examples/` for worked templates, all of which represent real
edits that landed on Wikidata:

- `example-new-concept-item.json` — the simplest shape. One
  `create_item` op. Posted as Q139480165 "user interface command."
- `example-concept-with-new-lexeme-sense.json` — three chained ops:
  `create_item` + `add_sense` + `add_claim` with placeholder
  resolution. Posted as Q139480774 "cancel" + a new L13009-S4 sense
  linked via P5137.
- `example-investigate-only.json` — a backlog proposal with no ops,
  just `entities_of_interest` + `open_questions`. Useful when you
  spot a problem on Wikidata that warrants investigation before any
  edit is possible.
