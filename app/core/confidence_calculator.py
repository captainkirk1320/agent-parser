"""
Confidence scoring for resume extraction fields.

Per-field confidence tracking allows downstream consumers to understand extraction certainty
and make intelligent decisions about whether to prompt the candidate for clarification.

Confidence Scale:
  1.0   = Exact match (regex, known value)
  0.9   = Very high confidence (minor normalization needed)
  0.8   = High confidence (inferred but validated)
  0.7   = Medium-high confidence (heuristic with good signals)
  0.6   = Medium confidence (multiple signals, some uncertainty)
  0.5   = Low-medium confidence (ambiguous but extractable)
  <0.5  = Low confidence (should prompt for clarification)
"""

from typing import List, Dict, Optional, Tuple
import re


class ConfidenceCalculator:
    """Central place for all extraction confidence logic."""

    @staticmethod
    def email(email_value: str, evidence_count: int = 1) -> Tuple[float, str]:
        """
        Calculate confidence for email extraction.
        
        Email is high confidence if:
          - Matches standard RFC5322 regex (simplified)
          - Found exactly once in resume
        
        Lower confidence if:
          - Found multiple times (ambiguity)
          - In unusual position (e.g., mid-text, not near name)
        """
        if not email_value:
            return 0.0, "no_email_found"
        
        # Validate format
        email_pattern = r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$"
        if not re.match(email_pattern, email_value, re.IGNORECASE):
            return 0.4, "invalid_email_format"
        
        # Exact match = high confidence
        if evidence_count == 1:
            return 1.0, "regex_exact_single"
        elif evidence_count <= 3:
            return 0.85, "regex_exact_multiple_occurrences"
        else:
            return 0.6, "too_many_email_candidates"

    @staticmethod
    def phone(phone_value: str, evidence_count: int = 1) -> Tuple[float, str]:
        """
        Calculate confidence for phone extraction.
        
        Phone is high confidence if:
          - Matches standard patterns (US or international)
          - Found exactly once
        """
        if not phone_value:
            return 0.0, "no_phone_found"
        
        # Check basic validity
        digits_only = re.sub(r"\D", "", phone_value)
        if len(digits_only) < 7:  # Too short to be a real phone
            return 0.3, "too_few_digits"
        
        if evidence_count == 1:
            return 1.0, "regex_exact_single"
        elif evidence_count <= 2:
            return 0.85, "regex_exact_multiple"
        else:
            return 0.6, "ambiguous_multiple_phones"

    @staticmethod
    def full_name(
        name_value: str,
        near_email: bool = False,
        is_top_of_resume: bool = False,
        passes_blacklist: bool = True,
        has_middle_initial: bool = False,
    ) -> Tuple[float, str]:
        """
        Calculate confidence for full name extraction.
        
        Factors:
          + Found near email (strong signal)
          + At top of resume (strong signal)
          + Passes blacklist (no section headers, etc.)
          + Has middle initial (good signal, less ambiguous)
          - Just title case at top (could be company name)
          - Contains numbers (likely bad parse)
        """
        if not name_value:
            return 0.0, "no_name_found"
        
        confidence = 0.5  # Start with baseline
        reasons = []
        
        # Quality checks
        if len(name_value) > 60:
            return 0.2, "name_too_long"
        
        if any(c.isdigit() for c in name_value):
            return 0.3, "name_contains_digits"
        
        if not passes_blacklist:
            confidence -= 0.2
            reasons.append("matches_blacklist_headers")
        else:
            reasons.append("passes_header_blacklist")
        
        # Positive signals
        if near_email:
            confidence += 0.25
            reasons.append("near_email")
        
        if is_top_of_resume:
            confidence += 0.25
            reasons.append("at_resume_top")
        
        if has_middle_initial:
            confidence += 0.05
            reasons.append("has_middle_initial")
        
        # Must have at least one space (first + last)
        if " " not in name_value:
            return 0.2, "no_space_in_name"
        
        confidence = max(0.0, min(1.0, confidence))
        method = "heuristic_window"
        if near_email and is_top_of_resume:
            method = "heuristic_multivariate"
        
        return confidence, method

    @staticmethod
    def location(
        location_value: str,
        extraction_method: str = "regex_pattern",  # "regex_pattern", "heuristic", "after_title"
        has_comma: bool = False,
        is_valid_format: bool = True,
    ) -> Tuple[float, str]:
        """
        Calculate confidence for location extraction.
        
        High confidence if:
          - Matches "City, State/Country" pattern
          - Extracted from dedicated location field (not glued to other text)
        
        Lower confidence if:
          - Only city name (no state)
          - Extracted from end of long line (could be date misparse)
        """
        if not location_value:
            return 0.0, "no_location_found"
        
        confidence = 0.6
        
        if extraction_method == "regex_pattern":
            confidence = 0.95 if is_valid_format else 0.7
        elif extraction_method == "heuristic":
            confidence = 0.75
        elif extraction_method == "after_title":
            confidence = 0.65  # Could be on same line as job title
        
        if not has_comma:
            confidence -= 0.1  # Missing state is less confident
        
        confidence = max(0.0, min(1.0, confidence))
        return confidence, extraction_method

    @staticmethod
    def url(url_value: str, url_type: str = "generic") -> Tuple[float, str]:
        """
        Calculate confidence for URL extraction.
        
        Types: linkedin, github, generic (http/https)
        Each has standard format.
        """
        if not url_value:
            return 0.0, "no_url_found"
        
        # Check format
        if not url_value.startswith(("http://", "https://")):
            return 0.3, "missing_protocol"
        
        if url_type == "linkedin":
            if "linkedin.com" in url_value:
                return 0.95, "linkedin_exact"
            return 0.5, "linkedin_invalid"
        elif url_type == "github":
            if "github.com" in url_value:
                return 0.95, "github_exact"
            return 0.5, "github_invalid"
        else:
            if url_value.count(".") >= 2:
                return 0.9, "generic_url_valid"
            return 0.6, "generic_url_questionable"

    @staticmethod
    def skill(
        skill_value: str,
        extraction_source: str = "inline",  # "inline", "bullet", "section_subheading"
        is_recognized: bool = True,
    ) -> Tuple[float, str]:
        """
        Calculate confidence for individual skill.
        
        Extraction source matters:
          - "inline" (Skills: Python, Java) = 0.95
          - "bullet" (• Python) = 0.85
          - "section_subheading" (Languages: Python) = 0.80
        
        Recognized skills (from known list) get slight boost.
        """
        if not skill_value:
            return 0.0, "empty_skill"
        
        if len(skill_value) < 2 or len(skill_value) > 100:
            return 0.2, "skill_length_invalid"
        
        confidence_map = {
            "inline": 0.95,
            "bullet": 0.85,
            "section_subheading": 0.80,
        }
        
        confidence = confidence_map.get(extraction_source, 0.75)
        
        if is_recognized:
            confidence = min(1.0, confidence + 0.02)
        
        return confidence, f"{extraction_source}_extracted"

    @staticmethod
    def experience_field(
        field_name: str,  # "company", "job_title", "location", "start_date", "end_date"
        field_value: Optional[str],
        extraction_line: Optional[str] = None,
        line_format: Optional[str] = None,  # "single_line", "multi_line"
        matched_pattern: bool = False,
    ) -> Tuple[float, str]:
        """
        Calculate confidence for individual experience field.
        
        Different fields have different confidence profiles:
          - Company: Usually high confidence if extracted cleanly
          - Job Title: Medium (can be ambiguous with descriptions)
          - Dates: High if regex matches, low if inferred
          - Location: High if "City, State" format, low if partial
        """
        if not field_value:
            return 0.0, f"no_{field_name}_found"
        
        # Field-specific logic
        if field_name == "company":
            # Company names are usually unambiguous
            confidence = 0.9 if line_format == "single_line" else 0.85
            return confidence, "company_extracted"
        
        elif field_name == "job_title":
            # Job titles are harder (could overlap with descriptions)
            if line_format == "single_line":
                confidence = 0.9 if matched_pattern else 0.7
            else:
                # Multi-line: likely on its own line
                confidence = 0.85 if len(field_value) < 100 else 0.6
            return confidence, "job_title_extracted"
        
        elif field_name == "start_date" or field_name == "end_date":
            # Dates are high confidence if regex matches
            if matched_pattern:
                confidence = 0.95
            else:
                confidence = 0.4  # Inferred/guessed
            return confidence, "date_extracted"
        
        elif field_name == "location":
            # Location confidence already handled by location() above
            # This is a fallback
            return 0.7, "location_experience_field"
        
        else:
            # Default: medium confidence
            return 0.6, f"field_{field_name}_unknown"

    @staticmethod
    def calculate_overall_parse_quality(field_confidences: Dict[str, float]) -> str:
        """
        Determine overall parse quality based on per-field confidences.
        
        Quality tiers:
          "high"   : Core fields (name, email, phone) have confidence >= 0.85
          "medium" : Core fields have confidence >= 0.65
          "low"    : Otherwise
        """
        core_fields = ["full_name", "email", "phone"]
        core_confidences = [
            field_confidences.get(field, 0.0) for field in core_fields
        ]
        
        avg_core = sum(core_confidences) / len(core_confidences) if core_confidences else 0.0
        
        if avg_core >= 0.85:
            return "high"
        elif avg_core >= 0.65:
            return "medium"
        else:
            return "low"
