"""
Character-level PDF extraction using geometric word boundary detection.

This module extracts characters with their positions, fonts, and sizes from PDFs,
then reconstructs words using gap-based thresholds rather than linguistic assumptions.

Phase 2a: Geometric-first approach (experimental).
"""

from typing import Dict, List, Tuple, Optional
import pdfplumber
from dataclasses import dataclass


@dataclass
class PDFCharacter:
    """Represents a single character with its geometric properties."""
    page: int
    char: str
    x0: float
    y0: float
    x1: float
    y1: float
    fontname: str
    size: float
    
    @property
    def width(self) -> float:
        """Width of the character in PDF units."""
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        """Height of the character in PDF units."""
        return self.y0 - self.y0  # Usually not used, but included for completeness


@dataclass
class PDFWord:
    """Represents a word reconstructed from characters."""
    text: str
    page: int
    characters: List[PDFCharacter]
    x0: float  # Left edge
    x1: float  # Right edge
    y0: float  # Top edge
    y1: float  # Bottom edge
    
    @property
    def locator(self) -> str:
        """Return a locator string for evidence tracking."""
        return f"pdf:page:{self.page}:word:{self.x0:.1f}_{self.y0:.1f}"


@dataclass
class PDFLine:
    """Represents a line of text (multiple words)."""
    page: int
    y_position: float
    words: List[PDFWord]
    
    @property
    def text(self) -> str:
        """Return the full text of the line."""
        return " ".join(w.text for w in self.words)
    
    @property
    def locator(self) -> str:
        """Return a locator string for evidence tracking."""
        return f"pdf:page:{self.page}:line:{self.y_position:.1f}"


def extract_characters_with_geometry(pdf_path: str) -> List[PDFCharacter]:
    """
    Extract all characters from a PDF with their geometric properties.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        List of PDFCharacter objects with position, font, size information
    """
    characters = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                for char in page.chars:
                    # Skip whitespace characters (pdfplumber already handles some)
                    if char['text'].strip() == '':
                        continue
                    
                    pdf_char = PDFCharacter(
                        page=page_num,
                        char=char['text'],
                        x0=char['x0'],
                        y0=char['top'],  # pdfplumber uses 'top' instead of 'y0'
                        x1=char['x1'],
                        y1=char['top'] + char['height'],
                        fontname=char.get('fontname', 'unknown'),
                        size=char['size'],
                    )
                    characters.append(pdf_char)
    except Exception as e:
        print(f"Error extracting characters: {e}")
        return []
    
    return characters


def reconstruct_words_from_chars(
    characters: List[PDFCharacter],
    gap_threshold_ratio: float = 0.25,
) -> List[PDFWord]:
    """
    Reconstruct words from characters using geometric gap detection.
    
    Strategy:
    1. Group characters by page and line (y-clustering)
    2. Within each line, detect word boundaries using horizontal gaps
    3. Gap > threshold * font_size → new word
    
    Args:
        characters: List of PDFCharacter objects
        gap_threshold_ratio: Ratio of font size that triggers word break (default 0.25)
    
    Returns:
        List of PDFWord objects
    """
    if not characters:
        return []
    
    # Group characters by page
    by_page: Dict[int, List[PDFCharacter]] = {}
    for char in characters:
        if char.page not in by_page:
            by_page[char.page] = []
        by_page[char.page].append(char)
    
    words = []
    
    # Process each page
    for page_num in sorted(by_page.keys()):
        page_chars = by_page[page_num]
        
        # Sort by y position (top to bottom), then x position (left to right)
        page_chars.sort(key=lambda c: (round(c.y0 / 2, 0), c.x0))
        
        # Group by lines (y-clustering)
        lines = _cluster_chars_into_lines(page_chars)
        
        # Within each line, detect word boundaries
        for line_chars in lines:
            line_words = _segment_line_into_words(line_chars, gap_threshold_ratio)
            words.extend(line_words)
    
    return words


