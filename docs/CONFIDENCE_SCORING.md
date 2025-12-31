# Per-Field Confidence Scoring - Implementation Guide

## Overview

**Version 1** of the agent-parser now includes per-field confidence scoring. This allows downstream consumers and future agents to understand **how confident the parser is** about each extracted field, enabling intelligent decisions about:

- When to prompt the candidate for clarification
- Which fields are suitable for automated processing vs. human review
- How to weight extraction results when building a larger system

## What Changed

### 1. **New Data Structures** (`schemas.py`)

#### `FieldConfidence`
Each field now has confidence metadata:

```python
class FieldConfidence(BaseModel):
    field_name: str                      # "email", "full_name", etc.
    confidence: float                    # 0.0 (no confidence) → 1.0 (absolute certainty)
    extraction_method: str               # How it was found (e.g., "regex_exact_single", "not_found")
    reasons: List[str]                   # Why confidence is this value
    required: bool                       # Is this field needed for "high" quality?
```

#### Updated `ParseResponse`
```python
class ParseResponse(BaseModel):
    candidate_profile: CandidateProfile
    evidence_map: Dict[str, List[EvidenceItem]]
    confidence_scores: Dict[str, FieldConfidence]  # NEW: Per-field confidence
    parse_quality: ParseQuality
    warnings: List[str]
```

#### `EvidenceItem` Enhanced
Evidence items now track confidence too:
```python
class EvidenceItem(BaseModel):
    source: Literal["docx", "pdf", "ocr", "user"]
    locator: str
    text: str
    confidence: float = 1.0  # NEW: Confidence in this specific evidence
```

### 2. **Confidence Calculator** (`confidence_calculator.py`)

Centralized logic for confidence calculation across all fields:

- **`email()`** - Confidence based on format validity, found once vs. multiple times
- **`phone()`** - Valid format, occurrence count
- **`full_name()`** - Multivariate: near email, at resume top, passes blacklist, has middle initial
- **`location()`** - Format validity (City, State), extraction context
- **`url()`** - Platform-specific (LinkedIn, GitHub, generic)
- **`skill()`** - Extraction source (inline vs. bullet vs. subheading)
- **`experience_field()`** - Per-field confidence (company, job_title, dates, location)
- **`calculate_overall_parse_quality()`** - Aggregate confidence → quality tier

## Confidence Scale

| Score | Meaning | Example |
|-------|---------|---------|
| **1.0** | Exact match | Email via regex, single occurrence |
| **0.9** | Very high confidence | Valid URL format found |
| **0.85** | High confidence | Phone found via regex, minor variations |
| **0.8** | High | Location with City, State format |
| **0.75** | Medium-high | Heuristic with good signals |
| **0.6** | Medium | Ambiguous but extractable |
| **0.5** | Low-medium | Multiple signals, uncertainty |
| **<0.5** | Low | Should prompt for clarification |
| **0.0** | Not found | Field missing entirely |

## Response Example

### Input Resume
```
JOHN SMITH
john.smith@techcorp.com
415-555-1234
San Francisco, California

Skills: Python, JavaScript, AWS
```

### Response with Confidence Scores
```json
{
  "candidate_profile": {
    "full_name": "John Smith",
    "email": "john.smith@techcorp.com",
    "phone": "415-555-1234",
    "location": "San Francisco, California",
    "skills": ["Python", "JavaScript", "AWS"]
  },
  "confidence_scores": {
    "full_name": {
      "field_name": "full_name",
      "confidence": 0.85,
      "extraction_method": "heuristic_window",
      "reasons": [
        "Extracted from resume header area",
        "Near email: true",
        "At top: true"
      ],
      "required": true
    },
    "email": {
      "field_name": "email",
      "confidence": 1.0,
      "extraction_method": "regex_exact_single",
      "reasons": ["Found via regex extraction"],
      "required": true
    },
    "phone": {
      "field_name": "phone",
      "confidence": 1.0,
      "extraction_method": "regex_exact_single",
      "reasons": ["Found via regex extraction"],
      "required": true
    },
    "location": {
      "field_name": "location",
      "confidence": 0.95,
      "extraction_method": "regex_pattern",
      "reasons": ["Extracted from geographic pattern"],
      "required": false
    },
    "skills": {
      "field_name": "skills",
      "confidence": 0.85,
      "extraction_method": "section_extraction",
      "reasons": ["Found 3 skills"],
      "required": false
    }
  },
  "parse_quality": "high",
  "warnings": []
}
```

