"""
Text normalization utilities for cleaning up PDF/DOCX extraction artifacts.

Handles glued words, irregular spacing, and CamelCase boundaries common in resume PDFs.
Two levels of aggressiveness:
- normalize_token_basic(): ultra-conservative, safe everywhere
- normalize_bullet_text(): richer pipeline for achievement/bullet text
"""

import re
from typing import Optional


# ============================================================================
# Email/Protected pattern detection
# ============================================================================

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_FLEX_RE = re.compile(r"([^\s@]+(?:\s+[^\s@]+)*)\s*(@)\s*([^\s@]+(?:\s+[^\s@]+)*)\s*\.\s*([A-Za-z]{2,})")


def extract_email_flexible(text: str) -> Optional[str]:
    """
    Extract email from text, handling accidental spaces around @, ., and within user/domain.
    
    Examples:
    - "annaford0719@gmail.com" → "annaford0719@gmail.com"
    - "annaford 0719@gmail.com" → "annaford0719@gmail.com"
    - "annaford0719 @ gmail . com" → "annaford0719@gmail.com"
    - "anna ford@gm ail.com" → "annaford@gmail.com"
    
    REJECTS phone+email concatenations:
    - "(856)366-5713k.o.harbaugh@gmail.com" → None (user part looks like phone)
    """
    if not text:
        return None
    
    def _user_looks_like_phone(user: str) -> bool:
        """Check if user portion looks like a phone number."""
        digit_count = sum(1 for c in user if c.isdigit())
        has_parens = "(" in user or ")" in user
        has_plus = user.startswith("+")
        # Phone-like: many digits + hyphens, or parens, or +
        has_digits_and_hyphens = digit_count >= 7 and "-" in user
        
        return has_parens or has_plus or has_digits_and_hyphens
    
    # Try flexible pattern first (handles spaces around @ and . and within parts)
    m = EMAIL_FLEX_RE.search(text)
    if m:
        user = m.group(1).replace(" ", "")
        domain = m.group(3).replace(" ", "")
        tld = m.group(4).replace(" ", "")
        
        if not _user_looks_like_phone(user):
            return f"{user}@{domain}.{tld}"
    
    # Fallback: normal strict email pattern (requires @ with no spaces, excludes parens/phone chars)
    # Match: alphanumeric._%+- before @, then domain.tld, no parens allowed
    m2 = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if m2:
        user = m2.group(0).split("@")[0]
        if not _user_looks_like_phone(user):
            return m2.group(0)
    
    return None


def _is_protected_token(tok: str) -> bool:
    """Check if token should be protected from normalization (e.g., emails)."""
    if "@" in tok:
        return True
    if EMAIL_RE.match(tok):
        return True
    return False


# ============================================================================
# Constants: Common glue patterns in resume text
# ============================================================================

JOINER_SUFFIX_PHRASES = [
    ("inthe", "in the"),
    ("ofthe", "of the"),
    ("tobe", "to be"),
    ("toa", "to a"),
    ("tothe", "to the"),
    ("andthe", "and the"),
]

JOINER_PREFIX_PHRASES = [
    ("dueto", "due to"),
    ("leadingto", "leading to"),
    ("setthe", "set the"),
]

EMBEDDED_JOINERS = ["the", "and", "for", "to", "in", "of"]
SHORT_JOINERS = {"to", "in", "of", "an", "a"}

# Whitelisted 3-letter words that shouldn't be split
COMMON3 = {"new", "all", "top", "one", "two", "six", "ten", "ver", "and", "the", "for"}
VOWELS = set("aeiouy")

# Words commonly seen after "a" in resume bullets
A_RIGHT_WHITELIST = {"new", "large", "positive", "can", "role", "territory", "team", "month", "year"}

# Short words commonly appear as left side of "a" in achievements
A_LEFT_WHITELIST = {"back", "won", "grew", "built", "led", "sold", "took"}