def _cluster_chars_into_lines(
    chars: List[PDFCharacter],
    y_tolerance: float = 3.0,
) -> List[List[PDFCharacter]]:
    """
    Group characters into lines by clustering on y-position.
    
    Args:
        chars: Sorted list of characters (by y, then x)
        y_tolerance: Vertical distance threshold for same line (in PDF units)
    
    Returns:
        List of character groups (each group is a line)
    """
    if not chars:
        return []
    
    lines = []
    current_line = [chars[0]]
    current_y = chars[0].y0
    
    for char in chars[1:]:
        # Check if character is on the same line
        if abs(char.y0 - current_y) < y_tolerance:
            current_line.append(char)
        else:
            # Start new line
            lines.append(current_line)
            current_line = [char]
            current_y = char.y0
    
    # Add last line
    if current_line:
        lines.append(current_line)
    
    return lines


def _segment_line_into_words(
    line_chars: List[PDFCharacter],
    gap_threshold_ratio: float = 0.25,
) -> List[PDFWord]:
    """
    Segment a line of characters into words using horizontal gap detection.
    
    Rule: gap > threshold_ratio * font_size → new word
    
    Also detect space characters explicitly and use them as hard boundaries.
    
    Args:
        line_chars: Characters in a single line (sorted by x)
        gap_threshold_ratio: Multiplier for font size to determine gap threshold
    
    Returns:
        List of PDFWord objects
    """
    if not line_chars:
        return []
    
    # Sort by x position (left to right)
    line_chars.sort(key=lambda c: c.x0)
    
    words = []
    current_word_chars = [line_chars[0]]
    
    for i in range(1, len(line_chars)):
        prev_char = line_chars[i - 1]
        curr_char = line_chars[i]
        
        # Calculate gap between characters
        gap = curr_char.x0 - prev_char.x1
        
        # Use current character's font size for threshold calculation
        # ADJUSTED: Use 0.3-0.4x font size for better separation detection
        threshold = gap_threshold_ratio * curr_char.size
        
        # Check if this is a space character (explicit word boundary)
        # Space chars won't be in the char list due to pdfplumber filtering,
        # so detect via large gaps instead
        is_space_gap = gap > (curr_char.size * 0.35)  # Larger gap = space
        
        # Also check for unusual font/size changes (column switches, etc.)
        font_changed = curr_char.fontname != prev_char.fontname
        size_changed = abs(curr_char.size - prev_char.size) > 1.0
        
        # Start new word if:
        # - Gap is large (space)
        # - Font changes
        # - Size changes significantly
        if is_space_gap or font_changed or size_changed:
            # Save current word and start new one
            words.append(_build_word(current_word_chars))
            current_word_chars = [curr_char]
        else:
            # Continue current word
            current_word_chars.append(curr_char)
    
    # Add last word
    if current_word_chars:
        words.append(_build_word(current_word_chars))
    
    return words


def _build_word(chars: List[PDFCharacter]) -> PDFWord:
    """Construct a PDFWord from a list of characters."""
    text = "".join(c.char for c in chars)
    x0 = min(c.x0 for c in chars)
    x1 = max(c.x1 for c in chars)
    y0 = min(c.y0 for c in chars)
    y1 = max(c.y1 for c in chars)
    
    return PDFWord(
        text=text,
        page=chars[0].page,
        characters=chars,
        x0=x0,
        x1=x1,
        y0=y0,
        y1=y1,
    )


def reconstruct_lines_from_words(words: List[PDFWord]) -> List[PDFLine]:
    """
    Group words back into lines (for compatibility with existing parsing pipeline).
    
    Args:
        words: List of PDFWord objects
    
    Returns:
        List of PDFLine objects
    """
    if not words:
        return []
    
    # Group words by page and y-position
    by_page_and_line: Dict[Tuple[int, float], List[PDFWord]] = {}
    
    for word in words:
        # Cluster words by y position (same line)
        line_key = (word.page, round(word.y0 / 2, 0) * 2)  # Round y to nearest 2 units
        if line_key not in by_page_and_line:
            by_page_and_line[line_key] = []
        by_page_and_line[line_key].append(word)
    
    # Sort words within each line by x position
    lines = []
    for (page, y), line_words in sorted(by_page_and_line.items()):
        line_words.sort(key=lambda w: w.x0)
        lines.append(PDFLine(page=page, y_position=y, words=line_words))
    
    return lines


