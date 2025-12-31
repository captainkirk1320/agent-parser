from typing import List, Tuple
from io import BytesIO
import re
import pdfplumber
from typing import Dict, Any
from functools import lru_cache


JOINERS_SET = {"a", "an", "to", "in", "of", "for", "and", "the", "by", "on", "at", "or", "as", "is"}
SUFFIX_JOINERS = ("by", "to", "in", "of", "at", "on")
COMMON3 = {"new", "all", "top", "one", "two", "six", "ten", "and", "ver"}  # Common 3-letter words
VOWELS = set("aeiouy")


def _wordish(s: str) -> bool:
    """Check if a string looks like a word-shaped piece (has vowels, no weird clusters)."""
    s = s.lower()
    if not s.isalpha():
        return False
    if not any(c in VOWELS for c in s):
        return False
    # Reject long consonant clusters (sign of glued text)
    if re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", s):
        return False
    return True


def _valid_piece(p: str) -> bool:
    """Check if a piece is valid for a segmentation candidate.
    
    A piece is valid if it's a known joiner, or it's 4+ chars and word-shaped,
    or it's a whitelisted 3-letter word.
    """
    p = p.lower()
    if p in JOINERS_SET:
        return True
    if len(p) >= 4:
        return _wordish(p)
    if len(p) == 3 and p in COMMON3:
        return True
    return False


def _veto_embedded_short_joiner(left: str, joiner: str, right: str) -> bool:
    """Hard-veto embedded short joiners likely inside a real word.
    
    If joiner is short (to, in, of, an, by, a) and both sides are long (6+),
    it's almost certainly buried inside a real word like "territory".
    """
    short_joiners = {"to", "in", "of", "an", "by", "a"}
    return joiner in short_joiners and len(left) >= 6 and len(right) >= 6


def _segment_token(tok: str) -> str:
    """Segment a glued token into pieces split at joiner boundaries.
    
    One-shot, deterministic segmentation with three passes:
    1. Suffix joiner (territoryby -> territory by)
    2. Embedded 'a' (backalarge -> back a large)
    3. Embedded joiners with strict validation (greeninall -> green in all)
    
    No recursive splitting. All pieces must pass _valid_piece().
    """
    t = tok.lower()
    
    # Only process suspicious tokens
    if not (t.isalpha() and t.islower() and len(t) >= 8):
        return tok
    
    # PASS 0: Suffix joiner (highest precision, prevents embedded mistakes)
    for j in SUFFIX_JOINERS:
        if t.endswith(j) and len(t) > len(j) + 3:
            left = t[:-len(j)]
            cand = [left, j]
            if all(_valid_piece(x) for x in cand):
                return " ".join(cand)
    
    # PASS 1: Embedded 'a' pass (backalarge -> back a large)
    # Try all positions and prefer split with longest left side (most conservative)
    for i in range(len(t) - 4, 2, -1):  # Scan RIGHT to LEFT for longest left piece
        if t[i] != "a":
            continue
        left, right = t[:i], t[i + 1:]
        cand = [left, "a", right]
        if all(_valid_piece(x) for x in cand):
            return " ".join(cand)
    
    # PASS 2: Embedded joiners (the, and, for, to, in, of, an)
    # Try longer joiners first so "the" beats "he", etc.
    # Only accept if both pieces are clearly valid (stronger requirement than PASS 1)
    best = None
    embedded_joiners = ["the", "and", "for", "to", "in", "of", "an"]
    
    for j in embedded_joiners:
        jlen = len(j)
        for i in range(4, len(t) - 3):  # More conservative range (4+ and -3)
            if t[i:i+jlen] != j:
                continue
            
            left, right = t[:i], t[i+jlen:]
            
            # Veto: embedded short joiner inside long stems
            if _veto_embedded_short_joiner(left, j, right):
                continue
            
            # Special case: prefer "a" over "an" if remainder becomes junk
            if j == "an" and not _valid_piece(right):
                # Try alternative: left + "a" + ("n" + right)
                alt_right = "n" + right
                cand_alt = [left, "a", alt_right]
                if all(_valid_piece(x) for x in cand_alt):
                    return " ".join(cand_alt)
                continue
            
            # Both pieces must be valid
            if not (_valid_piece(left) and _valid_piece(j) and _valid_piece(right)):
                continue
            
            # Prefer split with longest left word (stability against over-splitting)
            score = len(left) + len(right)
            if best is None or score > best[0]:
                best = (score, " ".join([left, j, right]))
    
    if best:
        return best[1]
    
    return tok


