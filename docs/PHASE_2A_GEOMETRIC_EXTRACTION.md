# Phase 2a: Geometric-First PDF Extraction

## Overview

This document describes the new **geometric-first** extraction approach (Phase 2a), which addresses the fundamental issue with linguistic-first parsing: relying on pre-extracted text that's already been mangled by the PDF library.

## The Problem with Linguistic-First

The current approach (Phase 1) works like this:
1. PDF library extracts text (black box)
2. We try to "fix" concatenated words using linguistic heuristics
3. Result: Brittle, requires large word dictionaries, doesn't scale

Example failure case:
```
PDF extracts: "Wonseveralteamandnationalblitzesduetoterritoryexpansionandcloserelationshipswithmajorkeyaccountinthe"
Dictionary tries: Split on known words, but runs out of coverage
Output: Still wrong
```

## The Solution: Geometric-First

Instead of trying to fix broken text, extract it correctly from the start using **character-level geometry**:

```
┌─────────────────────────────────────────────────────────┐
│ Phase A: Extract characters with positions/fonts        │
│ W(0,0) o(5,0) n(10,0) [gap>3pt] s(20,0) ...             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ Phase B: Detect word boundaries using geometry          │
│ Gap > 0.35×fontsize → new word                          │
│ Result: "Won" | "several" | "team" | ...                │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ Phase C: Group words into lines/blocks                  │
│ (Respects column layout, prevents mashups)              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ Phase D: Apply linguistic repair ONLY if needed         │
│ (Quality signal: if dict_coverage < 60%, run repair)    │
└─────────────────────────────────────────────────────────┘
```

## Key Files

- **[app/core/pdf_character_extractor.py](../app/core/pdf_character_extractor.py)** - Character-level extraction & word reconstruction using geometry
- **[app/core/pdf_hybrid_extractor.py](../app/core/pdf_hybrid_extractor.py)** - Hybrid approach (geometric + optional linguistic repair)
- **[tests/test_pdf_character_extraction.py](../tests/test_pdf_character_extraction.py)** - Test suite & comparison

## How It Works

### Phase A: Character Extraction

```python
from app.core.pdf_character_extractor import extract_characters_with_geometry

characters = extract_characters_with_geometry("resume.pdf")
# Returns: List[PDFCharacter] with x0, y0, fontname, size, etc.
```

Each character includes:
- Position (x0, y0, x1, y1) in PDF units
- Font name and size (allows font-aware thresholds)
- Page number (for multi-page PDFs)

### Phase B: Geometric Word Boundary Detection

**Core Rule**: `gap > 0.35 × font_size → new word`

```python
from app.core.pdf_character_extractor import reconstruct_words_from_chars

words = reconstruct_words_from_chars(characters)
# Returns: List[PDFWord] with geometric boundaries
```

Example:
```
Font size: 10pt
Threshold: 0.35 × 10 = 3.5pt

Character positions:
  W(0)  o(4)  n(8) [gap=12pt] s(20) e(24) v(28) e(32) r(36) a(40) l(44)
                    ↑ > 3.5pt, new word

Result: "Won" | "several"
```

**Also detects**:
- Font changes (e.g., bold title followed by regular text)
- Size changes (e.g., footnote vs. body text)

### Phase C: Line & Block Reconstruction

```python
from app.core.pdf_character_extractor import reconstruct_lines_from_words

lines = reconstruct_lines_from_words(words)
# Returns: List[PDFLine] with words grouped by y-position
```

Groups words into lines using y-clustering (tolerance: 2-3 PDF units per font size).

### Phase D: Quality-Driven Repair

```python
from app.core.pdf_hybrid_extractor import extract_pdf_hybrid

result = extract_pdf_hybrid("resume.pdf", quality_threshold=0.6)
```

Quality metrics:
- **dict_coverage**: % of words in COMMON_WORDS dictionary (target: >60%)
- **suspicious_ratio**: % of words with red flags (target: <15%)
- **no_vowel_ratio**: % of words with no vowels (target: <10%)
- **quality_score**: 0-1 composite score (target: >0.65)

If quality is below threshold, applies `_segment_concatenated_words()` to suspicious tokens only.

