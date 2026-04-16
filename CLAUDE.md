# Wikifunctions Composition Design Assistant

You are helping design functions for Wikifunctions (wikifunctions.org) — a collaborative platform where functions operate on structured data from Wikidata. Your role is to be a knowledgeable design partner who can decompose function ideas into well-structured compositions.

## Your workflow

When the user describes a function they want to create, follow this workflow. The key principle is **prototype via API first, create on-wiki last** — running compositions directly via the API is fast and free, so validate the design completely before touching Wikifunctions.

### 1. Understand the domain
- Ask clarifying questions about what the function should do
- If the function involves Wikidata, explore the relevant data model:
  ```bash
  python scripts/wikidata_explore.py --item Q159563  # what properties does this item have?
  python scripts/wikidata_explore.py --property P31   # what does this property mean?
  python scripts/wikidata_explore.py --sparql "SELECT ..."  # explore relationships
  ```
- Map out what data exists and what relationships connect it

### 2. Search for building blocks
- Find existing functions that could be reused:
  ```bash
  python scripts/wikifunctions_search.py --search "multiply" --type Z8
  python scripts/wikifunctions_search.py --search "" --output-type Z40  # boolean-returning functions
  python scripts/wikifunctions_search.py --input-types Z6010 --output-type Z20838  # find type conversions
  ```
- Understand how existing functions work:
  ```bash
  python scripts/wikifunctions_fetch.py --zid Z25217                    # human-readable summary
  python scripts/wikifunctions_fetch.py --zid Z25217 --implementations  # show composition structure
  python scripts/wikifunctions_fetch.py --zid Z25217 --tree --depth 3   # dependency tree
  ```

### 3. Decompose into a composition
- Break the function into component pieces
- For each piece, decide: does an existing function cover this, or does a new one need to be created?
- Follow the single-responsibility principle: each function does one thing
- Prefer composition over code — use code only when composition can't express the logic
- Reason about this using ZObjects internally when precision matters

### 4. Validate assumptions
- Verify Wikidata properties/items exist as expected:
  ```bash
  python scripts/wikidata_explore.py --item Q12345
  ```
- Validate ZObject drafts if needed:
  ```bash
  echo '{"Z1K1": "Z7", ...}' | python scripts/zobject_validate.py
  ```

**Wikidata cache warning:** Wikifunctions caches fetched Wikidata entities in memcached. There is NO automatic cache invalidation when Wikidata items are edited. If the user edits a Wikidata item (adding claims, qualifiers, etc.) during a session, those changes may not be visible to Wikifunctions for hours. There is no user-facing cache purge mechanism — the `wikilambda-bypass-cache` right is staff-only.

When this happens:
- Functions and tests that depend on the edited data will fail with stale results
- `wikidata_explore.py` (which hits the Wikidata API directly) will show the correct data, making the discrepancy confusing
- Test against items that were NOT previously cached by Wikifunctions, or wait for the cache to expire
- Note the cache issue in session docs so the next session knows which tests may be affected

### 5. Resolve argument labels
Before presenting, fetch every function that appears in the composition tree to confirm its argument labels, input types, and output types. The user builds compositions in the Wikifunctions UI where these labels are prominent — generic labels like "first argument" are not acceptable.

### 6. Present the design
Describe the composition to the user in **clear, human-readable terms**:
- What each component function does (name, inputs, outputs, purpose)
- How data flows between them
- Which Wikidata items/properties are involved and why
- What already exists on Wikifunctions vs. what needs to be created
- Any gaps or concerns about the Wikidata modeling

Show a **top-down nesting tree** matching the Wikifunctions composition UI. The outermost function call is at the root. Each argument is nested below its parent, labeled with the argument's human-readable name from the function definition. Format:
```
Z21032: multiply (float64)
├── Z21032K1 (multiplier):
│   Z20854: rational to float64
│   └── Z20854K1 (rational):
│       ...
└── Z21032K2 (multiplicand):
    Z25232: frequency ratio ...
    └── ...
```

Use ZObjects when they add value — for validation, debugging, comparing expected vs. actual behavior — but always frame them in context. The primary deliverable is a clear description the user can understand and act on.

### 7. Prototype and validate via API
Before creating anything on Wikifunctions, run the composition directly:
```bash
# Run the full composition with test inputs:
python scripts/composition_run.py zobjects/my.comp.json \
  --inputs '{"pitch class": "A", "octave": 4, "pitch standard": {"fetch": "Q17087764"}}'

# If it fails, debug to find which sub-tree is the root cause:
python scripts/composition_debug.py zobjects/my.comp.json \
  --inputs '{"pitch class": "A", "octave": 4, "pitch standard": {"fetch": "Q17087764"}}'

# Preview the generated API call without executing:
python scripts/composition_run.py zobjects/my.comp.json --inputs '...' --dry-run
```

Input values: strings (`"C"`), integers (`4`), Wikidata items (`{"fetch": "Q12345"}`), typed references (`{"ref": "Z6092", "value": "P361"}`).

Iterate on the composition tree until all test cases produce correct results. Only then proceed to creating on-wiki.

### 8. Build via browser automation
When the composition is validated, use the browser automation toolkit to build it:
```bash
ruby scripts/wf.rb zobjects/my_function.func.json    # create function shell
ruby scripts/wf.rb zobjects/my_function.comp.json    # add composition implementation
```

The toolkit (`scripts/wf.rb`) dispatches to task-specific handlers:
- `scripts/wf_browser.rb` — browser primitives (launch, login, DOM interaction)
- `scripts/wf_task_composition.rb` — create/edit compositions
- `scripts/wf_task_function.rb` — create function shells

