# Worked Example: Frequency of a Musical Pitch (Z25217)

## The prompt

> "I want a function that calculates the frequency of a musical pitch based on the A440 standard. It takes a pitch class and octave (like C4) and returns a frequency in hertz."

## The math

The frequency of a pitch in 12-tone equal temperament (A440 standard) is:

```
frequency = 440 × 2^(n/12)
```

where `n` is the number of semitones between the given pitch and A4.

## Decomposition strategy

Rather than implementing this as a single code function, we break it into reusable pieces:

### Level 1: The top-level function

**Z25217: frequency of pitch in A440 equal temperament**
- Inputs: pitch class (String, e.g. "C"), octave (Integer, e.g. 4)
- Output: Float64 (frequency in Hz)
- Composition: `multiply(440, frequency_ratio(semitone_distance_from_A4(pitch_class, octave)))`

This composes three things:
1. Calculate how many semitones the pitch is from A4
2. Convert that semitone distance to a frequency ratio
3. Multiply 440 by that ratio

### Level 2: The direct building blocks

**Z25230: semitone distance from A4**
- Inputs: pitch class (String), octave (Integer)
- Output: Integer (signed distance in semitones)
- Composition: calls Z25219 with the input pitch and hardcoded reference "A", 4
- Why a separate function: reusable — any A440-based calculation needs this

**Z25232: frequency ratio of semitone distance in 12TET**
- Inputs: semitone distance (Integer)
- Output: Float64
- Composition: `exponentiate(2.0, divide(integer_to_float(semitones), 12.0))`
- Why a separate function: reusable for any 12TET interval calculation

**Z21032: multiply (float64)** — already existed, generic math

### Level 3: Lower-level building blocks

**Z25219: difference between pitches in semitones**
- Inputs: first pitch class (String), first octave (Integer), second pitch class (String), second octave (Integer)
- Output: Integer
- Composition: `add(semitones_between_octaves(oct1, oct2), semitones_within_octave(pitch1, pitch2))`
- The most general form: works for any two pitches

**Z25227: semitones between octaves**
- Inputs: two octave numbers (Integer, Integer)
- Output: Integer
- Composition: `multiply(12, subtract(octave2, octave1))`

**Z25224: semitones between pitches within an octave**
- Inputs: two pitch class strings (String, String)
- Output: Integer
- This is the leaf that encodes the chromatic scale mapping (C=0, C#=1, D=2, ..., B=11)

### Pre-existing functions used (already on Wikifunctions)

- Z21032: multiply (float64)
- Z21028: exponentiation (float64)
- Z21033: divide (float64)
- Z20937: integer to float64
- Z16693: add integers

## What Claude would need to know to design this

### Domain knowledge (music theory)
- The A440 formula: `freq = 440 × 2^(n/12)`
- Pitch = pitch class + octave (scientific pitch notation)
- Semitone distance calculation splits into within-octave + between-octave parts

### Wikifunctions knowledge
1. **Available types**: String (Z6), Integer (Z16683), Float64 (Z20838)
2. **Available math functions**: multiply, divide, exponentiate, add, integer-to-float conversion
3. **Composition pattern**: nest Z7 function calls, use Z18 to thread arguments through
4. **Design principle**: decompose into small, reusable functions rather than one big implementation
5. **Naming convention**: descriptive names, implementations named by what they do (e.g. "440 times the frequency ratio")

### What Claude could discover via scripts

Against the local cache (preferred — also supports input/output type filters
and reverse-dependency search):
- `cache_query.py functions --label multiply` → Z21032 (and sibling arithmetic)
- `cache_query.py functions --input Z20838 --output Z20838 --label "exponent"` → Z21028
- `cache_query.py functions --input Z20838 --output Z20838 --label divide` → Z21033
- `cache_query.py functions --input Z16683 --output Z20838` → Z20937 (integer to float64)
- `cache_query.py functions --input Z16683 --output Z16683 --label add` → Z16693

Live fallback for very recent edits:
- `wikifunctions_search.py --search "multiply" --type Z8`

### What Claude would need in reference docs
- The type system: what Z6, Z16683, Z20838 are and when to use them
- The composition mechanics: Z7 function calls, Z18 argument references, literal values
- The design philosophy: small composable functions > monolithic implementations
- How to represent literal Float64 values (the 440.0 and 2.0 constants) — these are complex ZObjects with sign, exponent, significand, special-value fields

## Dependency tree

```
Z25217: frequency of pitch in A440 equal temperament [Function]
  Z25234: 440 times the frequency ratio [Composition]
    Z21032: multiply (float64) [pre-existing]
    Z25230: semitone distance from A4 [Function]
      Z25231: composition using 'difference between pitches' [Composition]
        Z25219: difference between pitches in semitones [Function]
          Z25229: distance within octave + octave difference [Composition]
            Z25227: semitones between octaves [Function]
            Z25224: semitones between pitches within an octave [Function]
            Z16693: add integers [pre-existing]
    Z25232: frequency ratio of semitone distance in 12TET [Function]
      Z25233: 2^(n/12) [Composition]
        Z21028: exponentiation (float64) [pre-existing]
        Z21033: divide (float64) [pre-existing]
        Z20937: integer to float64 [pre-existing]
```

## Test cases

- A4 → 440 Hz (trivial/sanity check)
- A3 → 220 Hz (one octave down = half frequency)
- C0 → ~16.352 Hz (edge case: low pitch, different pitch class)
