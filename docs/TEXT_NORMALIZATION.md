# Text Normalization Implementation

## Overview

Created a new module `app/core/text_normalization.py` that provides targeted, pragmatic glue-word fixing for resume text extracted from PDFs.

## Architecture

**Two-level approach:**

1. **normalize_token_basic()** - Ultra-conservative, safe everywhere
   - Special cases: `inanew`, `anew`, `startanew`, `leadingto`, `dueto`
   - Suffix phrases: `salesinthe`, `repsinthe`, `girlsofthe`, `toolstobe`

2. **normalize_bullet_text()** - Rich pipeline for achievement/bullet text
   - Applies basic normalization first
   - Then tries (per token, in order):
     - Suffix phrases
     - Prefix phrases (e.g., `duetoa 150%` → `due to a 150%`)
     - Embedded joiners (e.g., `territorytoover` → `territory to over`)
     - CamelCase boundaries (e.g., `SymposiuminMiami` → `Symposium in Miami`)
   - Re-runs suffix phrases after complex splits (catches patterns exposed by earlier passes)

## Examples Covered

**Basic normalization:**
- `inanew` → `in a new`
- `anew` → `a new`
- `startanew` → `start a new`
- `salesinthe` → `sales in the`
- `repsinthe` → `reps in the`

**Rich pipeline (bullet text):**
- `duetoa 150% growth` → `due to a 150% growth`
- `leadingto expansion` → `leading to expansion`
- `territorytoover $2M` → `territory to over $2M`
- `countrytoattend conference` → `country to attend conference`
- `SymposiuminMiami` → `Symposium in Miami`
- `growthinQ1` → `growth in Q 1`

**Safety features:**
- Hard veto for embedded short joiners (prevents `terri|to|ry` from `territory`)
- Word-shape validation (must have vowels, no 5+ consonant clusters)
- No recursion - single pass per token

## Test Coverage

- 10 basic normalization tests (all passing)
- 12 bullet text normalization tests (all passing)
- All 42 original tests still pass (no regressions)

**Total: 64 tests passing**

## Integration Points (Ready for Implementation)

The module is ready to be integrated into:

1. **pdf_extractor.py** - Call `normalize_token_basic()` in `_deglue_joiners()`
2. **line_parser.py** - Call `normalize_bullet_text()` on achievement/bullet lines before extracting bullets

See the concrete implementation plan in the issue/PR for wiring this into the extraction pipeline.

## Files Modified

- **Created:** `app/core/text_normalization.py` (305 lines)
- **Created:** `tests/test_text_normalization.py` (142 lines)
- **No changes to existing code** (backward compatible)

## Next Steps

1. Integrate `normalize_bullet_text()` call into `line_parser.py` when extracting achievements
2. Test in Swagger with real PDFs
3. Monitor for edge cases and adjust prefix/suffix phrase lists as needed

## Design Notes

**Why this approach vs generic segmentation:**

- Resume text gluing patterns are predictable and limited (20 common cases)
- Hardcoding explicit patterns beats trying to be "general"
- Avoids over-segmentation (the main failure mode of generic algorithms)
- Token-local operations eliminate adjacency dependencies
- Single-pass prevents reintroducing the problems we're fixing
