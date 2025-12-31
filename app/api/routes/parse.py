from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.schemas import ParseResponse
from app.core.text_parser import parse_text_to_response
from app.core.docx_extractor import extract_docx_lines
from app.core.line_parser import parse_lines_to_response
from app.core.pdf_extractor import extract_pdf_lines

router = APIRouter(tags=["parse"])


@router.post(
    "/parse",
    response_model=ParseResponse,
    summary="Parse Resume",
    description="Extract structured candidate information from a resume file (DOCX, PDF, or TXT). Returns extracted fields with evidence tracking and confidence scores.",
    responses={
        200: {
            "description": "Successfully parsed resume",
            "content": {
                "application/json": {
                    "example": {
                        "candidate_profile": {
                            "full_name": "John Doe",
                            "email": "john@example.com",
                            "phone": "(555) 123-4567",
                            "location": "San Francisco, CA",
                            "skills": ["Python", "FastAPI", "PostgreSQL"],
                            "experiences": [
                                {
                                    "company": "Tech Corp",
                                    "job_title": "Senior Engineer",
                                    "location": "San Francisco, CA",
                                    "start_date": "01/2020",
                                    "end_date": "Present"
                                }
                            ]
                        },
                        "parse_quality": "high",
                        "evidence_map": {},
                        "warnings": []
                    }
                }
            }
        },
        400: {"description": "Empty file uploaded"},
        415: {"description": "Unsupported file format"},
        422: {"description": "File has no extractable text"}
    }
)
async def parse_resume(
    file: UploadFile = File(..., description="Resume file (DOCX, PDF, or TXT format)")
):
    """
    Parse a resume file and extract candidate information.
    
    **Supported formats:**
    - DOCX (.docx)
    - PDF (.pdf) - Text-layer extraction only, OCR not supported
    - TXT (.txt)
    
    **Returns:**
    - **candidate_profile**: Extracted fields (name, email, phone, location, skills, experiences, education)
    - **evidence_map**: Source tracking for each extracted field
    - **parse_quality**: Overall quality assessment (high/medium/low)
    - **confidence_scores**: Per-field confidence metadata
    - **warnings**: Any warnings during parsing
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    # DOCX
    if filename.endswith(".docx") or content_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }:
        paras = extract_docx_lines(raw)
        lines = [(f"docx:paragraph:{i}", text) for i, text in paras]
        return parse_lines_to_response(lines, source="docx")
    # PDF
    if filename.endswith(".pdf") or content_type == "application/pdf":
        lines = extract_pdf_lines(raw)
        if not lines:
            raise HTTPException(
                status_code=422,
                detail="PDF appears to have no extractable text. OCR not enabled yet for this phase."
            )
        return parse_lines_to_response(lines, source="pdf")

    # Text
    if content_type in {"text/plain", "text/markdown", "application/json"} or filename.endswith((".txt", ".md")):
        text = raw.decode("utf-8", errors="replace")
        return parse_text_to_response(text, source="user")

    raise HTTPException(status_code=415, detail=f"Unsupported content type for now: {file.content_type}")