## How Parse Quality is Calculated

Parse quality now uses **confidence-informed logic**:

```python
def calculate_overall_parse_quality(field_confidences):
    """
    Core fields: name, email, phone
    
    "high"   : avg confidence of core fields >= 0.85
    "medium" : avg confidence of core fields >= 0.65
    "low"    : otherwise
    """
```

**Example:**
- Name (0.85) + Email (1.0) + Phone (1.0) = avg **0.95** → **HIGH**
- Name (0.0) + Email (1.0) + Phone (1.0) = avg **0.67** → **MEDIUM**
- Name (0.0) + Email (0.0) + Phone (1.0) = avg **0.33** → **LOW**

## When to Prompt for Clarification

Use confidence scores to decide:

```python
# Example: downstream dialog logic
for field, confidence_obj in confidence_scores.items():
    if confidence_obj.required and confidence_obj.confidence < 0.8:
        if not extracted_value:
            # Missing required field
            prompt_user(f"Please provide your {field}")
        else:
            # Low-confidence extraction
            if confidence_obj.confidence < 0.5:
                confirm_user(f"You have {field}: {extracted_value}. Is this correct?")
```

## Future Extensibility

The confidence calculator is designed for easy extension:

### Adding a New Field
1. Add a static method to `ConfidenceCalculator` class
2. Call it from `parse_lines_to_response()` in the appropriate section
3. Add the result to `confidence_scores` dict
4. Write tests in `test_confidence_scoring.py`

### Example: Adding Certifications
```python
# In confidence_calculator.py
@staticmethod
def certification(cert_name: str, issuer: str = None) -> Tuple[float, str]:
    """Calculate confidence for certification extraction."""
    if not cert_name:
        return 0.0, "not_found"
    
    confidence = 0.85
    if issuer:  # More confident if issuer is present
        confidence = 0.95
    
    return confidence, "certification_extracted"
```

## Implementation Details

### Files Modified/Created

| File | Change |
|------|--------|
| `app/core/schemas.py` | Added `FieldConfidence`, updated `EvidenceItem` and `ParseResponse` |
| `app/core/confidence_calculator.py` | **NEW**: Centralized confidence logic |
| `app/core/line_parser.py` | Integrated confidence scoring into parsing pipeline |
| `tests/test_confidence_scoring.py` | **NEW**: 10 tests demonstrating confidence scoring |

### Backward Compatibility

✅ **Fully backward compatible**. All existing tests pass. The new `confidence_scores` field is additive; consumers can ignore it if not needed.

## Testing

Run confidence scoring tests:
```bash
pytest tests/test_confidence_scoring.py -v
```

All 35 tests pass (10 new + 25 existing).

## Next Steps (v2+)

1. **Format Detection**: Analyze resume structure once per resume, store format fingerprint in response
2. **Enhanced Experience Confidence**: Track confidence per job field (company, title, dates, location)
3. **Education/Certifications**: Add parsing + confidence scoring
4. **Learning Loop**: Store extraction + ground truth, compute accuracy metrics
5. **Name Corpus Validation**: Build whitelist of known names, improve name confidence
6. **Language Support**: v1 is English-only; v2 can extend to multi-language with confidence penalties

## FAQ

**Q: Why does my email have confidence < 1.0?**
A: If regex found the email but multiple candidates exist (unlikely but possible in glued text), confidence is lower to signal ambiguity.

**Q: What if I don't care about confidence?**
A: You don't have to use it! Existing code sees the same `candidate_profile`, `evidence_map`, and `parse_quality` fields.

**Q: How do I know if a field is "good enough"?**
A: Use the `required` flag and your threshold. Core fields (name, email, phone) are marked `required: true`. Consider < 0.7 as "needs clarification."

**Q: Can I improve confidence for a field?**
A: Not directly, but you can help by ensuring your resume is well-formatted. Confidence algorithms expect standard patterns (email before phone, location with comma, etc.).
