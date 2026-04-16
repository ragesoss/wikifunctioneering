# Session: Generalizing pitch frequency to arbitrary pitch standards

**Date:** 2026-04-15

## Goal

Create a function that takes a pitch (e.g., "Eb5") and a Wikidata pitch standard item (e.g., A440 or scientific pitch) and returns the frequency in Hz. This generalizes the existing Z25217 (frequency of pitch in A440) to work with any 12-TET pitch standard.

## Wikidata modeling completed

Added P2144 (frequency) with qualifier P518 (applies to part) to pitch standard items:

- **A440 (Q2610210):** P2144 = 440 Hz, qualifier P518 → A4 (Q96254322)
- **Scientific pitch (Q17087764):** P2144 = 256 Hz, qualifier P518 → middle C (Q32700582)

Reference note items already had MIDI numbers:
- A4 (Q96254322): P361 → MIDI note numbers (Q96252942), qualifier P1545 = 69
- Middle C (Q32700582): P361 → MIDI note numbers (Q96252942), qualifier P1545 = 60

## Functions created

### Z33573: qualifier value of item property claim (helper)
- **Inputs:** item (Z6001), property (Z6092), qualifier (Z6092)
- **Output:** Z1
- **Implementation:** composition using Z23451 → Z28312 → Z811 → Z28297
- **Tests:** Mars density/phase (passing), A440/P2144/P518 (failing — Wikidata cache issue), scientific pitch/P2144/P518 (passing)
- **Reusable** for any "get a qualifier value from an item's property claim" pattern

### Z33570: reference note of pitch standard
- **Inputs:** pitch standard (Z6001)
- **Output:** Z6091 (Wikidata Item Reference)
- **Implementation:** composition using Z23742(Z33573(standard, P2144, P518))
- **Tests:** Scientific pitch → Q32700582 (passing), A440 → Q96254322 (failing — cache)

## Functions remaining

### 2. MIDI number of Wikidata pitch item
- **Inputs:** note (Z6001)
- **Output:** Integer
- Plan: both composition and Python implementations
- Composition is deep (10 levels) — uses Z28513 to filter P361 claims by having P1545 qualifier, then extracts the P1545 value and converts string → integer
- Key building blocks: Z29691, Z28513, Z28312, Z811, Z28297, Z31120, Z14283, Z17101
- Python is cleaner for this one (nested for loop with value-matching)

### 3. MIDI number of pitch
- **Inputs:** pitch class (String), octave (Integer)
- **Output:** Integer
- Plan: composition using Z25220 (distance from C) + integer math
- Formula: (octave + 1) × 12 + distance_from_C(pitch_class)
- Composition tree: Z16693(Z17120(12, Z16693(octave, 1)), Z25220(pitch_class))

### 4. Reference frequency of pitch standard
- **Inputs:** pitch standard (Z6001)
- **Output:** Float64
- Plan: composition chaining Z25218 → Z25294 → Z20854
- Three existing functions, straightforward

### 5. Frequency of pitch in equal temperament pitch standard (top-level)
- **Inputs:** pitch class (String), octave (Integer), pitch standard (Z6001)
- **Output:** Float64
- Plan: composition
- Formula: ref_freq × 2^((input_midi − ref_midi) / 12)
- Composition tree uses: Z21032 (multiply float64), Z25232 (frequency ratio), Z17111 (subtract integer), functions 1-4, Z6821 (fetch item)

## Known issues

### Wikidata cache on Wikifunctions
- A440 (Q2610210) data was stale for several hours after adding P518 qualifier — resolved by end of session
- No user-facing cache purge mechanism exists; `wikilambda-bypass-cache` right is staff-only
- Relevant Phabricator tickets: T338243, T379432, T390549, T397409
- All tests now passing for both A440 and scientific pitch

## What went well

- **Z33573 helper** — extracting the generic "qualifier value from item property claim" pattern into a reusable helper was very effective. It simplified Z33570 from a 5-level composition to 2 levels.
- **composition_guide.py** — the script that generates step-by-step UI instructions from a JSON composition tree is valuable. It matches the top-down workflow of the Wikifunctions composition editor.
- **Z33103 (statement value is reference to item?)** — discovered this existing function, which will be key for the future "qualifier value matching specific claim value" helper.
- **Z23451 (statement with highest rank)** — key shortcut that goes directly from (item, property) to the statement, avoiding the Z22220 → Z32097 → Z23680 chain.

## What was missing

- No documentation on when to use Z6091 vs Z6001 (or Z6092 vs Z6004) in function signatures — added to wikidata-integration.md during session.
- No way to purge Wikifunctions' Wikidata entity cache — significant friction when iterating on data models.
- The composition_guide.py script was created during the session — should have existed beforehand.

## What was wrong

- Z21449's name "first value of property from wikidata item" is confusing — it returns the main value, not qualifier values. Easy to mistake for something that shows qualifiers.
- Z25218's name "A4 frequency of pitch standard" is misleading for the general case (scientific pitch returns C4's frequency, not A4's).

## Suggestions

1. **Add composition_guide.py to the standard toolset** in CLAUDE.md — it should be the default way to present compositions to the user.
2. **Document the Z33573 helper pattern** in existing-building-blocks.md once it's proven stable — it's a fundamental Wikidata access pattern.
3. **Create the "qualifier value matching specific claim value" helper** (documented in future-helpers.md) — needed for any item with multiple claims for the same property.
4. **Add a "cache status" note to session docs** when Wikidata items are edited mid-session — helps the next session know which tests might be affected.