# Resume-domain common words for glue evidence checks
# Used to detect if a split is evidence of genuine glued text (not a real single word)
COMMON_WORDS = {
    "back", "large", "new", "role", "team", "month", "year", "account", "territory",
    "sales", "growth", "customers", "business", "country", "attend", "miami", "symposium",
    "conference", "leader", "expand", "market", "client", "revenue", "product", "service"
}

# Bullet-only exact fixes (highest precision)
EXACT_TOKEN_FIXES = {
    "selectedas": "selected as",
    "focusin": "focus in",
    "growthin": "growth in",
    "greeninall": "green in all",
    "expansionand": "expansion and",
    "over-executedonboth": "over-executed on both",
    "maintainingapositive": "maintaining a positive",
    "apositive": "a positive",
    "foranoverall": "for an overall",
    "personofthe": "person of the",
    "girlsofthe": "girls of the",
    "toolstobe": "tools to be",
}

MERGE_2_WHITELIST = {"newspaper", "expansion", "bulletin"}
MERGE_3_PREFIX_WHITELIST = {
    "maintaining",
    "increasing",
    "developing",
    "implementing",
    "managing",
}


# ============================================================================
# Validation helpers
# ============================================================================

def _has_vowels(s: str) -> bool:
    """Check if string has any vowels."""
    return any(c.lower() in VOWELS for c in s)


def _is_wordish(s: str) -> bool:
    """Check if string looks like a word (has vowels, no extreme consonant clusters)."""
    s = s.lower()
    if not s.isalpha():
        return False
    if not _has_vowels(s):
        return False
    # Reject long consonant clusters (sign of glued text)
    if re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", s):
        return False
    return True


def _strong_word(s: str) -> bool:
    """Check if string is a strong, recognizable word.
    
    Stricter than _is_wordish:
    - 5+ chars (substantial length)
    - 2+ vowels (filters fragments like 'ttend', 'kickst')
    - No long consonant clusters
    """
    s = s.lower()
    if not s.isalpha():
        return False
    if len(s) < 5:
        return False
    # Require 2+ vowels for substance
    vowel_count = sum(1 for c in s if c in VOWELS)
    if vowel_count < 2:
        return False
    # No extreme consonant clusters
    if re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", s):
        return False
    return True


def _glue_evidence(left: str, right: str) -> bool:
    """Check if a left|right split shows evidence of genuine glued text.
    
    Returns True if at least one side is a common word or whitelisted.
    This prevents false splits of real single words.
    
    Examples:
    - "back" | "large" → True (both in COMMON_WORDS)
    - "foo" | "bar" → False (neither is recognized)
    - "territory" | "over" → True (territory is in COMMON_WORDS)
    """
    l = left.lower()
    r = right.lower()
    return (l in COMMON_WORDS) or (r in COMMON_WORDS) or (l in A_LEFT_WHITELIST) or (r in A_RIGHT_WHITELIST)


def _is_valid_piece(p: str) -> bool:
    """Check if a piece is valid for segmentation."""
    p_lower = p.lower()
    # Joiners are always valid
    if p_lower in ("a", "an", "to", "in", "of", "for", "and", "the", "by", "on", "at", "or", "as", "is"):
        return True
    # 4+ chars and word-shaped
    if len(p) >= 4 and _is_wordish(p):
        return True
    # Whitelisted 3-letter words
    if len(p) == 3 and p_lower in COMMON3:
        return True
    return False


def _apply_to_subtokens(s: str, fn) -> str:
    """Apply a token-level function to each space-delimited subtoken in a possibly multi-token string."""
    parts = s.split()
    parts = [fn(p) for p in parts]
    return " ".join(parts)


# ============================================================================
# Step 0: Exact token fixes and list-level merges
# ============================================================================