def _deglue_joiners(text: str) -> str:
    """Apply rule-based de-gluing to text by segmenting suspicious tokens.
    
    For each token that looks glued (lowercase, long, all alphabetic), attempts
    to split it at known joiner points using deterministic, one-shot segmentation
    with strict piece validation.
    """
    toks = text.split()
    fixed = [_segment_token(t) for t in toks]
    return " ".join(fixed)






def _collapse_irregular_spacing(text: str) -> str:
    """
    Remove spaces from within fragmented words that PDFs extract incorrectly.
    
    PDFs often extract multi-character words as individual spaced fragments.
    This function identifies and fixes these patterns.
    
    Strategy: Identify patterns where single-character or short fragments are
    separated by spaces but belong together to form a word. This handles both
    lowercase fragments (common in glued text) and mixed-case fragments.
    
    Examples:
    - "mon ths" or "mont hs" -> "months"
    - "ne wc us to me rs" -> "newcustomers"  
    - "le ad in g" -> "leading"
    - "4 mont hs" -> "4months"
    - "cu st om er s" -> "customers"
    
    Args:
        text: Text potentially containing character-level fragmentation
        
    Returns:
        Text with fragmented words reassembled
    """
    if not text:
        return text
    
    # Pattern for fragmented words: short lowercase/letter sequences separated by spaces
    # This matches any word boundary followed by sequences of 1-2 character fragments
    # Examples: "ne wc us to me rs", "cu st om er s", "mon ths"
    def merge_fragments(match):
        """Merge fragmented parts of a word together."""
        fragment_str = match.group(0)
        # Remove spaces between letter fragments (case-insensitive)
        return re.sub(r'\s+(?=[a-zA-Z])', '', fragment_str)
    
    # Match sequences of short fragments (1-2 chars) separated by spaces
    # This pattern: (1-2 letters)(space)(1-2 letters)(space)... 
    # Requires at least 3 parts to avoid breaking normal text
    text = re.sub(r'[a-zA-Z]{1,2}(?:\s+[a-zA-Z]{1,2}){2,}', merge_fragments, text)
    
    # Also specifically handle number + month/year patterns broken across spaces
    # "5 mon ths" -> "5months", "4 mont hs" -> "4months"
    text = re.sub(r'(\d+)\s+([a-zA-Z])\s+([a-zA-Z]{2,})', r'\1\2\3', text)
    
    # Collapse any remaining multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text




