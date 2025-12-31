"""
Education parsing module for detecting and extracting education entries from resumes.

Provides deterministic, rule-based classification and parsing of education blocks,
distinguishing them from work experience through section detection and keyword patterns.
"""

import re
from typing import Dict, List, Tuple, Optional, Literal
from app.core.schemas import EducationEntry, EvidenceItem
from app.core.text_normalization import normalize_field_text


def normalize_pdf_wordbreaks(s: str) -> str:
    """
    Fix mid-word breaks in PDF-extracted text.
    
    CONSERVATIVE approach: Only removes breaks that look like PDF artifacts:
    - Multiple spaces between letters (e.g., "communicati  on" with 2+ spaces)
    - Single space between lowercase letters in middle of word (e.g., "communicati on")
    
    Does NOT remove single spaces between uppercase letters or in normal words.
    
    Examples:
        "communicati on" -> "communication"
        "journ a lism" -> "journalism"
        "Bachelor of Science" -> "Bachelor of Science" (unchanged)
        "Spring Trimester" -> "Spring Trimester" (unchanged)
    
    Args:
        s: Text with potential mid-word breaks
    
    Returns:
        Text with only PDF artifact breaks removed
    """
    if not s:
        return s
    # Only remove spaces in CLEAR artifact patterns:
    # 1) Multiple spaces between letters (obvious artifact)
    s = re.sub(r"(?<=[A-Za-z])\s{2,}(?=[A-Za-z])", "", s)
    # 2) Single space between lowercase letters only (very likely mid-word break)
    #    This avoids removing spaces in proper word boundaries
    s = re.sub(r"(?<=[a-z])\s(?=[a-z])", "", s)
    return s


# ===== SECTION DETECTION KEYWORDS =====

EDUCATION_SECTION_HEADERS = {
    "education",
    "academic background",
    "education & training",
    "academic",
    "schooling",
    "academic experience",
}

EXPERIENCE_SECTION_HEADERS = {
    "experience",
    "professional experience",
    "work experience",
    "employment",
    "work history",
    "career",
    "career experience",
    "career experience & achievements",
    "career experience and achievements",
}

# ===== DEGREE KEYWORDS (Strong Signal) =====
# If a line contains ANY of these, it MUST be classified as education

DEGREE_KEYWORDS = {
    "bachelor of",
    "bachelor's",
    "master of",
    "master's",
    "associate of",
    "associate's",
    "b.s.",
    "b.a.",
    "m.s.",
    "m.a.",
    "m.b.a.",
    "ph.d.",
    "phd",
    "doctorate",
    "doctoral",
    "graduate degree",
    "postgraduate",
    "diploma",
    "certificate",
    "b.s. in",
    "b.a. in",
    "m.s. in",
    "m.a. in",
}

# ===== INSTITUTION KEYWORDS =====
# If institution matches these + we're in education section, map to institution not company

INSTITUTION_KEYWORDS = {
    "university",
    "college",
    "institute",
    "institute of",
    "school",
    "academy",
    "high school",
    "secondary school",
    "prep school",
    "polytechnic",
    "state university",
    "community college",
    "trade school",
}

# ===== SPECIAL KEYWORDS =====
# High school detection

HIGH_SCHOOL_KEYWORDS = {
    "high school",
    "secondary school",
    "prep school",
    "preparatory",
}

STUDY_ABROAD_KEYWORDS = {
    "study abroad",
    "institute of study abroad",
    "dis study abroad",
    "semester abroad",
    "year abroad",
}

# ===== KNOWN STUDY ABROAD PROGRAM ABBREVIATIONS =====
# Maps abbreviations to full program names
STUDY_ABROAD_ABBREVIATIONS = {
    "dis": "Danish Institute of Study Abroad",
    "isa": "Institute for Study Abroad",
    "aifs": "American Institute for Foreign Study",
    "ciee": "Council on International Educational Exchange",
    "saf": "Study Abroad Foundation",
}