def _apply_exact_token_fixes(tok: str) -> str:
    """Apply bullet-only exact token fixes (highest precision)."""
    low = tok.lower()
    fixed = EXACT_TOKEN_FIXES.get(low)
    if not fixed:
        return tok
    # Preserve capitalization: if original was capitalized, capitalize fixed version
    if tok[:1].isupper():
        fixed = fixed[:1].upper() + fixed[1:]
    return fixed


def _merge_two_tokens(tokens: list[str]) -> list[str]:
    """Merge two adjacent tokens if their combination is in MERGE_2_WHITELIST.
    
    Handles artifacts like 'New spaper' -> 'Newspaper'.
    """
    out = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            a, b = tokens[i], tokens[i + 1]
            combo = (a + b).lower()
            if combo in MERGE_2_WHITELIST:
                merged = a + b
                # Preserve capitalization: if first token capitalized, capitalize result
                if a[:1].isupper():
                    merged = merged[:1].upper() + merged[1:]
                out.append(merged)
                i += 2
                continue
        out.append(tokens[i])
        i += 1
    return out


def _merge_three_tokens(tokens: list[str]) -> list[str]:
    """Merge three tokens if they form a word in MERGE_3_PREFIX_WHITELIST.
    
    Handles split-inside-a-word artifacts like 'mainta in ing' -> 'maintaining'.
    Only merges if middle token is short (<=2 chars) and lowercase-ish.
    """
    out = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens):
            a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
            # Middle token must be tiny and lowercase-ish (e.g., 'in', 'a')
            if len(b) <= 2 and b.islower():
                merged = (a + b + c).lower()
                # Check if merged matches any prefix in whitelist
                for w in MERGE_3_PREFIX_WHITELIST:
                    if merged.startswith(w):
                        # Preserve capitalization from first token
                        result_word = w.capitalize() if a[:1].isupper() else w
                        out.append(result_word)
                        # Add remainder if any
                        remainder = (a + b + c)[len(w):]
                        if remainder:
                            out.append(remainder)
                        i += 3
                        break
                else:
                    # No match, just append first token
                    out.append(tokens[i])
                    i += 1
                continue
        out.append(tokens[i])
        i += 1
    return out


def _merge_single_letter_splits(tokens: list[str]) -> list[str]:
    """Merge 3-token sequences where middle is a single letter: communic a tions → communications.
    
    Very constrained guard:
    - All three tokens are alphabetic
    - Middle token is exactly 1 letter
    - Left is ≥ 4 chars, right is ≥ 3 chars
    - Combined is ≥ 8 chars and looks wordish
    """
    out = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens):
            a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
            # All three alphabetic, middle is single letter
            if a.isalpha() and c.isalpha() and b.isalpha() and len(b) == 1:
                # Left ≥ 4, right ≥ 3
                if len(a) >= 4 and len(c) >= 3:
                    merged = a + b + c
                    # Merged must be ≥ 8 chars and look like a real word
                    if len(merged) >= 8 and _is_wordish(merged.lower()):
                        out.append(merged)
                        i += 3
                        continue
        out.append(tokens[i])
        i += 1
    return out


def _merge_letter_number_pairs(tokens: list[str]) -> list[str]:
    """Merge letter-number pairs: Q 1 → Q1, FY 2022 → FY2022.
    
    Currently handles:
    - Q + (1-2 digit number, optionally with trailing punctuation) → Q1, Q2, Q3, Q4
    """
    out = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            a, b = tokens[i], tokens[i + 1]
            # Q + digit(s), optionally with trailing punctuation
            if a.upper() == "Q" and re.match(r"\d{1,2}[,.\-]*$", b):
                # Extract digits and preserve trailing punctuation
                digit_match = re.match(r"(\d{1,2})(.*)", b)
                if digit_match:
                    digits, trailing = digit_match.groups()
                    merged = "Q" + digits + trailing
                    out.append(merged)
                    i += 2
                    continue
        out.append(tokens[i])
        i += 1
    return out