## Advantages Over Phase 1

| Aspect | Phase 1 (Linguistic-first) | Phase 2a (Geometric-first) |
|--------|---------------------------|----------------------------|
| **Root cause** | Tries to fix broken text | Prevents breakage from start |
| **Scalability** | Degrades with unusual fonts | Font-aware, scales |
| **Explainability** | "Dictionary says this word is valid" | "Gap was 3.5pt, threshold 3pt" |
| **Edge cases** | Requires new heuristics per case | Handles uniformly geometrically |
| **Word dictionary** | Must be comprehensive (200+ words) | Only needed as fallback |
| **Spelling errors** | Treated as parsing failures | Handled by repair layer (not parsing) |

## Test Results

### Anna Ford Resume (2024)

**Geometric extraction (Phase B only):**
```
Total words: 68
Dict coverage: 0%
Quality score: 0.18
Needs repair: True
```

**With linguistic repair (Phase D):**
```
Repair applied: True
Sample fixes:
  "ANNAFORD" → "ANNAFORD" (no change, correct)
  "SanDiego,California" → "San Diego,California" (camelCase split)
  "Iamaselfmotivated..." → "I am a self motivated..." (split long word)
```

## Configuration & Tuning

### Gap Threshold

Currently: `gap_threshold_ratio = 0.35`

Tuning:
- **Lower value (0.2)**: More aggressive splitting (catches smaller gaps)
- **Higher value (0.4)**: Less aggressive (may miss some breaks)

Recommendation: Keep at 0.35; adjust via `gap_threshold_ratio` parameter if needed.

### Quality Threshold

Currently: `quality_threshold = 0.6`

Usage in hybrid mode:
- If `quality_score < 0.6`, apply linguistic repair
- Tuning: Lower = more conservative (repair more often), Higher = more permissive

### Suspicious Word Detection

Current rules in `_should_repair_word()`:
- Length > 15 chars
- No vowels (in words > 3 chars)
- All uppercase (in words > 5 chars)
- Mixed numbers + letters without separators

Modify these rules to tune repair behavior.

## Future Improvements

### Phase 2b: Smart Repair Targeting

Instead of repairing all suspicious words, use ML/heuristics to prioritize:
- Repair achievement bullets first (high value)
- Skip company names (lower value)
- Use context (e.g., "industry-specific terms" dictionary)

### Phase 2c: Multi-Column Handling

Current line grouping assumes single column. Enhance to:
- Detect multi-column layouts
- Preserve column reading order
- Handle side-by-side content (e.g., skills + languages)

### Phase 3: Full Deterministic Parsing

Once geometric extraction is stable, rebuild experience/education/skills parsing to use:
- Geometric boundaries (actual positions, not heuristics)
- Quality scores throughout (confidence propagation)
- Measurable accuracy metrics

## Comparison with Current System

To compare geometric-first vs. current linguistic-first:

```python
from app.core.pdf_hybrid_extractor import compare_approaches

result = compare_approaches("resume.pdf")
# Prints detailed comparison + sample lines
```

## Integration Plan

**Current status**: Parallel implementation (both systems coexist)

**Phase 2b** (next sprint):
1. Validate geometric extraction on 100+ real resumes
2. Measure quality scores and dict coverage
3. Fine-tune gap thresholds and repair rules
4. Measure accuracy vs. Phase 1 (if ground truth available)

**Phase 2c** (after validation):
1. Update experience/education parsers to use geometric data
2. Gradually migrate extraction pipeline to geometric-first
3. Deprecate linguistic-first approach
4. Update evidence tracking (include geometric metadata)

## Testing

Run geometric extraction tests:
```bash
pytest tests/test_pdf_character_extraction.py -v
```

Run comparison on real PDFs:
```bash
python -c "from app.core.pdf_hybrid_extractor import compare_approaches; compare_approaches('tests/fixtures/Anna Ford Resume 2024  final.pdf')"
```

## References

- **pdfplumber documentation**: https://github.com/jsvine/pdfplumber
- **PDF coordinate system**: PDFs use points (1/72 inch), coordinates from bottom-left
- **Font metrics**: Each character has precise bounding box; pdfplumber provides this
