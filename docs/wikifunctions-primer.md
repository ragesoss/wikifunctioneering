# Wikifunctions Primer

## What Wikifunctions is

Wikifunctions (wikifunctions.org) is a collaborative platform for creating reusable functions that operate on structured data, particularly from Wikidata. Functions are defined as ZObjects — JSON structures that form an abstract syntax tree ("something like LISP in JSON").

## Core ZObject types

Every ZObject has a `Z1K1` key specifying its type. The types you'll encounter most:

| ZID | Name | Purpose |
|-----|------|---------|
| Z2 | Persistent Object | Wrapper for anything stored on a wiki page (has Z2K1=id, Z2K2=value, Z2K3=label, Z2K5=description) |
| Z6 | String | Text value. `{"Z1K1": "Z6", "Z6K1": "hello"}` or just `"hello"` in canonical form |
| Z7 | Function Call | Invoke a function. Z7K1=function reference, then argument keys |
| Z8 | Function | Definition: Z8K1=arguments, Z8K2=return type, Z8K3=testers, Z8K4=implementations |
| Z9 | Reference | Pointer to another ZObject by ZID |
| Z14 | Implementation | Implements a function via composition (Z14K2), code (Z14K3), or builtin (Z14K4) |
| Z17 | Argument Declaration | Defines a function argument: Z17K1=type, Z17K2=key ID, Z17K3=label |
| Z18 | Argument Reference | References a function's input argument by key |
| Z20 | Tester | Test case: Z20K1=function, Z20K2=test call, Z20K3=validator |

## Data types commonly used in functions

| ZID | Name | Notes |
|-----|------|-------|
| Z6 | String | Basic text |
| Z40 | Boolean | Z41=true, Z42=false |
| Z16683 | Integer | Signed: Z16683K1=sign (Z16659), Z16683K2=absolute value (Z13518 natural number) |
| Z13518 | Natural number | Z13518K1=digit string (e.g. "42") |
| Z20838 | Float64 | IEEE 754: Z20838K1=sign, Z20838K2=exponent (Integer), Z20838K3=significand (Natural number), Z20838K4=special value |
| Z16659 | Sign | Z16660=positive, Z16661=neutral (zero), Z16662=negative |
| Z881 | Typed List | Generic: `{"Z1K1": "Z7", "Z7K1": "Z881", "Z881K1": "Z6"}` = List of Strings |

### Wikidata types

| ZID | Name | Notes |
|-----|------|-------|
| Z6003 | Wikidata Item | Full item fetched from Wikidata |
| Z6092 | Wikidata Property Reference | A property ID like P31 |
| Z6007 | Wikidata Claim | A statement from a Wikidata item |

## How composition works

A **composition** implements a function by nesting calls to other functions. No code — just function calls and argument threading.

### The building blocks

1. **Z7 (Function Call)** — call a function with arguments:
```json
{
  "Z1K1": "Z7",
  "Z7K1": "Z21032",       // function to call (multiply float64)
  "Z21032K1": <arg1>,      // first argument (uses the function's own key names)
  "Z21032K2": <arg2>       // second argument
}
```

2. **Z18 (Argument Reference)** — pass through an input from the parent function:
```json
{
  "Z1K1": "Z18",
  "Z18K1": "Z25217K1"     // refers to the parent function's first argument
}
```

3. **Literal values** — inline a constant (type-specific ZObject)

4. **Nesting** — any argument to a Z7 call can itself be another Z7 call, a Z18 reference, or a literal.

### Example: the frequency formula

The composition for `frequency = 440 × 2^(semitones/12)`:

```
multiply(
  440.0,                           // literal Float64
  frequency_ratio(                 // Z25232
    semitone_distance_from_A4(     // Z25230
      pitch_class,                 // Z18 → parent arg K1
      octave                       // Z18 → parent arg K2
    )
  )
)
```

In ZObject JSON, this becomes nested Z7 calls where each argument is either a Z18 reference or another Z7 call.

### Key control flow functions

| ZID | Name | Purpose |
|-----|------|---------|
| Z802 | If | `if(condition, then, else)` — conditional branching |
| Z850 | Try-Catch | Error handling |
| Z851 | Throw Error | Raise an error |

## Design principles

1. **Decompose into small, reusable functions.** Each function should do one thing. A function that "calculates frequency from pitch" should compose "semitone distance" and "frequency ratio" — not inline all the logic.

2. **Check what already exists.** Many math, string, and list operations already exist. Search before creating.

3. **Name clearly.** Functions and implementations should have descriptive names. An implementation might be called "440 times the frequency ratio" to explain its approach.

4. **Write tests first.** Define Z20 testers with known input/output pairs before implementing.

5. **Prefer composition over code.** Compositions are more transparent, reusable, and translatable. Use code only when composition can't express the logic (e.g., parsing strings, complex algorithms).

## How to represent literal values

### Integer literal (e.g., 12)
```json
{
  "Z1K1": "Z16683",
  "Z16683K1": {"Z1K1": "Z16659", "Z16659K1": "Z16660"},  // positive sign (Z16661 neutral, Z16662 negative)
  "Z16683K2": {"Z1K1": "Z13518", "Z13518K1": "12"}        // absolute value
}
```

### Float64 literal (e.g., 440.0)
Float64 uses IEEE 754 representation with sign, exponent, significand, and special-value indicator. These are complex — use `wikifunctions_fetch.py --zid <known_constant> --raw` to see how existing constants are encoded, or use `integer_to_float64` (Z20937) in composition to convert from Integer.

### String literal
```json
{"Z1K1": "Z6", "Z6K1": "A"}
```
Or simply `"A"` in canonical form.
