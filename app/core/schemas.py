from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


ParseQuality = Literal["high", "medium", "low"]
ConfidenceScore = float  # 0.0 to 1.0


class EvidenceItem(BaseModel):
    source: Literal["docx", "pdf", "ocr", "user"]
    locator: str = Field(..., description="Where it came from (page, paragraph index, etc.)")
    text: str = Field(..., description="Exact supporting snippet")
    confidence: float = Field(default=1.0, description="Confidence in this evidence (0.0-1.0). 1.0 = exact match, <1.0 = inferred/repaired")


class FieldConfidence(BaseModel):
    """Per-field confidence metadata. Tracks why confidence is what it is."""
    field_name: str
    confidence: float = Field(..., ge=0.0, le=1.0, description="0.0 (no confidence) to 1.0 (absolute certainty)")
    extraction_method: str = Field(..., description="How it was extracted (e.g., 'regex_exact', 'heuristic', 'format_inference')")
    reasons: List[str] = Field(default_factory=list, description="Why confidence is this value")
    required: bool = Field(default=False, description="Is this field required for 'high' parse quality?")


class EducationEntry(BaseModel):
    """Education entry in candidate profile."""
    institution: Optional[str] = None  # University, School, Institute name
    degree: Optional[str] = None  # Bachelor of Science, M.S., etc.
    field_of_study: Optional[str] = None  # Computer Science, Engineering, etc.
    location: Optional[str] = None  # City, State
    start_date: Optional[str] = None  # YYYY or MM/YYYY
    end_date: Optional[str] = None  # YYYY or MM/YYYY
    gpa: Optional[str] = None  # GPA if available
    details: List[str] = Field(default_factory=list)  # Major, Minor, Focus, Honors, etc.


class CandidateProfile(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experiences: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)


class ParseResponse(BaseModel):
    candidate_profile: CandidateProfile
    evidence_map: Dict[str, List[EvidenceItem]]
    confidence_scores: Dict[str, FieldConfidence] = Field(
        default_factory=dict,
        description="Confidence metadata for each field"
    )
    parse_quality: ParseQuality
    warnings: List[str] = Field(default_factory=list)