# ============================================================================
# Step 1: Explicit special cases (highest precision)
# ============================================================================

def _fix_inanew(tok: str) -> str:
    """Fix 'inanew' and 'anew' patterns."""
    low = tok.lower()
    if low == "anew":
        return "a new"
    if low == "inanew":
        return "in a new"
    return tok


def _fix_startanew(tok: str) -> str:
    """Fix 'startanew' pattern."""
    if tok.lower() == "startanew":
        return "start a new"
    return tok


def _fix_leadingto(tok: str) -> str:
    """Fix 'leadingto' as standalone token."""
    if tok.lower() == "leadingto":
        return "leading to"
    return tok


def _fix_dueto(tok: str) -> str:
    """Fix 'dueto' as standalone token."""
    if tok.lower() == "dueto":
        return "due to"
    return tok


# ============================================================================
# Step 2: Suffix phrase fixes (e.g., salesinthe)
# ============================================================================

def _split_suffix_phrases(tok: str) -> str:
    """Peel off suffix phrases like 'inthe', 'ofthe', 'tobe'."""
    low = tok.lower()
    for suf, repl in JOINER_SUFFIX_PHRASES:
        if low.endswith(suf) and len(low) >= len(suf) + 4:  # >= not >, and 4+ chars before suffix
            left = tok[:-len(suf)]
            # left must be plausible
            if _is_valid_piece(left.lower()):
                return f"{left} {repl}"
    return tok


# ============================================================================
# Step 3: Prefix phrase fixes (e.g., duetoa, leadingto)
# ============================================================================

def _split_prefix_phrases(tok: str) -> str:
    """Handle prefix phrases like 'dueto', 'leadingto'."""
    low = tok.lower()
    for pre, repl in JOINER_PREFIX_PHRASES:
        if low.startswith(pre) and len(low) > len(pre):  # Just need to have something after prefix
            rest = tok[len(pre):]
            # Don't recurse; return and let caller apply pipeline again if needed
            return f"{repl} {rest}"
    return tok


# ============================================================================
# Step 3.5: Embedded 'a' fixes (e.g., backalarge -> back a large)
# ============================================================================

def _try_embedded_a(tok: str) -> Optional[str]:
    """Try to split on embedded 'a', with pragmatic glue-evidence guards.
    
    Returns the split string if found, None otherwise.
    
    Only splits if:
    - Token contains an 'a' in the middle
    - Split produces two plausible pieces
    - At least one piece is a recognized/common word (glue evidence)
    - Right side isn't garbage (short + consonant-starting + uncommon)
    """
    t = tok.lower()
    
    # Only process suspicious-looking tokens
    if not (t.isalpha() and len(t) >= 8):
        return None
    
    # Scan right-to-left for 'a' positions (prefer longer left piece)
    for i in range(len(t) - 4, 3, -1):
        if t[i] != "a":
            continue
        
        left = t[:i]
        right = t[i + 1:]
        
        # 1) Don't solve joiner cases here (let embedded-joiner logic handle)
        if left.endswith(("to", "of", "in", "by", "for")):
            continue
        
        # 2) Left must be strong OR whitelisted
        if not (_strong_word(left) or left in A_LEFT_WHITELIST):
            continue
        
        # 3) Right must be strong OR whitelisted OR (4+ chars, vowel-starting, wordish)
        right_ok = (
            _strong_word(right) or
            right in A_RIGHT_WHITELIST or
            (len(right) >= 4 and right[0] in VOWELS and _is_wordish(right))
        )
        if not right_ok:
            continue
        
        # 4) GLUE EVIDENCE: At least one side must be recognized (not just a strong word)
        # This prevents splitting random single words that happen to contain 'a'
        if not _glue_evidence(left, right):
            continue
        
        # 5) Avoid junk right pieces: short + consonant-starting + uncommon
        if len(right) < 5 and right[0].lower() not in VOWELS and right.lower() not in COMMON_WORDS:
            continue
        
        # Found a valid split! Return with original casing preserved
        return f"{tok[:i]} a {tok[i + 1:]}"
    
    return None