def _fix_glued_lowercase_text(text: str) -> str:
    """
    Fix common concatenated words in PDF-extracted text where spaces between lowercase words are lost.
    
    Designed for achievement bullets extracted from PDFs where spaces get lost between words.
    Uses a conservative multi-pass approach:
    1. Split on unambiguous long words (customers, business, achieved, acquired)
    2. Split on medium words (months, leading, years, etc.)
    3. Handle "in" boundaries after specific words (plan, months, year) - BEFORE splitting "new"
    4. Handle "new" boundaries
    5. Handle "to" boundaries (before specific words like "plan")
    
    Examples:
    - "newcustomersin" -> "new customers in"
    - "monthsinanewrole" -> "months in a new role"
    - "toplaninnewbusiness" -> "to plan in new business"
    """
    if not text:
        return text
    
    # Pass 1: Very long words (8+ chars) - unambiguous when surrounded by text
    text = re.sub(r'([a-z]+)(customers)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(business)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(achieved)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(acquired)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    
    # Pass 2: Medium-long words (6-7 chars) - split when surrounded by lowercase
    text = re.sub(r'([a-z]+)(months)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(leading)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(through)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(years)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(after)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(just)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]+)(growth)([a-z]+)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    
    # Pass 3: "in" after specific words - BEFORE splitting "new" so patterns can match
    # Only split these words when followed by "in": plan, months, year
    # This avoids breaking natural words like "creating", "leading", "business", etc.
    text = re.sub(r'(plan)(in)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(months)(in)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(month)(in)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(year)(in)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(years)(in)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    
    # Pass 4: "new" boundaries - split "new" when between lowercase text
    text = re.sub(r'(a)(new)([a-z]{2,})', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z]{2,})(new)([a-z]{2,})', r'\1 \2 \3', text, flags=re.IGNORECASE)
    # Also handle "new" + "business" directly (for patterns like "newbusiness")
    text = re.sub(r'(new)(business)', r'\1 \2', text, flags=re.IGNORECASE)
    
    # Pass 5: "to" before specific words - carefully targeted to avoid false positives
    # Split "plan" + "to", but be careful not to match inside other words
    text = re.sub(r'(plan)(to)([a-z])', r'\1 \2 \3', text, flags=re.IGNORECASE)
    # Also handle patterns like "toplan" that come from "to plan" (after non-letter)
    text = re.sub(r'([^a-z])(to)(plan)', r'\1\2 \3', text, flags=re.IGNORECASE)
    # Handle spacing after percent sign before "to"
    text = re.sub(r'(%)(to)', r'\1 \2', text, flags=re.IGNORECASE)
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


def _add_spaces_to_text(text: str) -> str:
    """
    Add spaces in common patterns where PDF extraction removes them.
    
    Examples:
    - "NewYork,NewYork" -> "New York, New York"
    - "TERRITORYMANAGER" -> "TERRITORY MANAGER"
    - "ACMECORP:TERRITORYMANAGER:NEWYORK" -> "ACME CORP: TERRITORY MANAGER: NEW YORK"
    - "January2024" -> "January 2024"
    """
    # First, handle camelCase patterns (lowercase -> uppercase boundary)
    # This handles cases like "NewYork" -> "New York" or "TERRITORYMANAGER" -> "TERRITORY MANAGER"
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Handle digit-letter boundaries: "January2024" -> "January 2024"
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    
    # Punctuation spacing: add space after colon/comma if missing
    # This handles "NEODENT:TERRITORY" -> "NEODENT: TERRITORY"
    text = re.sub(r':([A-Z])', r': \1', text)
    
    # Pattern: Comma followed directly by a capital letter (no space)
    # This handles cases like ",California" -> ", California"
    text = re.sub(r',([A-Z])', r', \1', text)
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


def _words_to_text(page: Any, *, x_tolerance: float = 3, y_tolerance: float = 2, line_y_tolerance: float = 3, use_text_flow: bool = True) -> str:
    """
    Extract text from a PDF page using word objects with smart spacing.
    
    Groups words by vertical position (y-coordinate), then joins them with single spaces.
    This avoids the glued-word and over-spaced-word problems of layout-based extraction.
    
    Args:
        page: pdfplumber page object
        x_tolerance: Distance tolerance for grouping words horizontally (higher = more gluing)
        y_tolerance: Distance tolerance for vertical grouping (ignored, word-level)
        line_y_tolerance: Distance tolerance for grouping words into lines (higher = more line mixing)
        use_text_flow: Whether to use text flow ordering
    
    Returns:
        Text with properly spaced lines
    """
    words = page.extract_words(
        x_tolerance=x_tolerance,
        y_tolerance=y_tolerance,
        keep_blank_chars=False,
        use_text_flow=use_text_flow,
    )

    if not words:
        return ""

    # Group words into lines by 'top' (y) coordinate
    words.sort(key=lambda w: (round(w["top"] / line_y_tolerance), w["x0"]))
    lines = []
    current_key = None
    current_words = []

    for w in words:
        key = round(w["top"] / line_y_tolerance)
        if current_key is None or key == current_key:
            current_words.append(w["text"])
            current_key = key
        else:
            lines.append(" ".join(current_words))
            current_words = [w["text"]]
            current_key = key

    if current_words:
        lines.append(" ".join(current_words))

    return "\n".join(lines)


def _score_text(s: str) -> float:
    """
    Score extracted text quality to detect over-gluing and over-spacing.
    
    Penalizes:
    - Very long alphabetic tokens (18+ chars) = glued words
    - Excessive single-letter tokens beyond legitimate words
    - Empty text
    
    Legitimate single letters (a, I, Q) are allowed.
    
    Args:
        s: Extracted text to score
    
    Returns:
        Score (lower is better)
    """
    tokens = re.findall(r"[A-Za-z]+", s)
    if not tokens:
        return 1e9
    
    # Count glued words (18+ chars indicates concatenated words)
    long_glued = sum(1 for t in tokens if len(t) >= 18)
    
    # Count excessive single-letter tokens beyond legitimate words
    # Legitimate: a, I, Q (and maybe others), but more than ~5 in a resume is fragmentation
    one_letter_count = sum(1 for t in tokens if len(t) == 1)
    excessive_singles = max(0, one_letter_count - 10)  # Allow up to 10 legitimate single letters
    
    return long_glued * 10 + excessive_singles * 3 + (len(s) == 0) * 50


def _extract_best(page: Any, *, x_tolerance_range: List[float] = None) -> Tuple[str, float, float]:
    """
    Auto-tune x_tolerance to minimize text extraction artifacts.
    
    Tries multiple x_tolerance values and picks the one with the best quality score.
    
    Args:
        page: pdfplumber page object
        x_tolerance_range: List of x_tolerance values to try (default: [1.5, 2, 2.5, 3])
    
    Returns:
        Tuple of (best_text, best_x_tolerance, best_score)
    """
    if x_tolerance_range is None:
        x_tolerance_range = [1.5, 2, 2.5, 3]  # Tighter range for better quality
    
    candidates = []
    for xt in x_tolerance_range:
        txt = _words_to_text(page, x_tolerance=xt, y_tolerance=2, line_y_tolerance=3, use_text_flow=True)
        candidates.append((_score_text(txt), xt, txt))
    
    candidates.sort(key=lambda x: x[0])
    best_score, best_xt, best_txt = candidates[0]
    
    return best_txt, best_xt, best_score


def extract_pdf_lines(pdf_bytes: bytes) -> List[Tuple[str, str]]:
    """
    Deterministically extract text lines from a PDF using word-level extraction.

    Strategy:
    1) Extract word objects with tuned x_tolerance to minimize gluing/splitting
    2) Group words by vertical position (y-coordinate) into lines
    3) Join words with single spaces
    4) Apply conservative de-gluing for common joiners (to, in, of, etc.)
    5) Apply additional post-processing for remaining patterns
    
    This approach avoids the glued-word and character-fragmentation problems
    of layout-based extraction by solving spacing issues at the source.
    """
    out: List[Tuple[str, str]] = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_i, page in enumerate(pdf.pages, start=1):
            # Auto-tune x_tolerance for this page to minimize artifacts
            text, used_x_tol, score = _extract_best(page)

            # Split on real line breaks
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            for line_i, line in enumerate(lines, start=1):
                # Apply conservative de-gluing for common joiners
                line = _deglue_joiners(line)
                # Apply additional post-processing for remaining patterns
                line = _add_spaces_to_text(line)
                out.append(
                    (f"pdf:page:{page_i}:line:{line_i}", line)
                )

    return out