# ===== EDUCATION-SPECIFIC BULLET KEYWORDS =====

EDUCATION_DETAIL_KEYWORDS = {
    "major:",
    "minor:",
    "focus in",
    "concentration",
    "focus:",
    "honors:",
    "dean's list",
    "cum laude",
    "magna cum laude",
    "summa cum laude",
    "gpa:",
    "scholarship",
    "award:",
    "relevant coursework",
    "coursework:",
}


def detect_section_type(line: str) -> Optional[Literal["education", "experience"]]:
    """
    Detect if a line is a section header and return the section type.
    
    Args:
        line: Text to check (typically a header line)
    
    Returns:
        "education", "experience", or None if not a section header
    """
    normalized = line.strip()
    # CRITICAL: Fix PDF wordbreaks (e.g., "educati on" -> "education") BEFORE matching
    normalized = normalize_pdf_wordbreaks(normalized)
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    
    # Check education headers
    if normalized in EDUCATION_SECTION_HEADERS:
        return "education"
    
    # Check experience headers
    if normalized in EXPERIENCE_SECTION_HEADERS:
        return "experience"
    
    return None


def has_degree_keyword(text: str) -> bool:
    """
    Check if text contains degree keywords.
    This is a STRONG signal that an entry is education, not experience.
    
    Args:
        text: Text to check
    
    Returns:
        True if degree keyword found (case-insensitive)
    """
    text_lower = text.lower()
    
    for keyword in DEGREE_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def is_high_school(text: str) -> bool:
    """
    Check if text refers to high school.
    High school ALWAYS maps to education, never experience.
    
    Args:
        text: Text to check
    
    Returns:
        True if high school detected
    """
    text_lower = text.lower()
    
    for keyword in HIGH_SCHOOL_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def is_institution_keyword(text: str) -> bool:
    """
    Check if text contains institution-specific keywords.
    When combined with education section context, this indicates
    an educational institution, not a company.
    
    Args:
        text: Text to check
    
    Returns:
        True if institution keyword found
    """
    text_lower = text.lower()
    
    for keyword in INSTITUTION_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def is_study_abroad(text: str) -> bool:
    """
    Check if text refers to study abroad program.
    Study abroad is still education, not experience.
    
    Args:
        text: Text to check
    
    Returns:
        True if study abroad detected
    """
    text_lower = text.lower()
    
    for keyword in STUDY_ABROAD_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def is_education_detail_bullet(text: str) -> bool:
    """
    Check if a bullet point is an education detail (major, minor, etc.)
    rather than a work achievement.
    
    Args:
        text: Bullet text to check
    
    Returns:
        True if this is an education detail bullet
    """
    text_lower = text.lower()
    
    for keyword in EDUCATION_DETAIL_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def extract_degree_from_text(text: str) -> Optional[str]:
    """
    Extract degree name from text.
    
    Examples:
        "Bachelor of Science in Computer Science" -> "Bachelor of Science"
        "M.S. in Engineering" -> "M.S."
        "PhD" -> "PhD"
    
    Args:
        text: Text containing degree information
    
    Returns:
        Extracted degree or None
    """
    # Normalize word breaks first to handle PDF artifacts
    text = normalize_pdf_wordbreaks(text)
    text_lower = text.lower()
    
    # Longer degree names first (longer match wins)
    degree_patterns = [
        r"(bachelor of science|bachelor's degree|master of science|master's degree|associate of|bachelor of arts|master of arts|doctor of philosophy)",
        r"(b\.s\.(?:\s+in)?|b\.a\.(?:\s+in)?|m\.s\.(?:\s+in)?|m\.a\.(?:\s+in)?|m\.b\.a\.(?:\s+in)?|ph\.d\.(?:\s+in)?)",
        r"(bachelor|master|associate|doctorate|doctoral|phd|graduate degree|postgraduate degree)",
    ]
    
    for pattern in degree_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # Get the matched degree text from original (preserve casing where possible)
            start = match.start()
            end = match.end()
            return text[start:end].strip()
    
    return None


