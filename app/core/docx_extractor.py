from io import BytesIO
from typing import List, Tuple

from docx import Document


def extract_docx_lines(docx_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Deterministically extract non-empty paragraph text from a DOCX.
    Returns list of (paragraph_index, text).
    """
    doc = Document(BytesIO(docx_bytes))
    out: List[Tuple[int, str]] = []
    for i, p in enumerate(doc.paragraphs):
        t = (p.text or "").strip()
        if t:
            out.append((i, t))
    return out
