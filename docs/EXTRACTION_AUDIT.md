# Agent 1 Extraction Audit

## Current Status: ~60% Complete

Extraction logic is partially implemented. Below is a detailed breakdown of what's working, what's missing, and what needs improvement.

---

## ✅ WORKING (WELL-TESTED)

### 1. **Email Extraction**
- **Status**: ✅ High confidence
- **Logic**: Regex pattern `EMAIL_RE`
- **Coverage**: Works across all formats (PDF, DOCX, TXT)
- **Evidence**: Properly tracked with source and locator
- **Tests**: `test_text_parse.py`, `test_docx_parse.py`
- **Notes**: Handles both spaced and non-spaced PDFs

### 2. **Phone Extraction**
- **Status**: ✅ High confidence
- **Logic**: Regex pattern `PHONE_RE`
- **Supported formats**: `503.804.0032`, `(555) 123-4567`, `+1-555-123-4567`
- **Evidence**: Properly tracked
- **Tests**: `test_pdf_resume_anchor.py`
- **Notes**: Handles US phone numbers; international not tested

### 3. **Full Name Extraction**
- **Status**: ✅ High confidence
- **Logic**: Multi-strategy approach:
  1. Window search (1-3 lines above email)
  2. Top 10 lines fallback
  3. Glued-line extraction from header
- **Title casing**: Converts ALL-CAPS to Title Case automatically
- **Evidence**: Properly tracked
- **Tests**: `test_pdf_resume_anchor.py`
- **Notes**: Prevents false positives by:
  - Filtering header lines
  - Requiring 2+ words
  - Max 60 characters
  - Checking against blacklist (EXPERIENCE, EDUCATION, etc.)

### 4. **Location Extraction**
- **Status**: ✅ High confidence (recently fixed)
- **Logic**: Pattern matching with two strategies:
  - Full line match: `^[A-Za-z .'-]+,\s*[A-Za-z]{2,}$`
  - Inline match: `\b[A-Za-z .'-]+,\s*[A-Za-z]{2,}\b`
- **Formatting**: Proper spacing applied (`_format_location`)
- **Recent fix**: Handles PDF extraction removing spaces (e.g., "SanDiego,California" → "San Diego, California")
- **Evidence**: Properly tracked and formatted
- **Tests**: `test_pdf_resume_anchor.py`
- **Notes**: Limited to "City, State/Country" pattern; multi-line addresses not supported

### 5. **URL/Link Extraction**
- **Status**: ⚠️ Partially working
- **Logic**: Three regex patterns:
  - LinkedIn URLs: `LINKEDIN_RE`
  - GitHub URLs: `GITHUB_RE`
  - Generic HTTP(S) URLs: `URL_RE`
- **Coverage**: All three formats detected
- **Evidence**: Tracked per URL found
- **Tests**: `test_text_parse.py` includes GitHub URL test
- **Issues**:
  - Only extracts from lines where patterns are found
  - No domain normalization (e.g., `linkedin.com/in/jane` vs `linkedin.com/company/jane`)
  - No URL validation beyond regex

---

## ⚠️ PARTIAL/WORKING BUT NEEDS IMPROVEMENT

### 6. **Skills Extraction**
- **Status**: ⚠️ Conservative (very limited)
- **Logic**: Only extracts from lines with explicit "Skills:" header
  ```regex
  ^\s*(technical\s+)?skills\s*:?\s*
  ```
- **Parsing**: Comma-separated list parsing
- **Evidence**: Tracked per line (not per skill)
- **Tests**: `test_text_parse.py` includes basic test
- **Issues**:
  - ❌ **Does not detect standalone skill sections** (many resumes have "Skills" as a section header with bullets below)
  - ❌ **Does not extract bullet-point skills** (only inline comma-separated)
  - ❌ **No skill deduplication across multiple lines**
  - ❌ **No skill validation** (random words can be extracted as skills)
  - ❌ **No skill categorization** (Technical, Soft, Languages all mixed)
  - ⚠️ **Limited to exact phrase match** - doesn't handle variations like "Competencies:", "Proficiencies:", "Technical Stack:"

**Example of what's NOT extracted:**
```
Skills
Python
JavaScript
SQL
React
```

---

## ❌ NOT IMPLEMENTED

### 7. **Experience/Work History Extraction**
- **Status**: ❌ Not started
- **Schema needed**:
  ```python
  {
    "job_title": str,
    "company": str,
    "location": str,
    "start_date": str (MM/YYYY),
    "end_date": str (MM/YYYY or "Present"),
    "description": str,
    "achievements": List[str]
  }
  ```
- **Complexity**: HIGH
  - Need to detect section headers ("Experience", "Work History", "Employment")
  - Need to parse multi-line entries (title, company, dates, bullets)
  - Need date normalization
  - Need to distinguish between company name, location, and dates
  - Need to handle various date formats
  - Need to group bullets under correct role
