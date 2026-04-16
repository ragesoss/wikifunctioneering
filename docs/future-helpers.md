# Future Helper Functions

Reusable Wikidata helper functions identified during design sessions but not yet created.

## qualifier value of item property claim matching value

Selects a claim by its **main value** rather than by rank, then extracts a qualifier. Needed when an item has multiple claims for the same property (e.g., Obama has five P39/position held claims).

**Signature:**
- `item` — Z6001 (Wikidata Item)
- `property` — Z6092 (e.g., P39)
- `value` — Z6091 (e.g., Q11696 / President of the United States — selects which claim)
- `qualifier` — Z6092 (e.g., P1365 / replaces)
- **Output:** Z1

**Composition tree:**
```
Z28297: value of claim
└── Z28297K1 (claim):
    Z811: head
    └── Z811K1:
        Z28312: qualifiers with predicate
        ├── Z28312K1 (statement):
        │   Z811: head
        │   └── Z811K1:
        │       Z28316: filter with second common element
        │       ├── Z28316K1 (two-argument function): Z33103 (literal ref)
        │       ├── Z28316K2 (list to filter):
        │       │   Z29691: get statements for property from item
        │       │   ├── Z29691K1 (item): ← input: item
        │       │   └── Z29691K2 (property): ← input: property
        │       └── Z28316K3 (second argument common): ← input: value
        └── Z28312K2 (predicate to match): ← input: qualifier
```

**Key building blocks:**
- Z29691 (get statements for property from item) — gets all claims for a property
- Z28316 (filter with bound argument) — filters a list using a two-argument predicate with one arg fixed
- Z33103 (statement value is reference to item?) — the filter predicate: checks if a statement's value matches a given item reference
- Z28312 / Z811 / Z28297 — qualifier extraction chain (same as Z33573)

**Test case:** Obama (Q76), P39 (position held), Q11696 (President), P1365 (replaces) → Q207 (George W. Bush)

**Relationship to Z33573:** Z33573 selects a claim by highest rank — sufficient when there's only one claim for the property (or one with preferred rank). This function selects by value match — needed when multiple claims exist for the same property.