def extract_field_of_study_from_degree_line(text: str) -> Optional[str]:
    """
    Extract field of study from a degree line.
    
    Examples:
        "Bachelor of Science in Computer Science" -> "Computer Science"
        "M.S. Engineering" -> "Engineering"
        "Degree in Business Administration" -> "Business Administration"
    
    Args:
        text: Text containing degree and field information
    
    Returns:
        Extracted field of study or None
    """
    # Normalize word breaks first to handle PDF artifacts
    text = normalize_pdf_wordbreaks(text)
    
    # Look for "in <field>" pattern, but stop at common delimiters like commas
    # This prevents capturing location information
    match = re.search(r"\bin\s+([A-Za-z\s&/\-]+?)(?:\s*(?:,|$|[\n\r]))", text, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        # Avoid capturing location keywords (City, Country)
        if len(field) > 2 and field.lower() not in {"states", "united states"}:
            # If field contains a comma, take only the part before it
            if "," in field:
                field = field.split(",")[0].strip()
            return field
    
    # Fallback: look for title-cased words after degree keyword
    degree_keywords_pattern = "|".join(re.escape(k) for k in ["bachelor", "master", "associate", "phd", "doctorate"])
    match = re.search(f"(?:{degree_keywords_pattern})\\s+(?:of\\s+)?[a-z]+\\s+([A-Za-z\\s&/\\-]+?)(?:,|$)", text, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        return field
    
    return None


def classify_entry_as_education(
    entry_lines: List[str],
    current_section: Optional[str] = None
) -> bool:
    """
    Determine if an entry should be classified as education based on:
    1. Current section context
    2. Degree keywords
    3. Institution keywords
    4. High school detection
    
    Args:
        entry_lines: List of text lines in the entry
        current_section: Current section type ("education", "experience", or None)
    
    Returns:
        True if entry should be education, False if experience
    """
    combined_text = " ".join(entry_lines).lower()
    
    # STRONG SIGNAL: Degree keyword -> ALWAYS education
    if has_degree_keyword(combined_text):
        return True
    
    # STRONG SIGNAL: High school -> ALWAYS education
    if is_high_school(combined_text):
        return True
    
    # STRONG SIGNAL: Study abroad -> ALWAYS education
    if is_study_abroad(combined_text):
        return True
    
    # CONTEXT: If in education section + has institution keyword -> education
    if current_section == "education" and is_institution_keyword(combined_text):
        return True
    
    # CONTEXT: If in education section but no conflicting signals -> assume education
    if current_section == "education":
        return True
    
    # Default: if no education signals and section is unknown or experience, treat as experience
    return False


def _extract_location_from_study_abroad(text: str) -> Optional[str]:
    """
    Extract location from study abroad entry like "DIS Study Abroad, Copenhagen".
    
    Special handling to extract the city name after comma in study abroad entries,
    even if it's a single word (unlike normal location extraction which requires City, State).
    
    Args:
        text: Study abroad text that may contain location after comma
    
    Returns:
        Location (city name) or None
    """
    # Look for comma followed by a single city name
    # Pattern: "DIS Study Abroad, Copenhagen" -> "Copenhagen"
    match = re.search(r",\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)$", text)
    if match:
        location = match.group(1).strip()
        # Validate it's a reasonable location name (at least 4 chars, no numbers)
        if len(location) >= 3 and not any(c.isdigit() for c in location):
            return location
    
    return None


def _expand_study_abroad_abbreviation(institution_text: str) -> str:
    """
    Expand known study abroad program abbreviations to full names.
    
    Examples:
        "DIS Study Abroad" -> "Danish Institute of Study Abroad"
        "ISA Study Abroad" -> "Institute for Study Abroad"
        "AIFS" -> "American Institute for Foreign Study"
    
    Args:
        institution_text: Institution text that may contain abbreviations
    
    Returns:
        Institution text with abbreviations expanded and deduplicated
    """
    for abbrev, full_name in STUDY_ABROAD_ABBREVIATIONS.items():
        # Match abbreviation at start of text (case-insensitive)
        pattern = re.compile(r"^" + re.escape(abbrev) + r"\s+", re.IGNORECASE)
        if pattern.match(institution_text):
            # Replace abbreviation with full name
            expanded = pattern.sub(full_name + " ", institution_text)
            
            # Remove trailing "Study Abroad" if the full name already contains it
            if "study abroad" in full_name.lower() and expanded.lower().endswith("study abroad"):
                expanded = re.sub(r"\s+[Ss]tudy\s+[Aa]broad\s*$", "", expanded).strip()
            
            return expanded.strip()
    
    return institution_text


def parse_education_entry(
    entry_lines: List[Tuple[str, str]],
    current_section: Optional[str] = None
) -> Tuple[EducationEntry, List[str]]:
    """
    Parse a single education entry (list of lines) into structured EducationEntry.
    
    Expected structure (flexible):
      Line 1: Institution (possibly with degree)
      Line 2: Location or Dates (if not on line 1)
      Line N: Details/bullets (majors, minors, honors, coursework, etc.)
    
    Args:
        entry_lines: List of (locator, text) tuples for the entry
        current_section: Section context ("education" or None)
    
    Returns:
        (EducationEntry object, list of warning messages)
    """
    education = EducationEntry()
    warnings = []
    
    if not entry_lines:
        return education, warnings
    
    # Pre-scan all lines to find structure
    # CRITICAL: Normalize word breaks FIRST to handle PDF artifacts
    lines_text = [normalize_pdf_wordbreaks(text.strip()) for locator, text in entry_lines]
    
    # Parse first line separately (may contain Institution: Degree format)
    first_text = lines_text[0] if lines_text else ""
    remaining_lines = lines_text[1:] if len(lines_text) > 1 else []
    combined_text = " ".join(lines_text)
    
    # CRITICAL: Check if first line is a BULLET before splitting on colon
    # Bullets with colons (e.g., "● Applied Communications Major: Social Media/Marketing")
    # must be preserved as details, not parsed as headers
    bullet_re = re.compile(r"^[\s•●\-\*\→\>]+")
    is_first_line_bullet = bullet_re.match(first_text)
    
    # Try to split first line on colon (common format: "UNIVERSITY: Degree")
    # BUT ONLY if it's NOT a bullet line
    institution_part = first_text
    degree_part = None
    
    if not is_first_line_bullet and ":" in first_text:
        parts = first_text.split(":", 1)
        institution_part = parts[0].strip()
        degree_part = parts[1].strip() if len(parts) > 1 else None
    elif is_first_line_bullet:
        # This is a bullet line, treat entire first line as a detail
        # and there's no institution on first line
        institution_part = None
    
    # Extract degree from degree_part first, then fallback to full text
    if degree_part:
        degree = extract_degree_from_text(degree_part)
        if degree:
            # Search for the " in <field>" pattern in the original degree_part
            # to extract field_of_study without mangling multi-word degrees
            field_match = re.search(
                r"\bin\s+([A-Za-z\s&/\-]+?)(?:\s*(?:,|$|[\n\r]))",
                degree_part,
                re.IGNORECASE
            )
            if field_match:
                field = field_match.group(1).strip()
                if field and len(field) > 2:
                    education.degree = degree.strip()
                    education.field_of_study = field
                else:
                    education.degree = degree.strip()
            else:
                education.degree = degree.strip()
                # Try to extract field_of_study from the degree part
                field = extract_field_of_study_from_degree_line(degree_part)
                if field:
                    education.field_of_study = field
        elif degree_part:
            # No standard degree found, but we have text after the colon
            # For study abroad or special cases, use the text as-is
            # e.g., "DANISH INSTITUTE OF STUDY ABROAD: STUDENT" -> degree = "STUDENT"
            education.degree = degree_part
    
    if not education.degree:
        # Fallback: search entire text for degree, then look for " in " pattern
        degree = extract_degree_from_text(combined_text)
        if degree:
            # Search for the " in <field>" pattern in the combined_text
            field_match = re.search(
                r"\bin\s+([A-Za-z\s&/\-]+?)(?:\s*(?:,|$|[\n\r●•\-\*]))",
                combined_text,
                re.IGNORECASE
            )
            if field_match:
                field = field_match.group(1).strip()
                if field and len(field) > 2:
                    education.degree = degree.strip()
                    education.field_of_study = field
                else:
                    education.degree = degree.strip()
            else:
                education.degree = degree.strip()
        
        # Extract field from the first line (before location) if available
        if not education.field_of_study:
            field = extract_field_of_study_from_degree_line(first_text if degree_part is None else degree_part)
            if field:
                education.field_of_study = field
    
    # Additional field_of_study extraction from details if not found yet
    # Look for lines with " in " pattern (e.g., "Bachelor of Science in Communication Studies")
    if not education.field_of_study and education.degree:
        for line in lines_text:
            if " in " in line and education.degree.lower() in line.lower():
                # Extract field after " in "
                field_match = re.search(rf"{re.escape(education.degree)}\s+in\s+([A-Za-z\s&/\-]+?)(?:\s*(?:,|$|[\n\r●•\-\*]))", line, re.IGNORECASE)
                if field_match:
                    field = field_match.group(1).strip()
                    if len(field) > 2:
                        education.field_of_study = field
                        break
    
    # Parse institution name (skip if first line was a bullet)
    if institution_part:
        # Special case: Check for study abroad patterns like "DIS Study Abroad, Copenhagen"
        if is_study_abroad(institution_part):
            # For study abroad, extract location using special handler
            loc = _extract_location_from_study_abroad(institution_part)
            
            if loc:
                # Institution is everything before location
                loc_idx = institution_part.find(loc)
                inst_name = institution_part[:loc_idx].strip().rstrip(",").strip()
                education.institution = _expand_study_abroad_abbreviation(inst_name)
                education.location = loc
            else:
                # Full thing is institution (no location extracted), try expanding abbreviation
                education.institution = _expand_study_abroad_abbreviation(institution_part)
        else:
            # Check if it has a location (City, State)
            loc = None
            try:
                from app.core.line_parser import _extract_location_from_line
                loc = _extract_location_from_line(institution_part)
            except:
                pass
            
            if loc:
                # Institution is everything before location
                loc_idx = institution_part.find(loc)
                inst_name = institution_part[:loc_idx].strip().rstrip(",")
                education.institution = inst_name
                education.location = loc
            else:
                # Full part is institution
                education.institution = institution_part
    
    # Parse remaining lines for location (if not found in first line), dates, and details
    # If first line was a bullet, include it in remaining processing
    lines_to_process = remaining_lines
    if is_first_line_bullet:
        lines_to_process = [first_text] + remaining_lines
    
    # Import here to avoid circular imports
    from app.core.line_parser import _extract_location_from_line, DATE_RANGE_RE
    
    # Study abroad location/date pattern: "Copenhagen, Denmark, Spring Trimester – 2015"
    STUDY_ABROAD_LOC_LINE = re.compile(
        r"^(?P<city>[^,]+),\s*(?P<country>[^,]+),\s*(?P<term>.+?)\s*[–-]\s*(?P<year>(19|20)\d{2})\s*$",
        re.IGNORECASE
    )
    
    for text in lines_to_process:
        t = text.strip()
        
        # Skip empty lines
        if not t:
            continue
        
        # CRITICAL: Handle bullets FIRST (before any other logic)
        # Bullets are ALWAYS details, never headers or entry boundaries
        if bullet_re.match(t):
            detail_text = bullet_re.sub("", t).strip()
            if detail_text and 5 < len(detail_text) < 500:
                education.details.append(detail_text)
            continue
        
        # Check for study abroad location/date pattern FIRST (before normal location extraction)
        # This prevents "Denmark, Spring" from being matched as a location
        # Study abroad pattern: "Copenhagen, Denmark, Spring Trimester – 2015"
        study_abroad_match = STUDY_ABROAD_LOC_LINE.match(t)
        if study_abroad_match and not education.location:
            city = study_abroad_match.group('city').strip()
            country = study_abroad_match.group('country').strip()
            term = study_abroad_match.group('term').strip()
            year = study_abroad_match.group('year').strip()
            
            education.location = f"{city}, {country}"
            education.start_date = year
            education.end_date = year
            # Add term to details
            education.details.append(term)
            continue
        
        # Check if it's a location or dates line (will have both or dates only)
        has_location = False
        has_dates = False
        
        loc = _extract_location_from_line(t)
        if loc and not education.location:
            education.location = loc
            has_location = True
        
        dates_match = DATE_RANGE_RE.search(t)
        if dates_match:
            matched = dates_match.group(0).strip()
            parts = re.split(r"\s*(?:-|–|to)\s*", matched, flags=re.IGNORECASE)
            if len(parts) >= 2:
                # Only set start_date if not already set
                if not education.start_date:
                    education.start_date = parts[0].strip()
                # Always update end_date to the most recent (last) date found
                education.end_date = parts[1].strip()
            has_dates = True
        
        # Special case: Trimester/Semester format (e.g., "Spring Trimester 2015", "Fall Semester 2016")
        if not has_dates and not education.end_date:
            trimester_match = re.search(r"(Spring|Fall|Winter|Summer)\s+(Trimester|Semester|Term)\s+(\d{4})", t, re.IGNORECASE)
            if trimester_match:
                year = trimester_match.group(3)
                term = trimester_match.group(1)
                education.end_date = year
                # Optionally store the term in details
                education.details.append(f"{term} {trimester_match.group(2)} {year}")
                has_dates = True
        
        # If this line is just location+dates (no bullet) AND has no other meaningful content, skip
        # But we need to be careful: lines like "Spokane, Washington, 2012 – 2016" might be location+dates
        # while others might be location + detail
        if has_location or has_dates:
            # Check if the line has ONLY location/dates or if there's more content
            # Strip out the location and dates we found, see what's left
            remaining_text = t
            if has_location:
                # Try to remove the location we found
                loc_start = remaining_text.find(education.location) if education.location else -1
                if loc_start >= 0:
                    remaining_text = remaining_text[:loc_start] + remaining_text[loc_start + len(education.location):]
            if has_dates:
                # Try to remove the date range
                remaining_text = DATE_RANGE_RE.sub("", remaining_text)
            
            remaining_text = remaining_text.strip()
            # If there's meaningful content left, add it as detail
            if remaining_text and 5 < len(remaining_text) < 500:
                education.details.append(remaining_text)
            continue
        
        # If we get here, it might be a non-bullet detail line or degree line
        # Add it as a detail if it's meaningful
        if 5 < len(t) < 500:
            education.details.append(t)
    
    # Validation: Remove junk details like "References Available Upon Request"
    junk_patterns = [
        r"references available upon request",
        r"available upon request",
        r"contact",
        r"phone",
        r"email",
    ]
    
    cleaned_details = []
    for detail in education.details:
        is_junk = False
        for pattern in junk_patterns:
            if re.search(pattern, detail.lower()):
                is_junk = True
                warnings.append(f"Removed junk detail from education entry: {detail}")
                break
        
        # Also filter out detail lines that are just numbers (likely orphaned dates)
        if not is_junk and detail.strip() and not re.match(r"^\d{4}$", detail.strip()):
            cleaned_details.append(detail)
        elif re.match(r"^\d{4}$", detail.strip()):
            # Log that we're removing a year-only detail
            warnings.append(f"Removed orphaned year from education details: {detail}")
    
    education.details = cleaned_details
    
    return education, warnings