- **Estimated effort**: 3-5 hours (depends on test resume variety)
- **Critical for**: Parse quality score (currently doesn't count experiences)

---

## 📊 EXTRACTION QUALITY METRICS

### Parse Quality Score (Current Logic)
```python
found = sum(1 for v in [full_name, email, phone] if v)
if found >= 3: "high"
elif found >= 2: "medium"
else: "low"
```

**Problem**: Doesn't account for:
- Location extraction ✅ (easy to add)
- Skills extraction ⚠️ (should count toward quality)
- Experiences extraction ❌ (should heavily count)

**Recommendation**: Update scoring to:
```python
score = 0
score += 3 if full_name else 0    # name is critical
score += 2 if email else 0         # email is critical
score += 2 if phone else 0         # phone is critical
score += 1 if location else 0      # location helpful
score += 1 if skills else 0        # skills helpful
score += 2 if experiences else 0   # experiences very important

if score >= 7: "high"
elif score >= 4: "medium"
else: "low"
```

---

## 🔴 KNOWN ISSUES & EDGE CASES

### 1. **International Phone Numbers**
- ❌ `PHONE_RE` only handles US format
- Issue: `+44 20 1234 5678` (UK), `+33 1 23 45 67 89` (France) not detected
- Fix needed: Expand regex or use phonenumbers library

### 2. **Date Normalization**
- ❌ No date extraction/normalization implemented
- Issue: Dates appear in many formats:
  - `January 2020 - Present`
  - `01/2020 - 12/2021`
  - `Jan 2020 - Dec 2021`
  - `2020 - 2021`
  - `Winter 2022` (non-standard)
- Need: `_normalize_date()` function

### 3. **Multi-line Locations**
- ❌ Only detects single-line "City, State" format
- Issue: Some resumes show:
  ```
  San Francisco, CA
  (or Remote)
  ```
- Or:
  ```
  San Francisco, California, USA
  ```
- Fix needed: Expand `LOCATION_RE` or use multi-line strategy

### 4. **Links in Email/Phone Lines**
- ⚠️ Links are searched across ALL lines
- Issue: If a URL appears on same line as email, both get extracted (correct) but evidence points to entire line (not precise)
- Improvement: Extract exact match location within line (requires URI-level evidence tracking)

### 5. **Skills Deduplication**
- ⚠️ No deduplication across multiple "Skills:" lines
- Issue: If resume has:
  ```
  Technical Skills: Python, SQL
  Soft Skills: Communication, Leadership
  ```
  Both lines are recorded, but as separate skill instances
- Fix: Normalize and deduplicate in `parse_lines_to_response()`

### 6. **Header Line Blacklist Coverage**
- ⚠️ `HEADER_BLACKLIST` is incomplete
- Missing common headers:
  - "contact information"
  - "core competencies"
  - "technical proficiencies"
  - "professional experience"
  - "work experience"
  - "employment history"
  - "areas of expertise"
  - "competencies"
  - "strengths"
  - "qualifications"

### 7. **PDF Space Removal (FIXED)**
- ✅ Recently fixed with `layout=True` + regex space-adding
- Handles: "SanDiego,California" → "San Diego, California"
- Potential issue: May not work for all PDFs (test with more samples)

---

## 🎯 PRIORITY ROADMAP

### Phase 1: Strengthen Existing Features (1-2 hours)
1. **Expand skills extraction**
   - Detect "Skills" section headers
   - Extract bullet-point skills
   - Deduplicate across multiple skill lines
   
2. **Improve header blacklist**
   - Add missing common headers
   - Make more robust to variations

3. **International phone numbers**
   - Add UK, Canada, Germany, France patterns
   - Or integrate `phonenumbers` library

### Phase 2: Add Date Handling (1-2 hours)
1. Implement `_normalize_date()` function
2. Test against common date formats
3. Flag non-standard dates as warnings

### Phase 3: Experience Extraction (3-5 hours) ⭐ CRITICAL
1. Section header detection
2. Multi-line entry parsing
3. Date extraction & normalization
4. Achievement bullet grouping
5. Comprehensive test suite

### Phase 4: Polish & Optimization (1 hour)
1. Update parse quality scoring
2. Add comprehensive warnings
3. Performance testing with large resumes

---

## 📝 TEST COVERAGE

### Current Tests
- ✅ `test_pdf_resume_anchor.py` - Name, email, phone, location (PDF)
- ✅ `test_docx_parse.py` - Email extraction (DOCX)
- ✅ `test_text_parse.py` - Email, skills, GitHub URL (TXT)
- ✅ `test_health.py` - API health check

### Missing Tests
- ❌ Skills extraction (section header, bullets)
- ❌ Link extraction (all three types: LinkedIn, GitHub, generic)
- ❌ Location extraction edge cases (multi-line, missing state)
- ❌ Date normalization
- ❌ Experience extraction
- ❌ International phone numbers
- ❌ Parse quality scoring
- ❌ Warning generation
- ❌ Evidence accuracy (verify locators point to correct content)

---

## 🚀 QUICK WINS (Next Steps)

1. **Expand skills extraction** (30 min)
   - Add section header detection
   - Extract bullets under "Skills" section
   - Add test case

2. **Fix header blacklist** (15 min)
   - Add 10 more common headers
   - Run existing tests to ensure no regression

3. **Add date normalization stub** (1 hour)
   - Create `_normalize_date()` function
   - Handle 3 most common formats
   - Flag unsupported formats as warnings

4. **Create experience extraction starter** (30 min)
   - Detect "Experience" section header
   - Group consecutive experience entries
   - Add test with dummy data

---

## 💡 Design Notes for Agent 1

From README:
> "Deterministic DOCX/PDF parsing. OCR only when required."

**Current alignment**: ✅ Good
- Using pdfplumber (deterministic)
- Using python-docx (deterministic)
- No OCR yet (good)

**Future consideration**:
- When parse quality is "low" AND OCR could help, flag for optional OCR
- Don't OCR by default (cost inefficient)
