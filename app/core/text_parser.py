import re
from typing import Dict, List, Tuple

from app.core.schemas import CandidateProfile, EvidenceItem, ParseResponse
from app.core.line_parser import parse_lines_to_response


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
URL_RE = re.compile(r"\bhttps?://[^\s)>\]]+\b", re.IGNORECASE)
LINKEDIN_RE = re.compile(r"\b(?:https?://)?(?:www\.)?linkedin\.com/[^\s)>\]]+\b", re.IGNORECASE)
GITHUB_RE = re.compile(r"\b(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_.-]+\b", re.IGNORECASE)


def _line_locator(i: int) -> str:
    return f"text:line:{i+1}"


def _add_evidence(evidence_map: Dict[str, List[EvidenceItem]], key: str, source: str, locator: str, text: str) -> None:
    evidence_map.setdefault(key, []).append(
        EvidenceItem(source=source, locator=locator, text=text.strip())
    )


def parse_text_to_response(text: str, source: str = "user") -> ParseResponse:
    """
    Parse plain text resume by converting to lines and delegating to line_parser.
    This ensures TXT/MD files get the same processing as DOCX/PDF.
    """
    lines = text.splitlines()
    
    # Convert to (locator, text) tuples like DOCX/PDF extractors do
    line_tuples = [(f"text:line:{i+1}", line) for i, line in enumerate(lines)]
    
    # Use the unified line parser
    return parse_lines_to_response(line_tuples, source=source)