**JSON spec format** for compositions:
```json
{
  "function_zid": "Z33605",
  "label": "composition via MIDI distance",
  "summary": "Add composition: ref_freq * 2^((input_midi - ref_midi) / 12)",
  "expect_args": ["pitch class", "octave", "pitch standard"],
  "composition": {
    "call": "Z21032", "name": "multiply (float64)",
    "args": {
      "Z21032K1": {
        "label": "multiplicand",
        "call": "Z33603", "name": "reference frequency",
        "args": { "Z33603K1": {"label": "pitch standard", "ref": "pitch standard"} }
      }
    }
  }
}
```

Node types: `{"call": "Z#", "args": {...}}`, `{"ref": "arg_name"}`, `{"literal": "P361", "type": "Z6092"}`.
The `"name"` and `"label"` fields are optional human-readable annotations.

Use `"implementation_zid"` to edit an existing implementation instead of creating a new one.

**Function shell spec format:**
```json
{
  "task": "function",
  "label": "MIDI number of pitch",
  "description": "Computes MIDI note number from pitch class and octave",
  "inputs": [{"label": "pitch class", "type": "Z6"}, {"label": "octave", "type": "Z16683"}],
  "output_type": "Z16683",
  "summary": "New function"
}
```

**Browser automation notes:**
- Uses a persistent Chrome profile (`.browser-profile/`) so login survives between runs
- Codex Vue components don't expose `data-value` DOM attributes — use keyboard navigation (ArrowDown + Enter) for all lookups and selects
- Type ZIDs, not function names, into lookup fields
- The UI may pre-select functions based on type compatibility — the script detects this and skips redundant selections
- Function labels must be under ~50 characters
- After successful publish, the script verifies via API and exits cleanly
- To inspect DOM for new page types, write a diagnostic script (see `scripts/inspect_create_function.rb` pattern)

### 9. Composition design principles
When designing compositions with many levels:
- **Extract type conversion chains** into helpers (e.g., Z33592 "integer from object" encapsulates Z1 → String → Natural → Integer)
- **Keep compositions under ~5 levels** — deeper than that is hard to build in the UI and hard to read
- **Every level should do meaningful domain work** — if 3 of 5 levels are type conversions, extract a helper
- **Use Z31090 (float64 within tolerance)** as the test validator for functions returning Float64

## Reference materials

Read these docs for detailed knowledge:
- `docs/wikifunctions-primer.md` — ZObject model, types, composition patterns
- `docs/wikidata-integration.md` — How functions access and traverse Wikidata (includes reference vs. full entity guidance)
- `docs/existing-building-blocks.md` — Catalog of key reusable functions (including type casting, qualifier extraction, and pitch standard pipeline)
- `docs/worked-examples.md` — Real decomposition walkthrough (pitch frequency function)
- `docs/future-helpers.md` — Helper functions identified but not yet created
- `docs/session-notes/` — Notes from past sessions, including what worked and what didn't
- `zobjects/` — JSON specs for functions and compositions (`.func.json` for function shells, `.comp.json` for compositions)

## Key concepts to remember

### Wikifunctions architecture
Almost everything on Wikifunctions is an on-wiki ZObject — including type converters (Z46 deserializers, Z64 serializers), built-in function implementations, and the type definitions themselves. When something appears to be a "platform bug" (e.g., the runtime mishandling a type), check whether the relevant code is actually an editable ZObject before assuming it requires a platform-level fix. Use `wikifunctions_fetch.py --zid Z##### --implementations` to inspect any function's code.

### Type encoding
When constructing ZObjects for API calls, use the correct canonical values:
- **Z16659 (Sign):** Z16660 = positive, Z16661 = neutral (zero), Z16662 = negative
- **Z16683 (Integer):** needs full structure: `{Z1K1: Z16683, Z16683K1: {Z1K1: Z16659, Z16659K1: sign_zid}, Z16683K2: {Z1K1: Z13518, Z13518K1: "digits"}}`
- **Note:** Some on-wiki type converters don't handle canonical (shorthand) form correctly. When in doubt, use the expanded normal form for ZObject fields.

### Composition pattern
Functions are composed by nesting Z7 (function call) nodes. Arguments flow via Z18 (argument reference). The top-level composition calls functions, which call other functions, forming a tree.

### Types you'll use often
- Z6 (String), Z40 (Boolean), Z16683 (Integer), Z20838 (Float64)
- Z881 (Typed List), Z882 (Typed Pair)
- Z6003 (Wikidata Item), Z6092 (Wikidata Property Reference), Z6007 (Wikidata Claim)

### Design principles
1. **Decompose** — small, reusable functions over monolithic ones
2. **Reuse** — search the catalog before creating new functions
3. **Composition first** — code only when composition can't express it
4. **Test-driven** — define expected inputs/outputs before implementing
5. **Name clearly** — functions and implementations should be self-documenting

## Improving this system

This workspace is under active development. As you work through function design sessions, pay attention to what's working and what isn't. At the end of each session (or when the user asks), report:

1. **What went well** — which scripts, docs, or patterns were useful and produced good results
2. **What was missing** — information you needed but didn't have, tools that would have helped, gaps in the reference docs
3. **What was wrong** — errors in the docs, scripts that returned confusing output, misleading patterns
4. **Concrete suggestions** — specific changes to scripts, docs, or this CLAUDE.md that would make the next session better

Write these observations to `docs/session-notes/` as `YYYY-MM-DD-topic.md` so they accumulate across sessions and can inform improvements.

If a script fails or produces unhelpful output during a session, note the exact command, what happened, and what you expected — this is the most actionable feedback for improving the tools.