def compute_extraction_quality(words: List[PDFWord]) -> Dict:
    """
    Compute quality signals to determine if text repair is needed.
    
    Signals:
    - % tokens found in common word dictionary
    - average token length
    - # tokens > 20 chars
    - ratio of tokens with no vowels
    - unexpected case patterns (ALLCAPS with no separators)
    
    Args:
        words: List of PDFWord objects
    
    Returns:
        Dictionary with quality metrics and repair recommendation
    """
    from app.core.line_parser import COMMON_WORDS
    
    if not words:
        return {
            'total_words': 0,
            'dict_coverage': 0.0,
            'avg_length': 0.0,
            'long_words': 0,
            'no_vowel_ratio': 0.0,
            'suspicious_ratio': 0.0,
            'needs_repair': False,
            'quality_score': 1.0,
        }
    
    total_words = len(words)
    dict_coverage_count = 0
    suspicious_count = 0
    no_vowel_count = 0
    long_words = 0
    total_length = 0
    
    suspicious_words = set()  # Track suspicious word indices to avoid double-counting
    
    for idx, word in enumerate(words):
        text = word.text.strip()
        
        # Skip punctuation-only words
        if not text or not any(c.isalpha() for c in text):
            continue
        
        total_length += len(text)
        text_lower = text.lower()
        
        # Dictionary coverage
        if text_lower in COMMON_WORDS:
            dict_coverage_count += 1
        
        # Check for long words
        if len(text) > 20:
            long_words += 1
            suspicious_words.add(idx)
        
        # Check for lack of vowels
        vowel_count = sum(1 for c in text_lower if c in 'aeiou')
        if len(text) > 3 and vowel_count == 0:
            no_vowel_count += 1
            suspicious_words.add(idx)
        
        # Check for all-caps without separators (suspicious pattern)
        if text.isupper() and len(text) > 5:
            suspicious_words.add(idx)
    
    # Calculate ratios
    alphanumeric_words = sum(1 for w in words if any(c.isalpha() for c in w.text))
    suspicious_count = len(suspicious_words)
    dict_coverage = dict_coverage_count / max(alphanumeric_words, 1)
    no_vowel_ratio = no_vowel_count / max(alphanumeric_words, 1)
    suspicious_ratio = suspicious_count / max(alphanumeric_words, 1)
    avg_length = total_length / max(alphanumeric_words, 1)
    
    # Overall quality score (0-1, higher is better)
    quality_score = (
        dict_coverage * 0.5 +  # Dictionary coverage is most important
        (1 - no_vowel_ratio) * 0.2 +  # Avoid no-vowel words
        (1 - suspicious_ratio) * 0.3  # Avoid suspicious patterns
    )
    
    # Recommendation: trigger repair if quality is below threshold
    needs_repair = (
        suspicious_ratio > 0.15 or  # More than 15% suspicious words
        dict_coverage < 0.6 or  # Less than 60% in dictionary
        no_vowel_ratio > 0.1  # More than 10% no-vowel words
    )
    
    return {
        'total_words': total_words,
        'dict_coverage': dict_coverage,
        'avg_length': avg_length,
        'long_words': long_words,
        'no_vowel_ratio': no_vowel_ratio,
        'suspicious_ratio': suspicious_ratio,
        'suspicious_count': suspicious_count,
        'needs_repair': needs_repair,
        'quality_score': quality_score,
    }


def extract_and_analyze_pdf(pdf_path: str) -> Dict:
    """
    Complete extraction pipeline: extract characters, reconstruct words,
    group into lines, and compute quality signals.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Dictionary with:
        - characters: List of PDFCharacter objects
        - words: List of PDFWord objects
        - lines: List of PDFLine objects (for compatibility)
        - quality: Quality analysis dictionary
    """
    # Step A: Extract characters
    characters = extract_characters_with_geometry(pdf_path)
    
    # Step B: Reconstruct words using geometry
    words = reconstruct_words_from_chars(characters)
    
    # Step C: Group words into lines
    lines = reconstruct_lines_from_words(words)
    
    # Step D: Compute quality signals
    quality = compute_extraction_quality(words)
    
    return {
        'characters': characters,
        'words': words,
        'lines': lines,
        'quality': quality,
    }
