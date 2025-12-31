"""
Hybrid extraction pipeline: Geometric-first, linguistic-second.

Uses character-level extraction to identify word boundaries geometrically.
If quality signals indicate issues, applies linguistic repair.

This is the "Phase 2" approach: deterministic, measurable, explainable.
"""

from typing import Dict, List, Tuple, Optional
import pdfplumber
from app.core.pdf_character_extractor import (
    extract_and_analyze_pdf,
    reconstruct_lines_from_words,
    PDFWord,
    PDFLine,
)
from app.core.line_parser import _segment_concatenated_words


def extract_pdf_hybrid(
    pdf_path: str,
    quality_threshold: float = 0.6,
    repair_if_needed: bool = True,
) -> Dict:
    """
    Hybrid extraction pipeline combining geometric and linguistic approaches.
    
    Strategy:
    1. Extract characters and reconstruct words geometrically
    2. Compute quality signals
    3. If quality is below threshold AND repair_if_needed=True, apply linguistic repair
    4. Return both geometric and repaired versions for comparison
    
    Args:
        pdf_path: Path to PDF file
        quality_threshold: Minimum quality score before applying repair (0-1)
        repair_if_needed: Whether to apply linguistic repair if quality is low
    
    Returns:
        Dictionary with:
        - geometric_lines: Lines from geometric extraction
        - repaired_lines: Lines after linguistic repair (if applied)
        - quality: Quality analysis
        - repair_applied: Whether repair was applied
        - evidence: Mapping of line locators to original text
    """
    # Step 1: Geometric extraction
    result = extract_and_analyze_pdf(pdf_path)
    geometric_lines = result['lines']
    quality = result['quality']
    
    # Step 2: Decide if repair is needed
    repair_applied = (
        repair_if_needed and
        (quality['needs_repair'] or quality['quality_score'] < quality_threshold)
    )
    
    # Step 3: Apply linguistic repair if needed
    repaired_lines = geometric_lines
    if repair_applied:
        repaired_lines = _apply_linguistic_repair(geometric_lines)
    
    # Step 4: Build evidence mapping
    evidence = _build_evidence_map(
        geometric_lines if not repair_applied else repaired_lines,
        pdf_path
    )
    
    return {
        'geometric_lines': geometric_lines,
        'repaired_lines': repaired_lines,
        'quality': quality,
        'repair_applied': repair_applied,
        'evidence': evidence,
    }


def _apply_linguistic_repair(lines: List[PDFLine]) -> List[PDFLine]:
    """
    Apply linguistic word-segmentation repair to geometric extraction.
    
    This runs the concatenated-word segmentation on suspicious words.
    """
    repaired_lines = []
    
    for line in lines:
        # Repair each word in the line
        repaired_words = []
        for word in line.words:
            text = word.text
            
            # Only repair if word looks suspicious
            if _should_repair_word(text):
                # Apply segmentation
                repaired_text = _segment_concatenated_words(text)
                
                # If repair changed the text, we need to split the word
                if ' ' in repaired_text:
                    # Split into multiple words
                    for repaired_part in repaired_text.split():
                        # Create a new word with the repaired text
                        # (keeping original character references for evidence)
                        repaired_words.append(
                            PDFWord(
                                text=repaired_part,
                                page=word.page,
                                characters=word.characters,  # Keep original for tracing
                                x0=word.x0,
                                x1=word.x1,
                                y0=word.y0,
                                y1=word.y1,
                            )
                        )
                else:
                    # No change, keep original
                    repaired_words.append(word)
            else:
                # Word looks fine, keep as is
                repaired_words.append(word)
        
        # Reconstruct line with repaired words
        repaired_lines.append(
            PDFLine(
                page=line.page,
                y_position=line.y_position,
                words=repaired_words,
            )
        )
    
    return repaired_lines


def _should_repair_word(text: str) -> bool:
    """
    Determine if a word is suspicious and should be repaired.
    
    Suspicious patterns:
    - Very long (>15 chars)
    - No vowels
    - All uppercase
    - Mix of numbers and letters without spaces
    """
    if not text or len(text) < 5:
        return False
    
    # Very long words are usually concatenated
    if len(text) > 15:
        return True
    
    # No vowels in word longer than 3 chars (very suspicious)
    vowel_count = sum(1 for c in text.lower() if c in 'aeiou')
    if len(text) > 3 and vowel_count == 0:
        return True
    
    # All uppercase with no separators (like TERRITORYMANAGER)
    if text.isupper() and len(text) > 5:
        return True
    
    # Numbers and letters mixed without clear separation
    has_letters = any(c.isalpha() for c in text)
    has_digits = any(c.isdigit() for c in text)
    if has_letters and has_digits and not any(c in '.-/ ' for c in text):
        return True
    
    return False


def _build_evidence_map(lines: List[PDFLine], pdf_path: str) -> Dict:
    """
    Build an evidence map linking repaired text back to original positions.
    
    Returns:
        Dictionary mapping line locators to geometric metadata
    """
    evidence = {}
    
    for line in lines:
        locator = line.locator
        evidence[locator] = {
            'page': line.page,
            'y_position': line.y_position,
            'text': line.text,
            'source': 'pdf_geometric',
        }
    
    return evidence


def compare_approaches(pdf_path: str) -> Dict:
    """
    Compare geometric-first vs. current linguistic-first extraction.
    
    Useful for validation and testing.
    
    Returns:
        Dictionary with comparison metrics
    """
    # Geometric approach
    geometric_result = extract_pdf_hybrid(pdf_path, repair_if_needed=False)
    
    print(f"\n{'='*60}")
    print(f"PDF EXTRACTION COMPARISON: {pdf_path}")
    print(f"{'='*60}")
    
    print(f"\nGEOMETRIC-FIRST APPROACH:")
    print(f"  Total lines: {len(geometric_result['geometric_lines'])}")
    print(f"  Quality score: {geometric_result['quality']['quality_score']:.2f}")
    print(f"  Dict coverage: {geometric_result['quality']['dict_coverage']:.2%}")
    print(f"  Needs repair: {geometric_result['quality']['needs_repair']}")
    
    # With repair
    hybrid_result = extract_pdf_hybrid(pdf_path, repair_if_needed=True)
    print(f"\nHYBRID (GEOMETRIC + REPAIR):")
    print(f"  Total lines: {len(hybrid_result['repaired_lines'])}")
    print(f"  Repair applied: {hybrid_result['repair_applied']}")
    
    print(f"\nSAMPLE LINES (FIRST 3):")
    for i, (geo_line, rep_line) in enumerate(
        zip(geometric_result['geometric_lines'][:3], 
            hybrid_result['repaired_lines'][:3])
    ):
        print(f"\n  Line {i+1}:")
        print(f"    Geometric: '{geo_line.text}'")
        print(f"    Repaired:  '{rep_line.text}'")
    
    return {
        'geometric': geometric_result,
        'hybrid': hybrid_result,
    }
