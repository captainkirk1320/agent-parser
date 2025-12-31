# Copilot Instructions for agent-parser

## Project Overview

**agent-parser** is a deterministic resume parsing service (FastAPI) that extracts candidate information from DOCX/PDF/TXT resumes and returns structured data with evidence tracking. It emphasizes accuracy over completeness—only extracting fields when highly confident.

**Key principle**: No hallucinations. All extracted data must be backed by exact source text evidence.

## Architecture & Data Flow

### Core Parsing Pipeline
1. **File Format Detection** ([parse.py](app/api/routes/parse.py#L18-L35)): Routes to appropriate extractor based on file extension/MIME type
2. **Format-Specific Extraction**: DOCX → paragraphs, PDF → layout-based text, TXT → raw lines
3. **Normalization** ([line_parser.py](app/core/line_parser.py#L1-70)): Fix PDF spacing issues (`_despace_if_needed`, `_normalize_for_search`)
4. **Candidate Profile Extraction**: Parse extracted lines into `CandidateProfile` via regex patterns or heuristics
5. **Evidence Mapping**: Track every extracted field's source line/page and original text

### Key Components
- **[schemas.py](app/core/schemas.py)**: `CandidateProfile` + `EvidenceItem` models. All responses wrap extracted data in `ParseResponse` with evidence_map and parse_quality
- **[text_parser.py](app/core/text_parser.py)**: Simple regex extraction for plain text (email, phone, URLs, name heuristics)
- **[line_parser.py](app/core/line_parser.py)**: Complex logic for PDF/DOCX-extracted lines—handles spacing, case normalization, location formatting
- **[docx_extractor.py](app/core/docx_extractor.py)**: Deterministic paragraph extraction; no formatting loss
- **[pdf_extractor.py](app/core/pdf_extractor.py)**: Layout-based extraction via `pdfplumber`, applies regex fixes for common extraction artifacts

## Extraction Patterns & Conventions

### Working Extractions (High Confidence)
- **Email/Phone**: Regex-based. Email RE: `\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b`
- **Full Name**: Multi-strategy (window around email, top-10-line heuristic). Name must contain space + <60 chars, passes blacklist check against section headers
- **Location**: Pattern `City, State/Country` with spacing normalization. Handles glued PDF text (NewYork → New York)
- **URLs/Links**: Three regex patterns (LinkedIn, GitHub, generic HTTP). Tracked per URL found
- **Work Experience**: Multi-format extraction including company name, job title, location, employment dates, and achievement bullets

#### Work Experience Details (Phase 2 - Completed)
The experience extraction system ([line_parser.py](app/core/line_parser.py#L273-L480)) supports:
1. **Entry Detection & Grouping** ([_group_experience_entries](app/core/line_parser.py#L315-L364)):
   - Detects experience section headers (EXPERIENCE, Career Experience, Work History, etc.)
   - Groups multi-line entries intelligently, handling PDF glued text and spacing issues
   - Single-line format: `Company: Title: Location` (e.g., `ACME CORP: TERRITORY MANAGER: NEW YORK`)
   - Multi-line format: Company on line 1, title/location/dates on line 2, achievements on following lines
   - **Key fix**: Distinguishes location-only lines from location+dates lines (continuation vs. new entry)

2. **Date Range Extraction** ([_extract_date_range](app/core/line_parser.py#L195-L210)):
   - Flexible pattern matching: `January 2024-Present`, `01/2024 - 12/2025`, `2020 - 2021`, etc.
   - Parses start_date and end_date separately
   - Handles "Present" and "Current" as end date indicators

3. **Location Extraction** ([_extract_location_from_line](app/core/line_parser.py#L118-L170)):
   - Smart "City, State/Country" pattern detection
   - Handles dates/other text on same line (scans right-to-left for location pattern)
   - Corrects PDF glued text: `NewYork` → `New York, New York`
   - Uses reverse-comma scanning to extract last valid City, State pair

4. **Field Preservation**:
   - Single-line format fields (company, title, location) are preserved and not overwritten by continuation lines
   - Multi-line location from proper formatting (e.g., "New York, New York") overrides abbreviated single-line location
   - Job title from line 2 only extracted if not already populated from line 1

5. **Achievement Collection**:
   - Bullet-point detection via regex (●, -, *, etc.)
   - Filters out extremely short (<10 chars) and extremely long (>500 chars) lines
   - Preserves original text in evidence tracking

**Test Coverage**: All 6 experience tests passing (test_experience_extraction.py)
- PDF resume with 3+ jobs (glued text handling)
- DOCX resume with 5+ jobs (multi-level structure)
- Inline single-line format
- Multi-line format with dates and achievements
- Resumes with missing dates
- Parse quality scoring includes experience field

### Partial/Known Gaps
- **Skills Extraction**: Currently only inline "Skills: X, Y, Z" format. **Missing**: Standalone skill sections (headers with bullet points below), skill deduplication, validation, categorization
- **Education**: Not implemented
- **Certifications**: Not implemented

### Evidence Tracking Convention
Every extracted field maps to a list of `EvidenceItem` objects:
```python
EvidenceItem(
    source="pdf|docx|text",  # Format source
    locator="pdf:page:1:line:3" | "docx:paragraph:5" | "text:line:7",  # Exact position
    text="<exact snippet from resume>"  # Original source text
)
```

## PDF-Specific Quirks

PDFs often extract with artifacts:
- **Spaced characters**: `E X P E R I E N C E` → `EXPERIENCE` (fixed by `_despace_if_needed`)
- **Glued text**: `NewYork,NewYork` → `New York, New York` (fixed by `_add_spaces_to_text` in pdf_extractor + `_normalize_for_search`)
- **No OCR**: Current implementation only handles text-layer extraction; scanned PDFs will fail (acceptable for phase 1)

Use [layout=True](app/core/pdf_extractor.py#L28) in pdfplumber to preserve space structure between elements.

## Development Workflow

### Running Tests
```bash
pytest                  # All tests
pytest tests/test_text_parse.py  # Specific test file
pytest -v              # Verbose output
```
Config: [pytest.ini](pytest.ini) with pythonpath = .

### Testing New Extractors
1. Add test cases in [tests/](tests/) using `TestClient(app)` from FastAPI
2. Use fixture resume in [tests/fixtures/](tests/fixtures/) or inline bytes
3. Assert on `response.json()["candidate_profile"][field]` and `response.json()["evidence_map"][field]`
4. Example: [test_text_parse.py#L5-L23](tests/test_text_parse.py#L5-L23) — shows expected response structure

### Adding New Extraction Logic
1. **For simple regex patterns**: Add to [text_parser.py](app/core/text_parser.py), create helper like `_find_emails()`
2. **For complex heuristics (PDF artifacts, multi-line parsing)**: Add to [line_parser.py](app/core/line_parser.py)
3. **Always return evidence**: Use `_add_evidence(evidence_map, key, source, locator, text)` helper
4. **Test deterministically**: Use exact resume text + assertions on extracted values + evidence presence

## Code Style & Patterns

- **Type hints**: Required on function signatures (Pydantic models use Optional generously)
- **Normalization for search, preserve for evidence**: `_normalize_for_search()` is used only for detection; original text stored in EvidenceItem
- **Defensive regexes**: Use `re.IGNORECASE`, handle variations (e.g., phone with/without parentheses)
- **Locators must be meaningful**: `"text:line:5"`, `"pdf:page:2:line:10"`, `"docx:paragraph:7"` — consumers parse these
- **Header blacklist**: [line_parser.py#L76+](app/core/line_parser.py#L76) prevents false positives (EXPERIENCE, SKILLS, etc. are not names)

## Common Pitfalls

1. **Extracting without evidence**: ❌ Never. Always trace back to source lines.
2. **Assuming PDF text is clean**: ❌ Apply `_normalize_for_search()` before matching, but preserve original in evidence.
3. **Missing edge cases in regex**: ❌ Test against [test fixtures](tests/fixtures/) and `test_pdf_resume_anchor.py` PDF
4. **Forgetting parse_quality**: Return `high|medium|low` in `ParseResponse`. High = all major fields found cleanly.
5. **Not handling multi-format input**: Test with TXT, DOCX, and PDF in same test suite.

## Next Priority (From EXTRACTION_AUDIT.md)

- **Education**: School, degree, graduation year
- **Certifications**: Cert name + issuer

✅ **Completed**: Skills extraction, Work experience extraction

See [docs/EXTRACTION_AUDIT.md](docs/EXTRACTION_AUDIT.md) for detailed status of each field.