# ============================================================================
# Step 4: Embedded joiner fixes (single pass, conservative)
# ============================================================================

def _split_embedded_joiner_once(tok: str) -> str:
    """Split on embedded joiners like 'territorytoover' -> 'territory to over'.
    
    Uses strong vetoes to avoid false positives like 'terri|to|ry'.
    Conservative: Only splits tokens 13+ chars with substantial pieces (5+ each side).
    Veto: only prevents splits where BOTH sides are 7+ chars (prevents real words like "territory").
    """
    low = tok.lower()
    
    # Don't touch short tokens or non-alphabetic
    if len(low) < 13 or not low.isalpha():
        return tok
    
    best = None
    for j in EMBEDDED_JOINERS:
        jlen = len(j)
        for i in range(5, len(low) - 5):
            if low[i:i+jlen] != j:
                continue
            
            left = tok[:i]
            right = tok[i+jlen:]
            left_low = left.lower()
            right_low = right.lower()
            
            # Hard veto: short joiner with BOTH sides very long (7+) - indicates single word like "territory"
            # But allow splits like "country|to|attend" where right is 6 chars
            if j in SHORT_JOINERS and len(left_low) >= 7 and len(right_low) >= 7:
                continue
            
            # Both pieces must be valid
            if not (_is_valid_piece(left_low) and _is_valid_piece(right_low)):
                continue
            
            # Prefer split with longest left (stability)
            score = len(left)
            cand = f"{left} {j} {right}"
            if best is None or score > best[0]:
                best = (score, cand)
    
    return best[1] if best else tok


# ============================================================================
# Step 5: CamelCase boundary fixes
# ============================================================================

def _split_camel_joiner(tok: str) -> str:
    """Fix CamelCase boundaries where joiner is at boundary.
    
    Examples:
    - SymposiuminMiami -> Symposium in Miami (after this + later steps)
    - growthinQ -> growth in Q
    """
    # Look for lowercase->Uppercase transition
    m = re.search(r"([a-z])([A-Z])", tok)
    if not m:
        return tok
    
    i = m.start(2)
    left = tok[:i]
    right = tok[i:]
    left_low = left.lower()
    
    # Only split if left ends with a joiner or is substantial
    if left_low.endswith(("in", "to", "of", "and", "for")):
        return f"{left} {right}"
    
    # Or if left is quite long (likely a word before the boundary)
    if len(left) >= 7 and _is_wordish(left_low):
        return f"{left} {right}"
    
    return tok


# ============================================================================
# Public API
# ============================================================================

def normalize_token_basic(token: str) -> str:
    """
    Ultra-conservative token normalization, safe to apply everywhere.
    
    Handles:
    - inanew / anew
    - startanew / leadingto / dueto (standalone tokens)
    - Suffix phrases (salesinthe, etc.)
    
    No recursion; applied once per token.
    
    Protected tokens (emails, etc.) are returned unchanged.
    """
    # GUARD: Protect emails from normalization
    if _is_protected_token(token):
        return token
    
    # Step 1: Explicit special cases
    tok = _fix_inanew(token)
    if tok != token:
        return tok
    
    tok = _fix_startanew(token)
    if tok != token:
        return tok
    
    tok = _fix_leadingto(token)
    if tok != token:
        return tok
    
    tok = _fix_dueto(token)
    if tok != token:
        return tok
    
    # Step 2: Suffix phrases
    tok = _split_suffix_phrases(token)
    if tok != token:
        return tok
    
    return token


def normalize_field_text(text: str) -> str:
    """
    Safe normalization for structured fields (job_title, company, location).
    
    Minimal scope: Only fixes split-inside-a-word patterns like "communicati on" → "communication".
    Does NOT apply aggressive joiner splitting (avoids corrupting names/places).
    
    Handles:
    - "communicati on" → "communication"
    - "communicati ons" → "communications"
    - "communic a tions" → "communications"
    """
    if not text or not text.strip():
        return text
    
    tokens = text.split()
    
    # 2-token merge: communication(s) family
    out = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            a, b = tokens[i], tokens[i + 1]
            if a.isalpha() and b.isalpha():
                combo = (a + b).lower()
                # Safe whitelist: communication(s) family only
                if combo in {"communication", "communications"}:
                    merged = a + b
                    out.append(merged)
                    i += 2
                    continue
        out.append(tokens[i])
        i += 1
    
    # 3-token merge: "communic a tions" → "communications"
    final = []
    i = 0
    while i < len(out):
        if i + 2 < len(out):
            a, b, c = out[i], out[i + 1], out[i + 2]
            if a.isalpha() and b.isalpha() and c.isalpha() and len(b) == 1:
                combo = (a + b + c).lower()
                if combo in {"communications"}:
                    merged = a + b + c
                    final.append(merged)
                    i += 3
                    continue
        final.append(out[i])
        i += 1
    
    return " ".join(final)


def normalize_bullet_text(text: str) -> str:
    """
    Rich normalization pipeline for achievement/bullet text.
    
    Upgraded approach:
    - List-level passes FIRST for split-inside-a-word artifacts
    - Per-token rules with safe subtoken reapplication
    - Exact token fixes for high-precision resume-specific patterns
    - Protected token guards for emails and other sensitive patterns
    
    Pipeline:
    0. List-level merges (in order):
       - 2-token merges (New spaper → Newspaper)
       - 3-token whitelist merges (mainta in ing → maintaining)
       - Single-letter split merges (communic a tions → communications)
       - Letter-number pair merges (Q 1 → Q1)
    1. Bullet-only exact token fixes
    2. Basic normalization with protected token guard
    3-8. Per-token pipeline with protected token guard
    """
    if not text or not text.strip():
        return text
    
    tokens = text.split()
    
    # List-level repairs FIRST (fixes split-inside-a-word before per-token rules)
    tokens = _merge_two_tokens(tokens)
    tokens = _merge_three_tokens(tokens)
    tokens = _merge_single_letter_splits(tokens)
    tokens = _merge_letter_number_pairs(tokens)
    
    result: list[str] = []
    
    for token in tokens:
        # GUARD: Protect emails and tokens with @ from normalization
        if _is_protected_token(token):
            result.append(token)
            continue
        
        norm = token
        
        # Step 0: Bullet-only exact fixes (highest precision)
        norm = _apply_exact_token_fixes(norm)
        
        # Step 1: Basic normalization
        norm = normalize_token_basic(norm)
        
        # Step 2: Suffix phrases
        if norm == token:
            norm = _split_suffix_phrases(norm)
        else:
            # norm has changed, safely apply to subtokens
            norm = _apply_to_subtokens(norm, _split_suffix_phrases)
        
        # Step 3: Prefix phrases (safe subtoken reapplication when norm has spaces)
        if norm == token:
            norm = _split_prefix_phrases(norm)
        else:
            norm = _apply_to_subtokens(norm, _split_prefix_phrases)
        
        # Step 4: Embedded joiners (high precision, single-token only)
        if norm == token:
            norm = _split_embedded_joiner_once(norm)
        
        # Step 5: Embedded 'a' (only if joiner didn't match)
        if norm == token:
            split_result = _try_embedded_a(norm)
            if split_result is not None:
                norm = split_result
        
        # Step 6: CamelCase (apply to subtokens if norm has spaces)
        norm = _apply_to_subtokens(norm, _split_camel_joiner)
        
        # Step 7: Re-run suffix phrases on subtokens (catches newly exposed patterns)
        norm = _apply_to_subtokens(norm, _split_suffix_phrases)
        
        result.append(norm)
    
    return " ".join(result)
