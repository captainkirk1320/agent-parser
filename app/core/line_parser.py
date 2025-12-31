from typing import Dict, List, Tuple, Optional
import re
import logging
from app.core.confidence_calculator import ConfidenceCalculator
from app.core.schemas import EvidenceItem, FieldConfidence, EducationEntry
from app.core.pdf_extractor import _fix_glued_lowercase_text, _collapse_irregular_spacing
from app.core.text_normalization import normalize_bullet_text, normalize_field_text, extract_email_flexible

logger = logging.getLogger(__name__)

# Common English words for word-segmentation fallback (most frequent words in professional context)
COMMON_WORDS = {
    "the", "a", "and", "to", "of", "in", "for", "is", "was", "on", "with", "by", "from",
    "as", "at", "be", "been", "that", "this", "it", "which", "who", "or", "an", "have",
    "has", "had", "are", "were", "new", "large", "back", "key", "account", "manager",
    "leader", "team", "sales", "customer", "territory", "grew", "growth", "won", "selected",
    "opened", "acquired", "finished", "performed", "transferred", "outperformed", "percent",
    "plan", "business", "year", "month", "due", "to", "leading", "over", "goals",
    "while", "always", "maintaining", "positive", "volunteer", "group", "girls", "boys",
    "teaching", "encouraging", "strong", "smart", "bold", "blitz", "expansion", "relations",
    "set", "tone", "overall", "atmosphere", "can", "do", "attitude", "case", "coast",
    "person", "june", "q", "west", "several", "national", "major", "downtown", "near",
    "relationship", "through", "develop", "improve", "increase", "decrease", "change", "led",
    "lead", "create", "created", "develop", "delivery", "managed", "manage", "led", "lead",
    "up", "down", "new", "implemented", "implement", "provide", "provided", "business",
    "process", "system", "quality", "customer", "service", "support", "training", "develop",
    "staff", "office", "regional", "company", "corporation", "division", "department",
    "responsible", "responsibilities", "achievement", "achievements", "accomplishment",
    "results", "result", "success", "successful", "successfully", "recognition", "award",
    "awards", "promoted", "promotion", "increase", "increased", "growth", "expand",
    "partnership", "partner", "collaborate", "collaboration", "initiative", "strategic",
    "strategy", "market", "marketing", "sales", "revenue", "profit", "efficiency",
    "effective", "effectiveness", "productivity", "product", "production", "quality",
    "implementation", "implemented", "launch", "launched", "innovation", "innovative",
    "technology", "technical", "operational", "operations", "logistics", "supply",
    "chain", "sourcing", "procurement", "vendor", "suppliers", "client", "clients",
    "prospecting", "pipeline", "closing", "negotiation", "negotiated", "contract",
    "proposal", "proposals", "presentations", "presentation", "training", "trained",
    "coaching", "mentoring", "mentored", "development", "developed", "improved",
    "reduced", "reduction", "optimized", "optimization", "streamlined", "streamline",
    "automated", "automation", "platform", "solution", "solutions", "integration",
    "integrated", "scaling", "scaled", "migration", "migrated", "modernization",
    "infrastructure", "deployment", "deployed", "maintenance", "support", "troubleshooting",
    "problem", "solving", "resolution", "incident", "security", "compliance", "risk",
    "management", "project", "program", "portfolio", "governance", "stakeholder",
    "stakeholders", "communication", "communication", "reporting", "analysis", "analytical",
    "datadriven", "metrics", "kpi", "kpis", "benchmark", "benchmarking", "forecast",
    "forecasting", "budget", "budgeting", "financial", "profitability", "roe", "roi",
    "valuation", "return", "investment", "capital", "funding", "investor", "venture",
    "startup", "scalable", "scalability", "sustainable", "sustainability", "corporate",
    "enterprise", "b2b", "b2c", "saas", "cloud", "on", "premise", "hybrid", "mobile",
    "web", "desktop", "application", "applications", "api", "apis", "database", "databases",
    "storage", "server", "servers", "network", "networking", "cloud", "aws", "azure",
    "gcp", "docker", "kubernetes", "agile", "scrum", "kanban", "devops", "ci", "cd",
    "testing", "test", "qa", "quality", "assurance", "ux", "ui", "design", "designer",
    "frontend", "backend", "fullstack", "architect", "architecture", "microservices",
    # Month names
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    # Common location words and proper nouns
    "diego", "francisco", "angeles", "york", "chicago", "denver", "denver",
    "boston", "atlanta", "seattle", "austin", "diego", "diego",
    # Common verbs for achievements
    "kick", "start", "kickstart", "grew", "grow", "achieved", "achieve",
}

SPACED_CHARS_RE = re.compile(r"^(?:[A-Za-z0-9@.()\-\+]\s+){2,}[A-Za-z0-9@.()\-\+]+$")

def _despace_if_needed(text: str) -> str:
    """
    Fix PDFs that extract text with spaces between characters.

    Examples:
      'E X P E R I E N C E' -> 'EXPERIENCE'
      'J O H N   D O E' -> 'JOHN DOE'   (preserves word boundary)
      '5 5 5 . 1 2 3 . 4 5 6 7' -> '555.123.4567'
    """
    t = text.strip()
    if not t:
        return t

    # Only apply when the line is mostly single characters separated by spaces
    if SPACED_CHARS_RE.match(t):
        # Split on 2+ spaces (treat as word boundaries), then remove remaining spaces inside each part
        parts = re.split(r"\s{2,}", t)
        parts = ["".join(p.split()) for p in parts]  # remove all whitespace inside each part
        return " ".join([p for p in parts if p])

    return t

NO_SPACE_PUNCT_RE = re.compile(r"([,;/\|\(\)\[\]])")
LETTER_DIGIT_BOUNDARY_RE = re.compile(r"([A-Za-z])(\d)|(\d)([A-Za-z])")
CAMEL_BOUNDARY_RE = re.compile(r"([a-z])([A-Z])")


def _normalize_for_search(text: str) -> str:
    """
    Used ONLY for matching/detection. Evidence must remain original.
    Goal: make awful PDF-extracted strings searchable.

    Examples:
      'NewYork,NewYork' -> 'New York, New York'
      'john.doe@example.com5551234567' -> 'john.doe@example.com 555.123.4567'
      'TERRITORYMANAGER' -> 'TERRITORY MANAGER'
      'SGIRLSINCOFTHEPACIFICNORTHWEST' -> 'S GIRLS INC OF THE PACIFIC NORTHWEST'
    """
    t = _despace_if_needed(text.strip())
    if not t:
        return t

    # Un-glue all-caps job title patterns (TERRITORYMANAGER -> TERRITORY MANAGER)
    # Look for common job title words that got glued
    job_title_patterns = [
        (r"TERRITORY([A-Z])", r"TERRITORY \1"),  # TERRITORYMANAGER -> TERRITORY MANAGER
        (r"MANAGER([A-Z])", r"MANAGER \1"),      # MANAGERREGON -> MANAGER REGION
        (r"KEY([A-Z])", r"KEY \1"),              # KEYACCOUNTMANAGER -> KEY ACCOUNT...
        (r"ACCOUNT([A-Z])", r"ACCOUNT \1"),      # ACCOUNTMANAGER -> ACCOUNT MANAGER
        (r"GROUP([A-Z])", r"GROUP \1"),          # GROUPLEADER -> GROUP LEADER
        (r"([A-Z])OF([A-Z])", r"\1 OF \2"),     # SOFTTHEPACIFIC -> S OF THEPACIFIC
    ]
    for pattern, replacement in job_title_patterns:
        t = re.sub(pattern, replacement, t)

    # Put spaces around common punctuation that often gets glued
    t = NO_SPACE_PUNCT_RE.sub(r" \1 ", t)

    # Split camelCase-ish boundaries (NewYork -> New York)
    t = CAMEL_BOUNDARY_RE.sub(r"\1 \2", t)

    # Split letter<->digit boundaries (ford0719 -> ford 0719)
    t = LETTER_DIGIT_BOUNDARY_RE.sub(lambda m: (m.group(1) + " " + m.group(2)) if m.group(1) else (m.group(3) + " " + m.group(4)), t)

    # Collapse whitespace
    t = " ".join(t.split())
    return t

def _format_location(s: str) -> str:
    # Remove spaces before commas: "New York , New York" -> "New York, New York"
    s = re.sub(r"\s+,", ",", s)
    # Normalize comma spacing: ",California" or ",  California" -> ", California"
    s = re.sub(r",\s*", ", ", s)
    # Collapse any remaining whitespace
    return " ".join(s.split()).strip()


def _detect_corruption_type(text: str) -> str:
    """
    Identify what type of corruption the achievement text has.
    
    Returns:
        'character_fragmentation': High space-to-character ratio (e.g., "ne wc us to me rs")
        'completely_glued': Long words with few spaces (e.g., "Transferredto San Diegoin")
        'mixed_corruption': Multiple spaces and glued words (e.g., "pl an an dg re en")
        'mostly_ok': Minimal issues, mostly correct
    """
    if not text or len(text) < 5:
        return 'mostly_ok'
    
    words = text.split()
    if not words:
        return 'mostly_ok'
    
    space_ratio = text.count(' ') / len(text) if text else 0
    
    # Detect glued words (words that are obviously concatenated)
    # Check for: lowercase word directly adjacent to uppercase (camelCase within word)
    glued_pattern = len(re.findall(r'[a-z]{2,}[A-Z]', text))
    
    # Check for: multiple long words (>10 chars) relative to space count
    long_words = [w for w in words if len(w) > 10 and not any(c.isupper() for c in w[1:])]  # avoid proper nouns
    
    # Character fragmentation: many short fragments (space-heavy) with very short average word
    if space_ratio > 0.2:  # More than 20% of text is spaces
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len < 3.5:  # Very short fragments
            return 'character_fragmentation'
    
    # Completely glued: few words for long text, OR has camelCase gluing pattern
    if (len(words) < 5 and len(text) > 25) or glued_pattern > 0:
        return 'completely_glued'
    
    # Mixed corruption: has multiple spaces AND short words (from fragmentation)
    if '  ' in text and any(len(w) < 2 for w in words):
        return 'mixed_corruption'
    
    # Fallback: if we see long words with no spaces, it's glued even if space_ratio is low
    if long_words and len(words) < 6:
        return 'completely_glued'
    
    return 'mostly_ok'


def _score_text_quality(original: str, normalized: str) -> float:
    """
    Score how good the normalized text is.
    Higher score = better quality.
    
    Factors:
    - Penalty for single-letter words (over-segmentation)
    - Reward for reasonable word lengths
    - Penalty for too many spaces
    - Reward for common achievement words
    - Preserve length (shouldn't shrink much)
    """
    score = 100.0
    words = normalized.split()
    
    if not words:
        return 0.0
    
    # Heavy penalty for single-letter words (sign of over-segmentation)
    single_letter_words = [w for w in words if len(w) == 1 and w.isalpha()]
    score -= len(single_letter_words) * 15
    
    # Penalty for too-short words (2 chars or less, excluding common ones)
    short_words = [w for w in words if len(w) <= 2 and w.lower() not in {'a', 'to', 'in', 'at', 'by', 'of'}]
    score -= len(short_words) * 3
    
    # Calculate average word length
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
    
    # Reward: reasonable word lengths (5-10 chars average for achievement text)
    if 5 <= avg_word_len <= 10:
        score += 15
    elif 3 <= avg_word_len <= 12:
        score += 5
    else:
        score -= 10
    
    # Penalty: too many spaces (over-segmentation)
    space_ratio = normalized.count(' ') / len(normalized) if normalized else 0
    if space_ratio > 0.25:
        score -= 20
    
    # Reward: found common achievement words
    achievement_words = {
        'acquired', 'grew', 'led', 'built', 'improved', 'increased', 'achieved',
        'won', 'developed', 'created', 'managed', 'exceeded', 'delivered',
        'customers', 'revenue', 'sales', 'growth', 'team', 'business'
    }
    found_achievement_words = len([w for w in [x.lower() for x in words] if w in achievement_words])
    score += found_achievement_words * 8
    
    # Penalty: significant loss of content
    if len(normalized) < len(original) * 0.7:
        score -= 25
    
    # Reward: minimal distortion of original
    if abs(len(normalized) - len(original)) < len(original) * 0.1:
        score += 10
    
    return max(0, score)


def _normalize_achievement_intelligently(text: str) -> str:
    """
    Intelligently normalize achievement text by:
    1. Detecting corruption type
    2. Trying multiple strategies
    3. Scoring and selecting the best result
    
    This handles the fact that different achievements have different corruption patterns.
    """
    text = text.strip()
    if not text or len(text) < 5:
        return text
    
    corruption_type = _detect_corruption_type(text)
    
    # Strategy 1: Full pipeline (collapse -> fix_glued -> segment)
    def full_pipeline(t: str) -> str:
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        t = re.sub(r'\s+', ' ', t)
        t = _collapse_irregular_spacing(t)
        t = _fix_glued_lowercase_text(t)
        t = _segment_concatenated_words(t)
        return t
    
    # Strategy 2: Conservative (only fix obvious patterns, minimal segmentation)
    def conservative_fix(t: str) -> str:
        # Only do CamelCase and collapse irregular spacing
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        t = re.sub(r'\s+', ' ', t)
        t = _collapse_irregular_spacing(t)
        t = _fix_glued_lowercase_text(t)
        # Don't segment - too aggressive
        return t
    
    # Strategy 3: Aggressive segmentation (for completely glued text)
    def aggressive_segment(t: str) -> str:
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        t = re.sub(r'\s+', ' ', t)
        # Apply segmentation twice for very glued text
        t = _segment_concatenated_words(t)
        t = _collapse_irregular_spacing(t)
        t = _segment_concatenated_words(t)
        return t
    
    # Strategy 4: Direct word segmentation for heavily glued text
    def direct_segmentation(t: str) -> str:
        """For text like 'Grewthe Oregonterritorytoover' -> apply pure word segmentation"""
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        t = _segment_concatenated_words(t)
        t = _collapse_irregular_spacing(t)
        return t
    
    # Select strategies based on corruption type
    if corruption_type == 'character_fragmentation':
        strategies = {
            'collapse_aggressive': conservative_fix,
            'full_pipeline': full_pipeline,
        }
    elif corruption_type == 'completely_glued':
        strategies = {
            'direct_segment': direct_segmentation,
            'aggressive': aggressive_segment,
            'full_pipeline': full_pipeline,
        }
    elif corruption_type == 'mixed_corruption':
        strategies = {
            'full_pipeline': full_pipeline,
            'aggressive': aggressive_segment,
        }
    else:  # mostly_ok
        strategies = {
            'conservative': conservative_fix,
            'full_pipeline': full_pipeline,
        }
    
    # Try selected strategies
    results = {}
    for strategy_name, strategy_func in strategies.items():
        try:
            result = strategy_func(text)
            score = _score_text_quality(text, result)
            results[strategy_name] = (result, score)
        except Exception:
            # If a strategy fails, skip it
            pass
    
    if not results:
        # Fallback: return original if all strategies fail
        return text
    
    # Select best result by score
    best_strategy = max(results.items(), key=lambda x: x[1][1])
    return best_strategy[1][0]


def _segment_concatenated_words(text: str) -> str:
    """
    Dynamically segment concatenated words in text using multiple strategies.
    
    Handles patterns like:
      'Grewtheterritoryby40%in5months' -> 'Grew the territory by 40% in 5 months'
      'Wonbackalargeaccount' -> 'Won back a large account'
      'Wonseveralteamandnationalblitzes...' -> 'Won several team and national blitzes...'
    
    Strategy:
    1. First, apply heuristic rules (uppercase, digits, punctuation)
    2. Use constraint satisfaction: maximize number of recognized words
    3. Apply character-level boundary detection (common word starts)
    4. Fall back to statistical heuristics if needed
    
    Args:
        text: Input text with possible concatenated words
    
    Returns:
        Text with spaces inserted between words
    """
    if not text or not any(c.isalpha() for c in text):
        return text
    
    # Pass 1: Insert spaces around numbers and existing punctuation
    result = re.sub(r'(\d)([a-z])', r'\1 \2', text, flags=re.IGNORECASE)
    result = re.sub(r'([a-z])(\d)', r'\1 \2', result, flags=re.IGNORECASE)
    
    # Pass 2: Handle uppercase boundaries
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)
    
    # Pass 3: Split words by known boundaries and segment the long ones
    words = result.split()
    segmented_words = []
    
    for word in words:
        # Short words or with numbers - keep as is
        if len(word) <= 3 or any(c.isdigit() for c in word):
            segmented_words.append(word)
            continue
        
        # For all-uppercase words (proper nouns/acronyms), keep as-is
        if word.isupper():
            segmented_words.append(word)
            continue
        
        word_lower = word.lower()
        
        # If the word (in lowercase) is a known complete word, don't segment it
        if word_lower in COMMON_WORDS:
            segmented_words.append(word)
            continue
        
        # For mixed-case words (like "Transferredto"), try simple 2-part split first
        # This is conservative but effective for achievements with sentence case
        if word[0].isupper():
            found_split = False
            for i in range(2, len(word_lower) - 1):
                first = word_lower[:i]
                rest = word_lower[i:]
                if first in COMMON_WORDS and rest in COMMON_WORDS:
                    segmented = first + " " + rest
                    # Restore capitalization
                    segmented = word[0].upper() + segmented[1:]
                    segmented_words.append(segmented)
                    found_split = True
                    break
            
            # If 2-part split didn't work, try full DP segmentation
            if not found_split:
                if len(word_lower) > 15:
                    segmented = _segment_long_word(word_lower)
                else:
                    segmented = _segment_lowercase_word(word_lower)
                # Restore capitalization if result changed
                if segmented != word_lower:
                    segmented = word[0].upper() + segmented[1:]
                segmented_words.append(segmented)
            continue
        
        # For all-lowercase words, use the full segmentation logic
        if len(word_lower) > 15:
            segmented = _segment_long_word(word_lower)
        else:
            segmented = _segment_lowercase_word(word_lower)
        
        segmented_words.append(segmented)
    
    result = " ".join(segmented_words)
    result = " ".join(result.split())  # Normalize whitespace
    return result.strip()


def _segment_long_word(word: str) -> str:
    """
    Segment very long concatenated words (15+ chars) using aggressive heuristics.
    Uses known word starts, common prefixes, and constraint satisfaction.
    """
    if len(word) <= 3:
        return word
    
    # Common word starters in English (helps identify boundaries)
    word_starts = {
        'a', 'an', 'and', 'as', 'at', 'be', 'by', 'can', 'do', 'for', 'get', 'go',
        'had', 'has', 'have', 'he', 'her', 'his', 'how', 'i', 'if', 'in', 'is',
        'it', 'its', 'key', 'lead', 'led', 'made', 'make', 'may', 'my', 'of', 'on',
        'or', 'our', 'out', 'over', 're', 'so', 'some', 'such', 'than', 'that',
        'the', 'their', 'them', 'then', 'there', 'these', 'they', 'this', 'to',
        'too', 'under', 'up', 'us', 'used', 'very', 'was', 'we', 'were', 'what',
        'when', 'which', 'who', 'why', 'will', 'with', 'won', 'would', 'yet', 'you',
        'your', 'grew', 'acquired', 'selected', 'opened', 'finished', 'transferred',
        'outperformed', 'performed', 'down', 'territory', 'due', 'relationships',
        'major', 'close', 'accounts', 'account', 'blitzes', 'expansion', 'team',
        'national', 'several', 'country', 'attend', 'new', 'year', 'month',
    }
    
    # Try DP with word boundaries, but allow partial matches
    memo = {}
    
    def segment_recursive(idx: int, depth: int = 0) -> Optional[List[str]]:
        """Try to segment word[idx:] optimally."""
        if depth > 100:  # Prevent infinite recursion
            return None
        
        if idx in memo:
            return memo[idx]
        
        if idx >= len(word):
            return []
        
        # Try word starters first (most likely to be correct)
        for end in range(idx + 2, min(idx + 12, len(word) + 1)):  # Words typically 2-11 chars
            candidate = word[idx:end]
            
            # Strong preference for known word starts
            if candidate in word_starts or _is_valid_word(candidate):
                rest = segment_recursive(end, depth + 1)
                if rest is not None:
                    memo[idx] = [candidate] + rest
                    return memo[idx]
        
        # Fallback: if we can't find a perfect match, take 3-4 chars and continue
        for chunk_size in [4, 3, 2]:
            if idx + chunk_size <= len(word):
                rest = segment_recursive(idx + chunk_size, depth + 1)
                if rest is not None:
                    memo[idx] = [word[idx:idx + chunk_size]] + rest
                    return memo[idx]
        
        # Last resort: take remaining
        if idx < len(word):
            return [word[idx:]]
        
        return None
    
    result = segment_recursive(0)
    if result:
        return " ".join(result)
    
    return word



def _segment_lowercase_word(word: str) -> str:
    """
    Segment a lowercase word into multiple words using dynamic programming.
    
    CONSERVATIVE approach: Only segment if:
    1. Word is very long (12+ chars) - indicates likely concatenation
    2. Segmentation results in common/valid words
    3. Don't segment short words (<=10 chars) unless absolutely necessary
    
    Uses constraint satisfaction to find the best segmentation by:
    1. Trying to maximize number of recognized words
    2. Preferring known dictionary words
    3. Falling back to heuristics (vowels, prefixes, suffixes, length)
    
    Args:
        word: A lowercase concatenated word
    
    Returns:
        Space-separated words, or original if segmentation uncertain
    """
    if not word or len(word) <= 2:
        return word
    
    # If already spaced, return as-is
    if ' ' in word:
        return word
    
    # For short words (<=10 chars), be very conservative - only split if we're sure
    if len(word) <= 10:
        if word in COMMON_WORDS:
            return word
        # Try simple 2-part split only
        for i in range(2, len(word) - 1):
            first = word[:i]
            rest = word[i:]
            if first in COMMON_WORDS and rest in COMMON_WORDS:
                return first + " " + rest
        return word
    
    # For medium words (11-15 chars), be cautious
    if len(word) <= 15:
        n = len(word)
        memo = {}
        
        def can_segment_conservative(idx: int, depth: int = 0) -> Optional[List[str]]:
            """Try to segment with preference for known words."""
            if depth > 50:  # Prevent infinite recursion
                return None
            if idx in memo:
                return memo[idx]
            
            if idx == 0:
                return []
            
            # Try to form the last word from position 'start' to 'idx'
            # STRICT: Only accept words in COMMON_WORDS or very standard patterns
            for start in range(max(0, idx - 12), idx):
                candidate = word[start:idx]
                
                # Only accept if it's a known word (not heuristics)
                if candidate in COMMON_WORDS:
                    prev = can_segment_conservative(start, depth + 1)
                    if prev is not None:
                        memo[idx] = prev + [candidate]
                        return memo[idx]
            
            return None
        
        segmentation = can_segment_conservative(n)
        if segmentation and len(segmentation) >= 2:  # Only accept if we got multiple words
            return " ".join(segmentation)
        
        return word
    
    # For long words (16+ chars), use aggressive segmentation
    # Dynamic programming for longer words
    n = len(word)
    memo = {}
    
    def can_segment(idx: int) -> Optional[List[str]]:
        """Try to segment word[0:idx] into valid words."""
        if idx in memo:
            return memo[idx]
        
        if idx == 0:
            return []
        
        # Try to form the last word from position 'start' to 'idx'
        # IMPORTANT: Try longer candidates FIRST (prefer known complete words over fragments)
        for length in range(min(15, idx), 1, -1):  # Try longest first
            start = idx - length
            if start < 0:
                continue
            candidate = word[start:idx]
            
            # Prefer words in the dictionary (known words)
            if candidate in COMMON_WORDS:
                prev_segmentation = can_segment(start)
                if prev_segmentation is not None:
                    memo[idx] = prev_segmentation + [candidate]
                    return memo[idx]
        
        # Fallback: try any valid word (including heuristic-based ones)
        for length in range(min(15, idx), 1, -1):  # Try longest first
            start = idx - length
            if start < 0:
                continue
            candidate = word[start:idx]
            
            if _is_valid_word(candidate):
                prev_segmentation = can_segment(start)
                if prev_segmentation is not None:
                    memo[idx] = prev_segmentation + [candidate]
                    return memo[idx]
        
        return None
    
    segmentation = can_segment(n)
    if segmentation:
        return " ".join(segmentation)
    
    # Fallback: use greedy algorithm
    return _greedy_segment(word)



def _is_valid_word(word: str) -> bool:
    """Check if a word is valid using dictionary + heuristics."""
    if not word or len(word) < 2:
        return False
    
    # Check dictionary first
    if word in COMMON_WORDS:
        return True
    
    # Heuristic: reasonable word length (2-20 chars)
    if len(word) > 20:
        return False
    
    # Heuristic: at least 1 vowel for words longer than 3 chars
    vowels = sum(1 for c in word if c in 'aeiou')
    if len(word) > 3 and vowels < 1:
        return False
    
    # Heuristic: check for recognizable patterns
    # Accept if it's a known prefix/suffix or looks like a real word
    common_prefixes = ('un', 're', 're', 'pre', 'dis', 'mis', 'over', 'out', 'in', 'inter', 'sub', 'super')
    common_suffixes = ('ed', 'ing', 'er', 'ly', 'tion', 'ment', 'ness', 'able', 'ful', 'less', 'ish')
    
    has_prefix = any(word.startswith(p) for p in common_prefixes)
    has_suffix = any(word.endswith(s) for s in common_suffixes)
    
    if has_prefix or has_suffix:
        return True
    
    # Be MUCH more restrictive on very short words now
    # Only accept 2-3 char segments if they're in the dictionary or are specific common short words
    if len(word) <= 3:
        short_words = {'a', 'an', 'to', 'in', 'on', 'at', 'as', 'is', 'it', 'be', 'do', 'go', 'up', 'no', 'so', 'or', 'by', 'he', 'me', 'we', 'my'}
        return word in short_words or word in COMMON_WORDS
    
    # Medium words (4-8 chars) with good vowel ratio - be more selective
    if len(word) <= 8:
        # Require higher vowel ratio to accept medium words
        return vowels >= max(1, len(word) // 2)
    
    return False


def _greedy_segment(word: str) -> str:
    """
    Greedy segmentation: pick longest matching word at each step.
    Fallback when optimal segmentation not found.
    """
    result = []
    i = 0
    
    while i < len(word):
        # Try longest possible word first
        found = False
        for j in range(min(i + 15, len(word)), i, -1):
            candidate = word[i:j]
            if _is_valid_word(candidate):
                result.append(candidate)
                i = j
                found = True
                break
        
        if not found:
            # Couldn't find a valid word, take 2-3 chars and continue
            # (This should rarely happen)
            chunk_size = min(3, len(word) - i)
            result.append(word[i:i + chunk_size])
            i += chunk_size
    
    return " ".join(result)


from app.core.schemas import CandidateProfile, EvidenceItem, ParseResponse, FieldConfidence, EducationEntry
from app.core.education_parser import (
    detect_section_type,
    has_degree_keyword,
    is_high_school,
    is_institution_keyword,
    is_study_abroad,
    parse_education_entry,
    classify_entry_as_education,
)


# Common resume section headers (never a name)
HEADER_BLACKLIST = {
    "objective",
    "summary",
    "professional summary",
    "profile",
    "experience",
    "work experience",
    "employment",
    "employment history",
    "professional experience",
    "education",
    "skills",
    "technical skills",
    "soft skills",
    "core competencies",
    "technical proficiencies",
    "competencies",
    "proficiencies",
    "areas of expertise",
    "expertise",
    "strengths",
    "projects",
    "certifications",
    "certification",
    "licenses",
    "awards",
    "publications",
    "volunteer",
    "volunteering",
    "volunteer experience",
    "interests",
    "hobbies",
    "references",
    "additional information",
}



EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
# Phone regex: captures full phone with proper spacing, handles normalized variants
# Handles: (555) 123-4567, ( 555 ) 123-4567, 555-123-4567, +1 555 123 4567, etc.
PHONE_RE = re.compile(
    r"(?:^|\s|\()"  # Start context (non-capturing)
    r"("  # Group 1: full phone number (what we extract)
        r"(?:\+?\d{1,3}[-.\s]?)?"  # Optional country code
        r"\(?\s*\d{3}\s*\)?"  # Area code (optional parens, with optional spaces)
        r"[-.\s]?"  # Separator
        r"\d{3}"  # Exchange
        r"[-.\s]?"  # Separator
        r"\d{4}"  # Line number
    r")",
    re.IGNORECASE
)
URL_RE = re.compile(r"\bhttps?://[^\s)>\]]+\b", re.IGNORECASE)
LINKEDIN_RE = re.compile(r"\b(?:https?://)?(?:www\.)?linkedin\.com/[^\s)>\]]+\b", re.IGNORECASE)
GITHUB_RE = re.compile(r"\b(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_.-]+\b", re.IGNORECASE)

# Simple "City, State" detector (e.g., "New York, New York", "Austin, TX")
LOCATION_RE = re.compile(r"^[A-Za-z .'-]+,\s*[A-Za-z]{2,}$")
# Location detector: find "City, State/Country" pattern
# US State abbreviations (2-letter codes)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}
# Multi-word US states/territories (normalized for lookup)
MULTI_WORD_STATES = {
    "new york", "new mexico", "new hampshire", "north carolina", "north dakota",
    "south carolina", "south dakota", "west virginia", "puerto rico"
}

def _extract_location_from_line(text: str) -> str | None:
    """
    Extract City, State/Country pattern from text by finding the LAST comma followed by a valid state/country.
    This handles cases like "Company, San Francisco, California" -> "San Francisco, California"
    Also handles "New York, New York" -> "New York, New York"
    Also handles "Spokane, Washington, 2012 – 2016" -> "Spokane, Washington"
    
    BUT does NOT match patterns like "DIS Study Abroad, Copenhagen" (returns None, since "DIS" is not a city).
    """
    # Look for pattern like "City, State" or "City, Country"
    # Start from the right end of the text and look for commas
    commas = [i for i, c in enumerate(text) if c == ',']
    
    if not commas:
        return None
    
    # Try each comma from right to left
    for comma_pos in reversed(commas):
        after_comma = text[comma_pos+1:].strip()
        # For multi-word locations, take up to 2 words
        words_after = after_comma.split()
        
        if not words_after:
            continue
        
        # Check first word (strip punctuation)
        first_word = words_after[0].strip(',.;:–-')
        two_words = " ".join(words_after[:2]).strip(',.;:–-') if len(words_after) >= 2 else ""
        
        # Check if it's a US state code, multi-word state, or valid country name
        is_state_code = first_word.upper() in US_STATES
        is_multi_word = two_words.lower() in MULTI_WORD_STATES
        is_valid_location = re.match(r"^[A-Z][a-z]+$", first_word) and len(first_word) >= 4  # Require >= 4 chars
        
        # Use two_words if it's a multi-word state, otherwise use first_word
        location_name = None
        if is_multi_word:
            location_name = two_words
        elif is_state_code:
            location_name = first_word
        elif is_valid_location:
            location_name = first_word
        
        if location_name:
            # Now extract what's before this comma (should be the city)
            before_comma = text[:comma_pos].strip()
            # Get the last 1-2 words before comma (the city name)
            words = before_comma.split()
            if words:
                # Take last 1-2 title-cased words as city
                city_words = []
                for w in reversed(words):
                    if re.match(r"^[A-Z][a-z]*$", w):
                        city_words.insert(0, w)
                        if len(city_words) >= 2:
                            break
                    else:
                        break  # Stop at non-city-like words
                
                # Key validation: city should be a real city name (not keywords like "Study", "Abroad", etc.)
                # If city is a single word and is not a known keyword, it's likely valid
                # But reject if it's obviously not a city (like "Study", "Abroad", etc.)
                invalid_city_keywords = {"study", "abroad", "institute", "program", "semester", "trimester", "year"}
                
                if city_words:
                    city = " ".join(city_words)
                    # Reject if city contains invalid keywords
                    if any(keyword in city.lower() for keyword in invalid_city_keywords):
                        continue
                    return f"{city}, {location_name}"
    
    return None


def _is_header_line(text: str) -> bool:
    raw = text.strip()
    if not raw:
        return True

    # CRITICAL: Fix PDF wordbreaks (e.g., "educati on" -> "education") BEFORE normalizing
    # This ensures headers with mid-word breaks are still recognized
    from app.core.education_parser import normalize_pdf_wordbreaks
    raw = normalize_pdf_wordbreaks(raw)
    
    t = _normalize_for_search(raw)
    key = re.sub(r"\s+", " ", t).strip().lower()

    if key in HEADER_BLACKLIST:
        return True

    # Reject ALL-CAPS single-word lines (EXPERIENCE, SKILLS, EDUCATION)
    if t.isupper() and (" " not in t):
        return True

    return False



def _normalize_name(name: str) -> str:
    """
    Normalize display name without changing evidence.
    If it's all-caps, convert to Title Case.
    """
    t = name.strip()
    if t.isupper():
        return t.title()
    return t


def _fix_word_breaks_aggressive(text: str) -> str:
    """
    Fix PDF word-break artifacts like "adopti on" -> "adoption", "terri to ries" -> "territories".
    
    Strategy: Conservatively merge adjacent tokens when they clearly form a broken word.
    Avoids merging normal word boundaries.
    
    Handles patterns like:
    - "adopti on" -> "adoption" (prefix + suffix)
    - "terri to ries" -> "territories" (prefix + short + suffix)
    - "2 nd" -> "2nd" (digit + letter suffix)
    - "atta in ment" -> "attainment" (prefix + short + suffix)
    - "initi a tive" -> "initiative" (prefix + single letter + suffix)
    
    This is a more aggressive version of normalize_bullet_text for full paragraph normalization.
    """
    if not text or not text.strip():
        return text
    
    tokens = text.split()
    out = []
    i = 0
    
    # Common suffixes that indicate word breaks (not real word boundaries)
    broken_suffixes = {
        'on', 'ing', 'ed', 'tion', 'sion', 'ment', 'ity', 'ies', 'able',
        'ness', 'ous', 'ful', 'less', 'ly', 'er', 'est', 'en', 'ist',
        'nd', 'st', 'rd', 'th',  # ordinal suffixes like 2nd, 1st, etc.
        'tive', 'ive',  # for initiative-like words
    }
    
    while i < len(tokens):
        merged = False
        
        # Try 3-token merge: "terri to ries" -> "territories" or "initi a tive" -> "initiative"
        # Pattern: tok1 + short-token(1-2 chars) tok2 + tok3(suffix or suffix-like)
        if i + 2 < len(tokens):
            tok1, tok2, tok3 = tokens[i], tokens[i+1], tokens[i+2]
            # Merge if middle token is very short (1-2 chars) AND last token looks like a suffix
            # BUT: Don't merge if tok1 or tok2 contains a digit (not a word-break artifact)
            if (len(tok2) <= 2 and 
                (tok3.lower() in broken_suffixes or tok3.lower().endswith(('ies', 'ment', 'tion', 'tive', 'ive'))) and
                not any(c.isdigit() for c in tok1) and  # Skip if tok1 contains a digit
                not any(c.isdigit() for c in tok2)):    # Skip if tok2 is a digit or contains one
                merged_3 = tok1 + tok2 + tok3
                out.append(merged_3)
                i += 3
                merged = True
        
        if not merged and i + 1 < len(tokens):
            tok1, tok2 = tokens[i], tokens[i+1]
            
            # Case 1: tok2 is a clear suffix (very short, in our broken_suffixes set)
            if tok2.lower() in broken_suffixes:
                # Merge if tok1 ends with a vowel (suggests word break, not boundary)
                if tok1 and tok1[-1].lower() in 'aeiou':
                    merged_2 = tok1 + tok2
                    out.append(merged_2)
                    i += 2
                    merged = True
                # Special case: DISABLE digit + ordinal suffix merging
                # Reason: "2 nd" should be "2nd", but "Q2 2 nd" shouldn't become "Q22nd"
                # The heuristic is too error-prone. Leave these for manual post-processing.
                # elif tok1[-1].isdigit() and tok2.lower() in {'nd', 'st', 'rd', 'th'}:
        
        if not merged:
            out.append(tokens[i])
            i += 1
    
    return " ".join(out)


# ===== EXPERIENCE PARSING PATTERNS =====

# Detect experience section headers (including variants like "Career Experience", "Work History", etc.)
EXPERIENCE_HEADER_RE = re.compile(
    r"^\s*(career\s+)?(work\s+)?(professional\s+)?(experience|employment|history)",
    re.IGNORECASE
)

# Single-line format: "Company: Title: Location" (colon-delimited only)
# Do NOT match slashes to avoid conflict with date formats like "02/2019 - 04/2025"
# Example: "ACME CORP: TERRITORY MANAGER: NEW YORK"
SINGLE_LINE_EXPERIENCE_RE = re.compile(
    r"^(.+?):\s*(.+?):\s*(.+)$"
)

# Two-part format: "Company: Job Title" (colon-delimited only)
# Do NOT match slashes to avoid conflict with date formats like "02/2019 - 04/2025"
# Examples: "NEODENT: TERRITORY MANAGER" or "SOUTHERN GLAZER'S: KEY ACCOUNT MANAGER"
TWO_PART_EXPERIENCE_RE = re.compile(
    r"^(.+?):\s*([A-Z][A-Za-z\s&'-]*)(?::\s*)?$"
)

# Date patterns (relaxed, capture many formats)
# Examples: "January 2024-Present", "01/2024 - 12/2025", "Jan 2020 - Dec 2021", "2020 - 2021"
DATE_RANGE_RE = re.compile(
    r"(\d{1,2}[-/]?\d{1,2}[-/]?\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4})\s*(?:-|–|to)\s*(?:Present|Current|(\d{1,2}[-/]?\d{1,2}[-/]?\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}))",
    re.IGNORECASE
)

# Bullet/achievement line detector
BULLET_RE = re.compile(r"^[\s•●\-*>+]+")


def _detect_experience_section_start(lines: List[Tuple[str, str]]) -> int | None:
    """
    Scan lines for the start of an experience section.
    Returns the index of the header line, or None if not found.
    """
    for idx, (locator, text) in enumerate(lines):
        if EXPERIENCE_HEADER_RE.match(text.strip()):
            return idx
    return None


def _extract_date_range(text: str) -> Tuple[str | None, str | None]:
    """
    Extract start_date and end_date from text.
    Returns (start_date, end_date) or (None, None) if not found.
    
    Tries to normalize to MM/YYYY format where possible.
    """
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None, None
    
    matched = m.group(0).strip()
    # For now, return the matched string as-is (full normalization is future work)
    # Typically looks like "January 2024 - Present" or "01/2024 - 12/2025"
    parts = re.split(r"\s*(?:-|–|to)\s*", matched, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None, None


def _title_case_each_word(text: str) -> str:
    """
    Convert to title case: lowercase everything then uppercase first letter of each word.
    This works better than str.title() for text with hyphens, apostrophes, etc.
    """
    words = text.split()
    return " ".join(w[0].upper() + w[1:].lower() if w else "" for w in words)


def _parse_single_line_experience(text: str) -> Dict[str, str | None]:
    """
    Parse a single-line experience entry: "Company: Title: Location" or "Company: Title" (2-part).
    Returns dict with company, job_title, location.
    
    Examples:
      Input: "ACME CORP: TERRITORY MANAGER: NEW YORK"
      Output: {"company": "ACME CORP", "job_title": "Territory Manager", "location": "New York"}
      
      Input: "NEODENT: TERRITORYMANAGEROREGON:"
      Output: {"company": "NEODENT", "job_title": "Territory Manager Oregon", "location": None}
    """
    result = {"company": None, "job_title": None, "location": None}
    
    # Remove bullet prefix if present and check if original was all-caps
    text_clean = BULLET_RE.sub("", text).strip()
    # Check if any letters in the original (after removing bullet/spaces) were uppercase
    was_all_caps = bool(re.search(r"[A-Z]", text_clean)) and not bool(re.search(r"[a-z]", text_clean))
    
    t = _normalize_for_search(text_clean).strip()
    
    # Try 3-part format first
    m = SINGLE_LINE_EXPERIENCE_RE.match(t)
    if m:
        company = m.group(1).strip()
        job_title = m.group(2).strip()
        location = m.group(3).strip() if m.group(3) else None
        
        # Normalize case: if original was all-caps, use word-by-word title case
        if was_all_caps:
            if company:
                company = _title_case_each_word(company)
            if job_title:
                job_title = _title_case_each_word(job_title)
            if location:
                location = _title_case_each_word(location)
        
        # Apply field-safe normalization (fixes split-inside-a-word like "communicati on")
        if company:
            company = normalize_field_text(company)
        if job_title:
            job_title = normalize_field_text(job_title)
        if location:
            location = normalize_field_text(location)
        
        result["company"] = company if company else None
        result["job_title"] = job_title if job_title else None
        result["location"] = location
        return result
    
    # Try 2-part format: "Company: Job Title" or "Company: Job Title:"
    m_two_part = TWO_PART_EXPERIENCE_RE.match(t)
    if m_two_part:
        company = m_two_part.group(1).strip()
        job_title = m_two_part.group(2).strip() if m_two_part.group(2) else None
        
        # Normalize case: if original was all-caps, use word-by-word title case
        if was_all_caps:
            if company:
                company = _title_case_each_word(company)
            if job_title:
                job_title = _title_case_each_word(job_title)
        
        # Apply field-safe normalization (fixes split-inside-a-word like "communicati on")
        if company:
            company = normalize_field_text(company)
        if job_title:
            job_title = normalize_field_text(job_title)
        
        result["company"] = company if company else None
        result["job_title"] = job_title
        return result
    
    return result


def _is_company_or_job_line(text: str) -> bool:
    """
    Heuristic: Is this line a company name or job title line?
    (Used to distinguish from achievement bullets and descriptions.)
    """
    t = text.strip()
    
    # Has a bullet or dash prefix -> achievement, not company/job
    if BULLET_RE.match(t):
        return False
    
    # Too long -> probably description, not company/job
    if len(t) > 150:
        return False
    
    # Empty -> no
    if not t:
        return False
    
    # Mostly uppercase or Title Case -> likely company/job name
    word_count = len(t.split())
    upper_words = sum(1 for w in t.split() if w and w[0].isupper())
    
    # At least 50% uppercase-starting words is a good signal
    if word_count > 0 and upper_words / word_count >= 0.5:
        return True
    
    return False


def _is_company_with_location_header(text: str) -> bool:
    """
    Detect if a line is a company header with location (H2-like format).
    
    Examples:
      - "Bausch & Lomb, Phoenix Valley, AZ"
      - "Google, Mountain View, CA"
      - "Tech Corp, Austin, TX"
    
    Returns True if:
    1. Line contains at least one comma
    2. The part after last comma looks like a location (State/Country code)
    3. The part before the location looks like a company name
    4. Line is relatively short (< 150 chars)
    """
    if not text or len(text) > 150:
        return False
    
    # Must have at least one comma
    if "," not in text:
        return False
    
    # Try to extract location from the line
    location = _extract_location_from_line(text)
    
    if not location:
        return False
    
    # Get the part before the location
    loc_idx = text.find(location)
    before_loc = text[:loc_idx].strip().rstrip(",").strip()
    
    # Company name should:
    # 1. Not be empty
    # 2. Not be a job title (all-caps single word is unlikely for company, but "MANAGER" is a title)
    # 3. Start with an uppercase letter
    # 4. Contain reasonable company name characters (letters, spaces, &, -, etc.)
    
    if not before_loc:
        return False
    
    # Reject if it looks like a job title (single all-caps word like "MANAGER", "DIRECTOR")
    if before_loc.isupper() and len(before_loc.split()) == 1 and len(before_loc) < 20:
        return False
    
    # Check it's a reasonable company name length and format
    if not re.match(r"^[A-Z&\s'-]", before_loc):
        return False
    
    return True


def _is_job_title_header(text: str) -> bool:
    """
    Detect if a line is a job title header (H3-like format, usually all-caps or Title Case).
    
    Can include dates on the same line, separated by whitespace.
    Examples:
      - "BUSINESS DEVELOPMENT MANAGER"
      - "Territory Manager"
      - "Senior Software Engineer"
      - "BUSINESS DEVELOPMENT MANAGER                04/2025 - PRESENT"
    
    Returns True if:
    1. The part before dates is Title Case or ALL CAPS job title
    2. Does NOT contain colons (colon indicates single-line format like "Company: Title")
    3. Does NOT contain commas (comma indicates location or company/location format)
    4. If dates present, they should be separated from title by whitespace
    """
    if not text or len(text) > 150:
        return False
    
    t = text.strip()
    
    # Skip if it's a section header (EXPERIENCE, EDUCATION, SKILLS, etc.)
    if t.lower() in HEADER_BLACKLIST:
        return False
    
    # Skip if it contains colons (indicates single-line format)
    if ":" in t:
        return False
    
    # Skip if it contains commas (indicates location or company/location format)
    if "," in t:
        return False
    
    # Skip if it looks like a location line (has city, state pattern)
    if _extract_location_from_line(t):
        return False
    
    # Extract title part (before dates if present)
    # Check if there are dates at the end
    title_part = t
    if re.search(r'\d{1,2}[-/]\d{1,4}', t):
        # Remove dates from the end for title validation
        # Whitespace before dates is optional (dates might be at the start of the line)
        title_part = re.sub(r'\s*\d{1,2}[-/]\d{1,4}\s*(?:-|–|to)\s*(?:Present|Current|\d{1,2}[-/]\d{1,4})?', '', t, flags=re.IGNORECASE)
        title_part = title_part.strip()
    
    if not title_part:
        return False
    
    # Must be Title Case or ALL CAPS
    if not (title_part.isupper() or re.match(r"^[A-Z][A-Za-z\s&'-]*$", title_part)):
        return False
    
    # Word count should be 1-6 (typical job titles, not counting dates)
    words = title_part.split()
    if len(words) < 1 or len(words) > 6:
        return False
    
    return True


def _group_experience_entries(
    lines: List[Tuple[str, str]],
    section_start: int
) -> List[List[Tuple[str, str]]]:
    """
    Group consecutive lines into experience entries.
    
    Supports multiple formats:
      1. H2/H3 Format (hierarchical headers):
         - H2: "Company Name, Location"
         - H3: "Job Title"
         - H3 or same line: Dates (04/2025 - PRESENT)
         - Following lines: Description, bullets, achievements
      
      2. Single-line format: "Company: Title: Location"
      
      3. Multi-line format:
         - Line 1: Company (possibly with location)
         - Line 2+: Title, dates, achievements
    
    Strategy:
      1. Skip the header line itself
      2. Skip empty lines
      3. Detect entry boundaries:
         - H2 company header: "Company, Location"
         - H3 job title header: All-caps "JOB TITLE"
         - Single-line format (Company: Title: Location)
         - Two-part format (Company: Title)
      4. Continue grouping until we hit another major section header (EDUCATION, etc.)
    
    Returns list of experience entry groups (each group is a list of locator/text pairs).
    """
    entries: List[List[Tuple[str, str]]] = []
    current_entry: List[Tuple[str, str]] = []
    last_h2_company_header: Tuple[str, str] | None = None  # Track last H2 company header for multi-job entries
    
    for idx in range(section_start + 1, len(lines)):
        locator, text = lines[idx]
        t = text.strip()
        
        # Empty line
        if not t:
            continue
        
        # Hit another major section header (EDUCATION, etc.) -> end experiences
        if _is_header_line(text) and not BULLET_RE.match(t) and ":" not in t and idx > section_start + 2:
            # Make sure it's really a major section, not just a sub-heading
            if re.match(r"^[A-Z][A-Za-z\s/&-]*$", t) and len(t.split()) <= 5:
                if current_entry:
                    entries.append(current_entry)
                    current_entry = []
                # Stop grouping
                break
        
        # Detect start of new experience entry:
        is_new_entry_start = False
        
        # CRITICAL GUARD: Bullets can NEVER start new entries
        # They are ALWAYS details/achievements attached to an existing entry
        # This prevents education details like "● Applied Communications Major: Social Media/Marketing"
        # from being misclassified as a new experience entry
        if BULLET_RE.match(t):
            # This is a bullet line - treat as attachment to current entry only
            is_new_entry_start = False
        # Skip date-only lines (they belong to current entry, not new entries)
        # Examples: "04/2025 - PRESENT", "01/2023 - 12/2024"
        elif re.match(r'^\d{1,2}[-/]\d{1,4}\s*(?:-|–|to)\s*(?:\d{1,2}[-/]\d{1,4}|Present|Current)', t, re.IGNORECASE):
            # This is a date range line - attach to current entry
            is_new_entry_start = False
        # Pattern 0: H2/H3 Hierarchical Format
        # Detect "Company, Location" as start of new entry
        elif _is_company_with_location_header(t):
            is_new_entry_start = True
            # Remember this H2 company header for subsequent H3 job titles
            last_h2_company_header = (locator, text)
        # Pattern 1: Single-line format (Company: Title: Location)
        # IMPORTANT: Must have colons to distinguish from job title headers with dates
        elif ":" in t and SINGLE_LINE_EXPERIENCE_RE.match(t):
            is_new_entry_start = True
            # Clear H2 cache - we're in a different format now
            last_h2_company_header = None
        # Pattern 1b: Two-part format (Company: Job Title with no location)
        # This catches cases like "NEODENT: TERRITORYMANAGEROREGON:" or "SOUTHERN GLAZER'S: KEY ACCOUNT MANAGER"
        elif TWO_PART_EXPERIENCE_RE.match(t):
            # Make sure it's not just a normal line with a colon (e.g., description)
            # Two-part format should have ALL CAPS or Title Case words (job titles are usually uppercase)
            parts = TWO_PART_EXPERIENCE_RE.match(t).groups()
            company_part = parts[0].strip()
            # If company part looks like a company name (not a long description), treat as new entry
            if len(company_part) < 100 and (company_part.isupper() or any(w[0].isupper() for w in company_part.split())):
                # Non-bullet line with company:role format -> new entry
                is_new_entry_start = True
                # Clear H2 cache - we're in a different format now
                last_h2_company_header = None
        # Pattern 2: Company name with location (e.g., "Bausch & Lomb, Phoenix Valley, AZ")
        # OR Company with location + dates (e.g., "Google, Mountain View, CA, 2020 – Present")
        # These can indicate a new entry IF they have a company name before the location.
        # IMPORTANT: Standalone location lines in the middle of descriptions should NOT split entries
        elif current_entry and _extract_location_from_line(t) is not None and not BULLET_RE.match(t) and len(t) < 200:
            # Check if this looks like a company+location header or just a location
            # Company headers have a company name before the location
            is_company_location = _is_company_with_location_header(t)
            
            if is_company_location:
                # This looks like a new company+location header, so start a new entry
                is_new_entry_start = True
                # Clear H2 cache - this is a new company, not part of previous H2/H3 structure
                last_h2_company_header = None
        # Pattern 3: Job title header (all-caps or Title Case with optional dates)
        # This indicates a new job entry within the same company, but ONLY if:
        # 1. We have a cached H2 company header (indicating H2/H3 format)
        # 2. Current entry already has a complete job title with content
        elif current_entry and _is_job_title_header(t) and last_h2_company_header:
            # Check if current entry already has a complete job title with content after it
            # This is true if we've seen: [company, description, job_title, dates/description, bullet/achievement]
            # We need at least: company + job_title_with_dates + some_content = 4+ lines minimum
            has_prior_job_title = False
            if len(current_entry) >= 4:  # At minimum: company + job_title + dates + (description or bullet)
                # Check if any earlier line looks like a job title header
                for earlier_locator, earlier_text in current_entry:
                    if _is_job_title_header(earlier_text.strip()):
                        has_prior_job_title = True
                        break
            
            if has_prior_job_title:
                # This is a second job title under the same H2 company, so start a new entry
                # CRITICAL: Prepend the cached H2 company header to ensure company name is carried forward
                is_new_entry_start = True
            # else: this is the first job title in H3 format, keep it attached to company header
        # Pattern 4: Simple multi-line format without H2 header
        # Detect when we have a completed entry (with bullets/achievements) followed by a new company/job line
        # This handles simple formats like:
        #   TECH CORP
        #   Software Engineer
        #   ● Achievements
        #   SALES CORP   <- This should start a new entry
        #   Account Manager
        elif current_entry and _is_company_or_job_line(t) and not BULLET_RE.match(t):
            # Check if current entry has achievements/bullets (indicating it's complete)
            has_achievements = any(BULLET_RE.match(line_text) for _, line_text in current_entry)
            # If we have achievements, this new company/job line likely starts a new entry
            if has_achievements and len(current_entry) >= 3:  # At least company + job + achievement
                is_new_entry_start = True
                # Clear H2 cache since we're not in H2/H3 format
                last_h2_company_header = None
        
        if is_new_entry_start and current_entry:
            # Start a new entry, save the old one
            entries.append(current_entry)
            # If starting a new H3 job title entry and we have a cached H2 company header, prepend it
            # ONLY prepend if this is actually a job title header (not a different format)
            if _is_job_title_header(t) and last_h2_company_header and not _is_company_with_location_header(t):
                current_entry = [last_h2_company_header, (locator, text)]
            else:
                current_entry = [(locator, text)]
                # If this is a new H2 company header, update the cache
                if _is_company_with_location_header(t):
                    last_h2_company_header = (locator, text)
                # Otherwise, clear the cache (we're in a different format)
                else:
                    last_h2_company_header = None
        else:
            current_entry.append((locator, text))
    
    # Don't forget the last entry
    if current_entry:
        entries.append(current_entry)
    
    return entries


def _parse_experience_entry(entry_lines: List[Tuple[str, str]]) -> Dict[str, any]:
    """
    Parse a single experience entry (list of lines) into structured data.
    
    Supports multiple formats:
      
      H2/H3 Format (hierarchical):
      - Line 1: "Company, Location" (H2 header)
      - Line 2: "JOB TITLE" (H3 header, may include dates)
      - Line 3+: Description, achievements
      
      Single-line format:
      - Line 1: "Company: Title: Location"
      
      Multi-line format:
      - Line 1: Company (possibly with location)
      - Line 2: Job Title, Location, or Dates
      - Line 3+: Achievements/bullets/description
    
    Returns dict with keys: company, job_title, location, start_date, end_date, company_description, job_description, achievements (list)
    """
    experience = {
        "company": None,
        "job_title": None,
        "location": None,
        "start_date": None,
        "end_date": None,
        "company_description": None,
        "job_description": None,
        "achievements": []
    }
    
    if not entry_lines:
        return experience
    
    # Pre-scan first 3 lines to identify structure
    first_lines_raw = [entry_lines[i][1].strip() for i in range(min(3, len(entry_lines)))]
    
    # Parse first line(s) for company, job_title, location, dates
    idx = 0
    
    # LINE 1: Look for company/location or single-line format
    if idx < len(entry_lines):
        locator, text = entry_lines[idx]
        t = text.strip()
        
        # Try single-line format first (Company:Title:Location)
        parsed = _parse_single_line_experience(t)
        if parsed["company"] or parsed["job_title"]:
            experience.update(parsed)
            idx += 1
        # CRITICAL: Check if line 1 is a company with location (H2 header)
        # This happens in H2/H3 format - the H2 header should have been prepended by grouping logic
        elif _is_company_with_location_header(t):
            # This is an H2 company header
            location_text = _extract_location_from_line(t)
            if location_text:
                experience["location"] = _format_location(location_text)
                loc_start = t.find(location_text)
                company_part = t[:loc_start].strip().rstrip(",")
                if company_part:
                    experience["company"] = company_part.title() if company_part.isupper() else company_part
            idx += 1
        # Check if line 1 is a job title header ONLY if line 2 also exists and looks like it could be in H3 format
        # (This prevents treating standalone company names like "TECH CORP" as job titles)
        elif _is_job_title_header(t) and len(entry_lines) >= 2 and _is_company_with_location_header(entry_lines[0][1]):
            # First line is a job title, not a company (H3 format with H2 header on line 0)
            # This means it's a continuation entry (multiple jobs under same company)
            # Leave company blank and jump to job title parsing
            pass  # Don't increment idx yet; process as job title in next section
        else:
            # Line 1 is likely company name (possibly with location)
            # Check if it has a location
            location_text = _extract_location_from_line(t)
            if location_text:
                # Extract location and treat rest as company
                experience["location"] = _format_location(location_text)
                # Extract company name (everything before the location)
                loc_start = t.find(location_text)
                company_part = t[:loc_start].strip().rstrip(",")
                if company_part:
                    experience["company"] = company_part.title() if company_part.isupper() else company_part
            else:
                # No location, so the whole line is company name
                experience["company"] = t.title() if t.isupper() else t
            idx += 1
    
    # LINE 2: Collect company description lines, then look for job title (H3 header)
    # In H2/H3 format, description lines appear between company header and job title
    # Strategy: Collect ALL non-empty, non-bullet lines until we hit the job title header
    company_desc_lines = []
    while idx < len(entry_lines):
        locator, text = entry_lines[idx]
        t = text.strip()
        
        if not t:
            # Skip empty lines
            idx += 1
            continue
        
        # CRITICAL: Stop immediately on bullet lines (they are achievements, not descriptions)
        if BULLET_RE.match(text):
            break
        
        # Check if this is an H3-like job title header (all-caps or Title Case job title)
        if _is_job_title_header(t):
            # Found the job title! Save accumulated description and break
            if company_desc_lines:
                raw_desc = " ".join(company_desc_lines)
                # Normalize to fix PDF corruption artifacts (adopti on -> adoption, 2 nd -> 2nd)
                normalized = _fix_word_breaks_aggressive(raw_desc)
                normalized = normalize_bullet_text(normalized)
                experience["company_description"] = normalized
            
            # Extract dates from this job title line if present
            dates = _extract_date_range(t)
            if dates[0]:
                experience["start_date"], experience["end_date"] = dates
            
            # Extract job title (remove dates from the end)
            title_part = t
            if re.search(r'\d{1,2}[-/]\d{1,4}', t):
                # Remove dates from the end
                title_part = re.sub(r'\s+\d{1,2}[-/]\d{1,4}\s*(?:-|–|to)\s*(?:Present|Current|\d{1,2}[-/]\d{1,4})?', '', t, flags=re.IGNORECASE)
                title_part = title_part.strip()
            
            if title_part:
                experience["job_title"] = title_part.title() if title_part.isupper() else title_part
            
            idx += 1
            
            # LINE 2.5: Check if next line has more info (dates if not on same line, or location)
            # In H3 format, dates might come on a separate line after the title if not on same line
            if idx < len(entry_lines) and not dates[0]:  # Only check next line if we didn't find dates on this line
                locator_next, text_next = entry_lines[idx]
                t_next = text_next.strip()
                
                # Check if next line is just dates/location (no company/title)
                dates_next = _extract_date_range(t_next)
                has_dates = dates_next[0] is not None
                has_location = _extract_location_from_line(t_next) is not None
                is_just_dates = (has_dates or has_location) and not _is_job_title_header(t_next) and not _is_company_with_location_header(t_next)
                
                if is_just_dates:
                    # Extract dates from this line
                    if dates_next[0]:
                        experience["start_date"], experience["end_date"] = dates_next
                    
                    # Extract location if present
                    location_text = _extract_location_from_line(t_next)
                    if location_text:
                        experience["location"] = _format_location(location_text)
                    
                    idx += 1
            break  # Exit while loop after finding job title
        elif any(c.isupper() for c in t) or any(c.isdigit() for c in t):
            # This is a company description line (mixed case, contains text, not a job title)
            # Collect it as part of company description
            company_desc_lines.append(t)
            idx += 1
        else:
            # Skip other lines (pure lowercase, etc.)
            idx += 1
    
    # JOB DESCRIPTION: Collect non-bullet lines after job title but before achievements
    # Strategy: Collect ALL non-bullet, non-header lines as job description until we hit a bullet point
    # This is more robust to PDF corruption and varying line lengths
    job_desc_lines = []
    temp_idx = idx
    while temp_idx < len(entry_lines):
        check_locator, check_text = entry_lines[temp_idx]
        check_t = check_text.strip()
        
        if not check_t:
            # Skip empty lines but keep looking for more content
            temp_idx += 1
            continue
        
        # Stop when we hit a bullet (achievements start)
        if BULLET_RE.match(check_text):
            break
        
        # Stop if it's a header line (section header like EDUCATION, SKILLS)
        if _is_header_line(check_text):
            break
        
        # CRITICAL: Don't stop on company header detection if we haven't found any job description yet
        # This prevents misinterpreting continuation text as a new entry
        is_company_header = _is_company_with_location_header(check_t)
        if is_company_header and job_desc_lines:
            # We already have job description, so this is likely a new entry
            break
        
        # Collect any non-empty, non-header line as job description
        # (unless it looks like a company header and we already have description)
        if not is_company_header:
            job_desc_lines.append(check_t)
            idx = temp_idx + 1  # Advance idx past job description
        
        temp_idx += 1
    
    if job_desc_lines:
        raw_job_desc = " ".join(job_desc_lines)
        # Normalize to fix PDF corruption artifacts (adopti on -> adoption, 2 nd -> 2nd)
        normalized = _fix_word_breaks_aggressive(raw_job_desc)
        normalized = normalize_bullet_text(normalized)
        experience["job_description"] = normalized
    
    # Remaining lines are likely achievements/description
    # Handle wrapped bullet lines: if a line doesn't start with a bullet, it's a continuation
    current_achievement = None
    for line_idx in range(idx, len(entry_lines)):
        locator, text = entry_lines[line_idx]
        t = text.strip()
        
        if not t:  # Skip empty lines
            continue
        
        # CRITICAL: Stop if we encounter another job title header (new job)
        # This prevents the next job from being included in achievements
        if _is_job_title_header(t):
            # Save current achievement before stopping
            if current_achievement and len(current_achievement) > 10 and len(current_achievement) < 500:
                # Fix word-break artifacts first (2 nd -> 2nd, adopti on -> adoption)
                current_achievement = _fix_word_breaks_aggressive(current_achievement)
                current_achievement = normalize_bullet_text(current_achievement)
                has_character_fragmentation = bool(re.search(r'\b[a-z]\s+[a-z]\s+[a-z]\b', current_achievement))
                if has_character_fragmentation:
                    current_achievement = _normalize_achievement_intelligently(current_achievement)
                    current_achievement = normalize_bullet_text(current_achievement)
                experience["achievements"].append(current_achievement)
            # Stop processing - next entry should be handled by entry grouping
            break

        # Check if this line starts with a bullet marker
        is_bullet_line = bool(BULLET_RE.match(text))
        
        # Skip lines that look like company:role headers
        if TWO_PART_EXPERIENCE_RE.match(t) and ":" in t:
            continue
        
        # Skip lines that look like location+date headers
        if _extract_location_from_line(t) and DATE_RANGE_RE.search(t):
            continue
        
        # Skip lines that are only location (City, State)
        if _extract_location_from_line(t) and len(t) < 60 and ":" not in t and not any(c.isdigit() for c in t):
            continue
        
        # CRITICAL: Skip description text that appears before achievements
        # If this is a non-bullet line and we haven't found any achievements yet,
        # and it looks like flowing prose (no sentence-ending bullet pattern),
        # skip it as a job description
        if (not is_bullet_line and not current_achievement and 
            len(t) > 80 and not re.match(r'^[•\-*].*[.:;!?]$', t)):
            # This looks like a job description (long paragraph), skip it
            continue
        
        # Remove bullet formatting
        achievement = BULLET_RE.sub("", t).strip()
        
        # If this line doesn't start with a bullet, it's a continuation of the previous achievement
        if not is_bullet_line and current_achievement is not None and achievement:
            # Append to previous achievement with a space
            current_achievement = current_achievement + " " + achievement
            continue
        
        # This is a new bullet line - save the previous achievement if valid
        if current_achievement and len(current_achievement) > 10 and len(current_achievement) < 500:
            # Fix word-break artifacts first (2 nd -> 2nd, adopti on -> adoption)
            current_achievement = _fix_word_breaks_aggressive(current_achievement)
            # Apply targeted glue-word fixes
            current_achievement = normalize_bullet_text(current_achievement)
            
            # Check for character fragmentation
            has_character_fragmentation = bool(re.search(r'\b[a-z]\s+[a-z]\s+[a-z]\b', current_achievement))
            
            if has_character_fragmentation:
                # Use intelligent normalization for heavily corrupted text
                current_achievement = _normalize_achievement_intelligently(current_achievement)
                # Apply normalize again to fix any new issues
                current_achievement = normalize_bullet_text(current_achievement)
            
            experience["achievements"].append(current_achievement)
        
        # Start new achievement (or skip if it's too short)
        if achievement and len(achievement) > 10:
            current_achievement = achievement
        else:
            current_achievement = None
    
    # Don't forget the last achievement
    if current_achievement and len(current_achievement) > 10 and len(current_achievement) < 500:
        # Fix word-break artifacts first (2 nd -> 2nd, adopti on -> adoption)
        current_achievement = _fix_word_breaks_aggressive(current_achievement)
        # Apply targeted glue-word fixes
        current_achievement = normalize_bullet_text(current_achievement)
        
        # Check for character fragmentation
        has_character_fragmentation = bool(re.search(r'\b[a-z]\s+[a-z]\s+[a-z]\b', current_achievement))
        
        if has_character_fragmentation:
            # Use intelligent normalization for heavily corrupted text
            current_achievement = _normalize_achievement_intelligently(current_achievement)
            # Apply normalize again to fix any new issues
            current_achievement = normalize_bullet_text(current_achievement)
        
        experience["achievements"].append(current_achievement)
    
    return experience


def looks_like_education_line(line: str) -> bool:
    """
    Deterministic check: does this line have strong education signals?
    
    Uses only strong, unambiguous signals:
    - Degree keywords (Bachelor, Master, PhD, B.S., etc.)
    - Institution keywords (University, College, School, High School, etc.)
    - Study abroad keywords
    
    Returns True only if line clearly indicates education.
    """
    line_lower = line.lower()
    
    # Strong degree signals
    degree_terms = [
        "bachelor of", "bachelor's", 
        "master of", "master's",
        "associate of", "associate's",
        "doctorate", "doctoral",
        "phd", "ph.d.",
        "b.s.", "b.a.", "m.s.", "m.a.", "m.b.a.",
        "graduate degree", "postgraduate"
    ]
    
    # Strong institution signals
    institution_terms = [
        "university", "college", "institute",
        "academy", "high school", "secondary school",
        "prep school", "polytechnic", "school"
    ]
    
    # Study abroad signals
    study_abroad_terms = ["study abroad", "dis study", "isa study", "semester abroad", "year abroad"]
    
    # Check for any strong signal
    if any(term in line_lower for term in degree_terms):
        return True
    if any(term in line_lower for term in institution_terms):
        return True
    if any(term in line_lower for term in study_abroad_terms):
        return True
    
    return False


def parse_lines_to_response(
    lines: List[Tuple[str, str]],  # (locator, text)
    source: str,
) -> ParseResponse:
    def add_ev(evidence_map: Dict[str, List[EvidenceItem]], key: str, locator: str, text: str) -> None:
        evidence_map.setdefault(key, []).append(
            EvidenceItem(source=source, locator=locator, text=text.strip())
        )

    candidate = CandidateProfile()
    evidence_map: Dict[str, List[EvidenceItem]] = {}
    warnings: List[str] = []

    # --- 1) Extract phone + email first (anchors) ---
    # IMPORTANT: Extract phone BEFORE email to prevent phone digits from being
    # included in email user portion when they're on the same line
    email_idx = None
    phone_idx = None

    for idx, (locator, text) in enumerate(lines):
        t = _normalize_for_search(text)
        
        # Try to find phone in normalized text
        m = PHONE_RE.search(t)
        if m:
            # Extract phone from original text to preserve formatting
            # The matched pattern might be "( 555 ) 123-4567" in normalized
            # but we want "(555) 123-4567" from the original
            phone_digits = re.findall(r"\d+", m.group(1))
            if len(phone_digits) >= 3:  # At least area, exchange, line
                # Try to find the full phone in original text
                phone_pattern = r"(\(?\s*\d{3}\s*\)?\s*[-.]?\s*\d{3}\s*[-.]?\s*\d{4})"
                m_orig = re.search(phone_pattern, text)
                if m_orig:
                    candidate.phone = m_orig.group(1).replace(" ", "").replace("\t", "")
                    # Try to preserve original formatting if it's cleaner
                    if "(" in text and ")" in text:
                        # Has parens, try to extract with parens
                        m_formatted = re.search(r"\(\d{3}\)\s*\d{3}[-.]?\d{4}", text)
                        if m_formatted:
                            candidate.phone = m_formatted.group(0)
                    elif re.search(r"\d{3}[-.]?\d{3}[-.]?\d{4}", text):
                        # Try standard formats
                        m_std = re.search(r"\d{3}[-.]?\d{3}[-.]?\d{4}", text)
                        if m_std:
                            candidate.phone = m_std.group(0)
                else:
                    # Fallback to reconstructed phone from digits
                    if len(phone_digits) >= 4:
                        candidate.phone = f"({phone_digits[0]}){phone_digits[1]}-{phone_digits[2]}"
            add_ev(evidence_map, "phone", locator, text)  # keep ORIGINAL evidence text
            phone_idx = idx
            break

    for idx, (locator, text) in enumerate(lines):
        # IMPORTANT: do NOT use _normalize_for_search for emails
        raw = _despace_if_needed(text)
        raw_nospace = re.sub(r"\s+", "", raw)

        # Try to extract email (handles spaces around @ and .)
        email = extract_email_flexible(raw_nospace) or extract_email_flexible(raw)
        if email:
            candidate.email = email
            # Evidence keeps the original extracted text (may contain spaces)
            add_ev(evidence_map, "email", locator, text)
            email_idx = idx
            break


    # --- 2) Name extraction (caps-safe) ---
    # Preferred: look 1–3 lines above email (strongest deterministic signal)
    def looks_like_name(s: str) -> bool:
        raw = s.strip()
        t = _normalize_for_search(raw)

        if not t or len(t) > 60:
            return False
        if _is_header_line(t):
            return False
        # Must be letters/spaces/dots/hyphens/apostrophes
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,58}", t):
            return False
        # Must have at least 2 words (prevents "EXPERIENCE")
        if len(t.split()) < 2:
            return False
        return True
    
    def try_name_from_glued_top_line() -> bool:
        if candidate.full_name:
            return True
        if not lines:
            return False

        locator, raw = lines[0]
        t = _normalize_for_search(raw)

        # If we have an email, take substring before it (most resumes put name before email)
        if candidate.email and candidate.email in t:
            prefix = t.split(candidate.email, 1)[0].strip()
        else:
            prefix = t

        # Prefix often looks like: "JOHN DOE New York, New York ..."
        # Take first 2–4 Title-ish tokens that start with letters
        tokens = [tok for tok in prefix.split() if re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", tok)]
        if len(tokens) >= 2:
            # Most reliable: first two tokens
            name_guess = " ".join(tokens[:2])
            if not _is_header_line(name_guess):
                candidate.full_name = _normalize_name(name_guess)
                add_ev(evidence_map, "full_name", locator, raw)
                return True

        return False


    def try_name_from_window(center_idx: int | None) -> bool:
        if center_idx is None:
            return False
        start = max(0, center_idx - 3)
        end = center_idx  # exclusive
        for j in range(end - 1, start - 1, -1):  # closer lines first
            locator, text = lines[j]
            if looks_like_name(text):
                cleaned = _normalize_for_search(text)
                candidate.full_name = _normalize_name(cleaned)
                add_ev(evidence_map, "full_name", locator, text)
                return True
        return False

    got_name = try_name_from_window(email_idx)

    # Fallback: search top 10 non-empty lines (still header-safe)
    if not got_name:
        for locator, text in lines[:10]:
            if looks_like_name(text):
                cleaned = _normalize_for_search(text)
                candidate.full_name = _normalize_name(cleaned)
                add_ev(evidence_map, "full_name", locator, text)
                got_name = True
                break

    if not got_name:
        got_name = try_name_from_glued_top_line()



    # --- 3) Location extraction (near top OR near email/name) ---
    def maybe_set_location(idx: int, locator: str, text: str) -> None:
        if candidate.location:
            return
        t = _normalize_for_search(text)
        if len(t) > 200:
            return
        if _is_header_line(t):
            return
        
        location_text = _extract_location_from_line(t)
        m = LOCATION_RE.match(t) or location_text
        if m:
            matched_text = location_text if location_text else m.group(0)
            candidate.location = _format_location(matched_text)
            # Format the evidence text to preserve spaces
            formatted_evidence = _format_location(matched_text)
            add_ev(evidence_map, "location", locator, formatted_evidence)


    # Prefer top-of-document location line
    for idx, (locator, text) in enumerate(lines[:15]):
        maybe_set_location(idx, locator, text)

    # --- 4) Links ---
    links: List[str] = []
    for locator, text in lines:
        for rx in (LINKEDIN_RE, GITHUB_RE, URL_RE):
            t = _normalize_for_search(text)
            for m in rx.finditer(t):
                url = m.group(0)
                if url not in links:
                    links.append(url)
                    add_ev(evidence_map, "links", locator, text)
    candidate.links = links

    # --- 5) Skills extraction (improved) ---
    def _is_skills_header(text: str) -> bool:
        """Detect if a line is a skills section header."""
        # Match common skill section headers (with or without content after)
        return bool(re.match(
            r"^\s*(technical\s+|core\s+|additional\s+)?(skills|competencies|proficiencies|expertise|strengths)\s*:?",
            text,
            re.IGNORECASE
        ))

    def _extract_inline_skills(text: str) -> List[str]:
        """Extract comma-separated skills from a single line."""
        # Remove leading section headers like "Skills:" or "Technical Skills:"
        cleaned = re.sub(
            r"^\s*(technical\s+|core\s+|additional\s+)?(skills|competencies|proficiencies)\s*:?\s*",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()
        
        if not cleaned:
            return []
        
        # Split by comma, semicolon, or bullet (•)
        parts = re.split(r"[,;•]", cleaned)
        skills = []
        for part in parts:
            skill = part.strip()
            # Skip empty strings and very short strings (likely noise)
            if skill and len(skill) >= 2:
                skills.append(skill)
        return skills

    def _is_skill_bullet(text: str) -> bool:
        """Detect if a line is a skill bullet point."""
        t = text.strip()
        # Explicit bullet indicators: •, -, *, >
        if re.match(r"^[\s•\-*>]+[A-Za-z]", t):
            return True
        # Capitalized single-ish words (but not if they look like section headers)
        # "Python" = skill, "Additional Competencies" = subheader
        if re.match(r"^[A-Z][A-Za-z0-9\s\+#\-\.\/\(\)]*$", t):
            # Exclude if it looks like a subheading (multiple words with first letter caps, or known keywords)
            words = t.split()
            if len(words) > 3:  # Too many words for a skill
                return False
            # Check if it matches skill subheading patterns like "Languages:" "Frameworks:" etc.
            if re.match(r"^[A-Za-z]+\s*:", t):  # Pattern like "Languages:"
                return False
            return True
        return False

    skills: List[str] = []
    seen_skills = set()  # For deduplication
    skill_section_active = False
    
    for idx, (locator, text) in enumerate(lines):
        t = _normalize_for_search(text).strip()
        raw = text.strip()
        
        # Check if this is a skills section header
        if _is_skills_header(text):
            skill_section_active = True
            # Also extract inline skills if present (e.g., "Skills: Python, JavaScript")
            inline_skills = _extract_inline_skills(text)
            if inline_skills:
                for skill in inline_skills:
                    if skill not in seen_skills:
                        skills.append(skill)
                        seen_skills.add(skill)
                add_ev(evidence_map, "skills", locator, text)
            continue
        
        # If a skills section is active, collect bullet-point skills
        if skill_section_active:
            if not raw:
                # Empty line - continue within section
                continue
            
            # Check if we've hit another major section header (not blacklist, but obvious headers)
            if re.match(r"^[A-Z][A-Za-z\s]*$", raw) and len(raw.split()) <= 3 and _is_header_line(text):
                # This looks like a real section header (e.g., "EXPERIENCE", "EDUCATION")
                skill_section_active = False
                continue
            
            # Extract bullet-point skill
            if _is_skill_bullet(text):
                skill = raw
                # Remove bullet indicators
                skill = re.sub(r"^[\s•\-*>]+", "", skill).strip()
                
                if skill and len(skill) >= 2:
                    # Don't apply _is_header_line() here because "SQL", "AWS", etc are valid skills
                    if skill not in seen_skills:
                        skills.append(skill)
                        seen_skills.add(skill)
                        add_ev(evidence_map, "skills", locator, text)
            elif re.match(r"^[A-Za-z][A-Za-z0-9\s\+#\-\.\/\(\),]*:\s*", raw):
                # Subheading format like "Languages: Python, JavaScript"
                # Extract the part after the colon
                match = re.match(r"^[A-Za-z][A-Za-z0-9\s\+#\-\.\/\(\),]*:\s*(.*)", raw)
                if match:
                    remainder = match.group(1).strip()
                    # Parse comma or semicolon separated skills
                    parts = re.split(r"[,;•]", remainder)
                    for part in parts:
                        skill = part.strip()
                        if skill and len(skill) >= 2 and skill not in seen_skills:
                            skills.append(skill)
                            seen_skills.add(skill)
                    if remainder:
                        add_ev(evidence_map, "skills", locator, text)
    
    candidate.skills = skills

    # --- 7) SECTION STATE TRACKING (EXPLICIT, NON-NEGOTIABLE) ---
    # Track current section state as we parse through resume
    current_section = None
    section_headers_found = {}  # Map of section_type -> line_index
    
    # Scan through ALL lines and detect section headers
    for idx, (locator, text) in enumerate(lines):
        section_type = detect_section_type(text)
        if section_type:
            logger.debug(f"SECTION HEADER DETECTED at line {idx}: '{text.strip()}' -> section_type='{section_type}'")
            section_headers_found[section_type] = idx
    
    edu_section_idx = section_headers_found.get("education")
    exp_section_idx = section_headers_found.get("experience")
    
    logger.debug(f"Section detection results:")
    logger.debug(f"  - EDUCATION section at index: {edu_section_idx}")
    logger.debug(f"  - EXPERIENCE section at index: {exp_section_idx}")
    
    # --- 7a) EDUCATION SECTION DETECTION (MUST RUN BEFORE EXPERIENCE) ---
    educations: List[EducationEntry] = []
    
    # --- 7b) Experience extraction (GATED by education section) ---
    experiences: List[Dict] = []
    
    # SOFT GATE: If both sections exist, experience parser will stop at education naturally
    # The _group_experience_entries function already detects and stops at major section headers
    logger.debug(f"Processing section order: edu={edu_section_idx}, exp={exp_section_idx}")
    
    if edu_section_idx is not None and exp_section_idx is not None:
        if edu_section_idx < exp_section_idx:
            logger.debug("EDUCATION section comes BEFORE EXPERIENCE - experience parser will stop at education")
        else:
            logger.debug("EDUCATION section comes AFTER EXPERIENCE - experience parser will include entries until education")
    
    if exp_section_idx is not None:
        logger.debug(f"Starting EXPERIENCE parsing from line {exp_section_idx}")
        entry_groups = _group_experience_entries(lines, exp_section_idx)
        for entry_lines in entry_groups:
            exp_dict = _parse_experience_entry(entry_lines)
            # Track evidence for this experience
            if exp_dict["company"] or exp_dict["job_title"]:
                logger.debug(f"  -> Found experience entry: company='{exp_dict.get('company')}', title='{exp_dict.get('job_title')}'")
                # For now, add all lines as evidence
                for locator, text in entry_lines:
                    if exp_dict["company"] or exp_dict["job_title"] or exp_dict["achievements"]:
                        add_ev(evidence_map, "experiences", locator, text)
                experiences.append(exp_dict)
    else:
        logger.debug("SKIPPING experience parsing (no EXPERIENCE section found or blocked by education)")
    
    # --- CRITICAL: RECLASSIFICATION PASS (Final routing before assignment) ---
    # Some education entries may have been parsed as experience entries.
    # This is the MANDATORY step to ensure education never remains in experiences[].
    
    def looks_like_education_entry(exp: Dict) -> bool:
        """
        Deterministically detect if an experience entry is actually education.
        Uses strong signals only (no heuristics).
        """
        company = (exp.get("company") or "").lower()
        title = (exp.get("job_title") or "").lower()
        location = (exp.get("location") or "").lower()
        text = f"{company} {title} {location}"
        
        # Degree keywords
        degree_terms = [
            "bachelor", "master", "associate", "phd", "ph.d", "doctorate",
            "b.s.", "b.a.", "m.s.", "m.a.", "m.b.a.", "b.sc", "m.sc",
            "undergraduate", "graduate", "diploma"
        ]
        
        # Institution keywords
        institution_terms = [
            "university", "college", "institute", "academy", 
            "high school", "school", "polytechnic"
        ]
        
        # Study abroad keywords
        study_abroad_terms = [
            "study abroad", "dis study", "isa study", 
            "semester abroad", "exchange program"
        ]
        
        # Check for strong education signals
        has_degree = any(term in text for term in degree_terms)
        has_institution = any(term in text for term in institution_terms)
        has_study_abroad = any(term in text for term in study_abroad_terms)
        
        return has_degree or has_institution or has_study_abroad
    
    def convert_experience_to_education(exp: Dict) -> 'EducationEntry':
        """
        Convert experience-shaped dict to EducationEntry object.
        This fixes the shape mismatch that causes education to be stuck as experience.
        """
        from app.core.schemas import EducationEntry
        
        company = exp.get("company", "")
        title = exp.get("job_title", "")
        
        # Extract degree and field of study from job_title
        degree = None
        field_of_study = None
        
        title_lower = title.lower()
        if any(term in title_lower for term in ["bachelor", "b.s.", "b.a.", "b.sc"]):
            degree = title
        elif any(term in title_lower for term in ["master", "m.s.", "m.a.", "m.b.a.", "m.sc"]):
            degree = title
        elif any(term in title_lower for term in ["associate", "a.a.", "a.s."]):
            degree = title
        elif any(term in title_lower for term in ["ph.d", "phd", "doctorate"]):
            degree = title
        elif "major" in title_lower:
            # "Applied Communications Major" -> field of study
            field_of_study = title.replace("Major", "").replace("major", "").strip()
        
        return EducationEntry(
            institution=company,
            degree=degree,
            field_of_study=field_of_study,
            location=exp.get("location"),
            start_date=exp.get("start_date"),
            end_date=exp.get("end_date"),
            gpa=None,
            details=exp.get("achievements", [])
        )
    
    def split_experience_and_education(experiences: List[Dict]) -> Tuple[List[Dict], List['EducationEntry']]:
        """
        Final authoritative reclassification pass.
        Ensures education entries NEVER remain in experiences[] at response time.
        """
        true_experiences = []
        reclassified_education = []
        
        for exp in experiences:
            if looks_like_education_entry(exp):
                logger.debug(f"RECLASSIFICATION: Moving '{exp.get('company')}' from experience to education")
                edu_entry = convert_experience_to_education(exp)
                reclassified_education.append(edu_entry)
            else:
                true_experiences.append(exp)
        
        return true_experiences, reclassified_education
    
    # NOTE: Reclassification moved AFTER education parsing (see below)
    # This ensures properly parsed education entries are not overwritten by old-logic conversions

    # --- 7c) Education extraction (SECTION-GATED, high priority) ---
    """
    Extract education entries with section-aware classification.
    
    Separates education from experience using:
    1. Section headers (EDUCATION, ACADEMIC BACKGROUND, etc.)
    2. Degree keywords (Bachelor, Master, B.S., PhD, etc.)
    3. Institution keywords (University, College, School, etc.)
    4. High school detection
    5. Study abroad program detection
    """
    
    def _group_education_entries(
        lines_to_group: List[Tuple[str, str]],
        section_start_idx: int
    ) -> List[List[Tuple[str, str]]]:
        """
        Group consecutive lines into education entries.
        
        Strategy:
          1. Skip the header line itself
          2. Skip empty lines
          3. Detect entry boundaries:
             - Lines with institution+degree keywords
             - Lines with dates (education format: dates on their own line)
             - Multi-line blocks with cohesive content
          4. Continue grouping until we hit another major section header
        
        Returns list of education entry groups.
        """
        entries: List[List[Tuple[str, str]]] = []
        current_entry: List[Tuple[str, str]] = []
        
        for idx in range(section_start_idx + 1, len(lines_to_group)):
            locator, text = lines_to_group[idx]
            t = text.strip()
            
            # Empty line - skip but stay in current entry
            if not t:
                continue
            
            # Hit another major section header -> end education grouping
            if _is_header_line(text) and not BULLET_RE.match(t) and idx > section_start_idx + 2:
                if re.match(r"^[A-Z][A-Za-z\s/&-]*$", t) and len(t.split()) <= 5:
                    if current_entry:
                        entries.append(current_entry)
                        current_entry = []
                    break
            
            # Detect start of new education entry
            is_new_entry_start = False
            
            # Strong signals for new entry:
            # 1. Line contains institution keyword (University, College, etc.)
            # Institution keywords are the PRIMARY anchor for new education entries
            if is_institution_keyword(t):
                is_new_entry_start = True
            # 2. Line is high school
            elif is_high_school(t):
                is_new_entry_start = True
            # 3. Line is study abroad
            elif is_study_abroad(t):
                is_new_entry_start = True
            # 4. Degree keyword ONLY starts new entry if we haven't started an entry yet
            # (prevents "Bachelor of Science..." from splitting an existing institution entry)
            elif has_degree_keyword(t) and not current_entry:
                is_new_entry_start = True
            # 5. Heuristic: Location-only line at start of new entry
            # (Only treat location as new entry start if we haven't started an entry yet OR
            # it's a completely different location that suggests a new institution)
            elif not BULLET_RE.match(t) and _extract_location_from_line(t) is not None and len(t) < 150:
                # Only treat as new entry if:
                # a) We have no current entry (first entry), OR
                # b) The previous line(s) already have a location (suggesting this is new institution)
                if not current_entry:
                    is_new_entry_start = True
                else:
                    # Check if previous lines already have location extracted
                    prev_text = " ".join([text for _, text in current_entry])
                    if not _extract_location_from_line(prev_text):
                        # Previous entry has no location yet, so this location belongs to it
                        is_new_entry_start = False
                    else:
                        # Previous entry already has location, so this is probably a new entry
                        is_new_entry_start = True
            
            if is_new_entry_start and current_entry:
                entries.append(current_entry)
                current_entry = [(locator, text)]
            else:
                current_entry.append((locator, text))
        
        # Don't forget the last entry
        if current_entry:
            entries.append(current_entry)
        
        return entries
    
    # Import education functions once at the start
    from app.core.education_parser import (
        classify_entry_as_education, parse_education_entry
    )
    
    # Now process education section with proper logging
    if edu_section_idx is not None:
        logger.debug(f"Starting EDUCATION parsing from line {edu_section_idx}")
        edu_entry_groups = _group_education_entries(lines, edu_section_idx)
        logger.debug(f"  -> Found {len(edu_entry_groups)} education entry groups")
        
        for entry_lines in edu_entry_groups:
            # Check if this should really be education (use context)
            entry_text_lines = [text.strip() for locator, text in entry_lines]
            should_be_education = classify_entry_as_education(entry_text_lines, current_section="education")
            
            if should_be_education:
                education_entry, edu_warnings = parse_education_entry(entry_lines, current_section="education")
                
                if education_entry.institution or education_entry.degree:
                    logger.debug(f"  -> Found education entry: institution='{education_entry.institution}', degree='{education_entry.degree}'")
                    # Track evidence
                    for locator, text in entry_lines:
                        add_ev(evidence_map, "education", locator, text)
                    
                    educations.append(education_entry)
                    warnings.extend(edu_warnings)
    
    # --- GUARDRAIL: Warn if EDUCATION section exists but yielded nothing ---
    if edu_section_idx is not None and not educations:
        warnings.append("EDUCATION header found but no education entries parsed")
    
    # --- FALLBACK: Education Safety Net (Only if no explicit EDUCATION header found) ---
    # If we haven't found any education entries through explicit EDUCATION section,
    # scan remaining lines for strong education signals as a last resort.
    if not educations and edu_section_idx is None:
        logger.warning("Education fallback triggered: no EDUCATION header found, scanning for education entries")
        
        # Scan for lines with education signals, then collect surrounding context
        fallback_block_lines = []
        in_education_block = False
        
        for idx, (locator, text) in enumerate(lines):
            t = text.strip()
            
            # Stop at experience section
            if exp_section_idx is not None and idx >= exp_section_idx:
                break
            
            # Skip empty lines
            if not t:
                if in_education_block:
                    # Blank line ends the current education block
                    in_education_block = False
                continue
            
            # Skip section headers
            if _is_header_line(text):
                in_education_block = False
                continue
            
            # Check if this line starts a new education block
            if looks_like_education_line(t) and not BULLET_RE.match(t):
                in_education_block = True
                fallback_block_lines.append((idx, locator, text))
            elif in_education_block:
                # Include lines that are part of education blocks (locations, dates, bullets, details)
                fallback_block_lines.append((idx, locator, text))
        
        # Now use the standard grouping logic on these lines, but specifically for education
        if fallback_block_lines:
            # Convert back to the format expected by _group_education_entries
            # We need to simulate having an education section at index -1 so the grouping works
            fallback_lines_for_grouping = [(locator, text) for idx, locator, text in fallback_block_lines]
            
            # Manually group into education entries using looser logic
            current_group = []
            
            for idx, (locator, text) in enumerate(fallback_lines_for_grouping):
                t = text.strip()
                
                # Check if this line starts a new education entry
                is_new_entry_marker = looks_like_education_line(t) and not BULLET_RE.match(t)
                
                # If this is a new entry marker and we have a current group, save the current group
                if is_new_entry_marker and current_group:
                    # Try to parse the previous group
                    entry, _ = parse_education_entry(current_group, current_section="education")
                    if entry.institution or entry.degree:
                        # Deduplication
                        is_duplicate = any(
                            existing.institution == entry.institution and
                            existing.degree == entry.degree
                            for existing in educations
                        )
                        if not is_duplicate:
                            logger.debug(f"Fallback: Created education entry: {entry.institution}")
                            for loc, txt in current_group:
                                add_ev(evidence_map, "education", loc, txt)
                            educations.append(entry)
                    current_group = [(locator, text)]
                else:
                    current_group.append((locator, text))
            
            # Don't forget the last group
            if current_group:
                entry, _ = parse_education_entry(current_group, current_section="education")
                if entry.institution or entry.degree:
                    is_duplicate = any(
                        existing.institution == entry.institution and
                        existing.degree == entry.degree
                        for existing in educations
                    )
                    if not is_duplicate:
                        logger.debug(f"Fallback: Created education entry: {entry.institution}")
                        for loc, txt in current_group:
                            add_ev(evidence_map, "education", loc, txt)
                        educations.append(entry)
    
    # --- RECLASSIFICATION: Fallback only when education parsing yielded nothing ---
    # If EDUCATION section was successfully parsed, do NOT run reclassification.
    # Reclassification uses old logic (no bullet-first, no study abroad regex, no degree split)
    # and would overwrite properly parsed entries.
    reclassified_educations = []
    if not educations:
        logger.debug("Running experience→education reclassification (fallback only)")
        experiences, reclassified_educations = split_experience_and_education(experiences)
        logger.debug(f"Reclassified: {len(reclassified_educations)} experiences moved to education")
    else:
        logger.debug(f"Skipping reclassification: {len(educations)} education entries already parsed")
    
    candidate.experiences = experiences
    
    # --- MERGE: Combine reclassified education with parsed education ---
    # Prefer parser-generated entries over reclassified ones (parser has better logic)
    all_education_entries = educations + reclassified_educations
    
    # Deduplication: Remove duplicates, preferring entries with more populated fields
    # (parser-generated entries are better than reclassified conversions)
    seen_education = {}
    unique_education = []
    for edu in all_education_entries:
        key = (edu.institution or "", edu.degree or "")
        if key not in seen_education and (edu.institution or edu.degree):
            seen_education[key] = edu
            unique_education.append(edu)
        elif key in seen_education:
            # Keep entry with more populated fields (field_of_study, dates, details)
            existing = seen_education[key]
            edu_score = sum([
                1 if edu.field_of_study else 0,
                1 if edu.start_date else 0,
                1 if edu.end_date else 0,
                len(edu.details) if edu.details else 0
            ])
            existing_score = sum([
                1 if existing.field_of_study else 0,
                1 if existing.start_date else 0,
                1 if existing.end_date else 0,
                len(existing.details) if existing.details else 0
            ])
            if edu_score > existing_score:
                # Replace with better entry
                idx = unique_education.index(existing)
                unique_education[idx] = edu
                seen_education[key] = edu
    
    logger.debug(f"Final education count: {len(unique_education)} (after merging reclassified + deduplication)")
    candidate.education = unique_education
    
    # --- GUARDRAIL: Warning if no education detected ---
    if not candidate.education:
        warnings.append("No education entries detected in resume")

    # --- 8) Confidence Scoring ---
    """
    Calculate per-field confidence scores to inform downstream consumers
    whether extraction is reliable or needs clarification.
    """
    confidence_scores: Dict[str, FieldConfidence] = {}
    
    # Email confidence
    if candidate.email:
        email_evidence_count = len(evidence_map.get("email", []))
        conf, method = ConfidenceCalculator.email(candidate.email, email_evidence_count)
        confidence_scores["email"] = FieldConfidence(
            field_name="email",
            confidence=conf,
            extraction_method=method,
            reasons=["Found via regex extraction"],
            required=True,
        )
    else:
        confidence_scores["email"] = FieldConfidence(
            field_name="email",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No email found in resume"],
            required=True,
        )
    
    # Phone confidence
    if candidate.phone:
        phone_evidence_count = len(evidence_map.get("phone", []))
        conf, method = ConfidenceCalculator.phone(candidate.phone, phone_evidence_count)
        confidence_scores["phone"] = FieldConfidence(
            field_name="phone",
            confidence=conf,
            extraction_method=method,
            reasons=["Found via regex extraction"],
            required=True,
        )
    else:
        confidence_scores["phone"] = FieldConfidence(
            field_name="phone",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No phone number found in resume"],
            required=True,
        )
    
    # Full name confidence
    if candidate.full_name:
        near_email = email_idx is not None and email_idx >= 0
        is_top = any(ev.locator.startswith("docx:paragraph:0") or ev.locator.startswith("pdf:page:1:line:")
                    for ev in evidence_map.get("full_name", []))
        
        conf, method = ConfidenceCalculator.full_name(
            candidate.full_name,
            near_email=near_email,
            is_top_of_resume=is_top,
            passes_blacklist=True,
            has_middle_initial=" " in candidate.full_name and len(candidate.full_name.split()) >= 3,
        )
        confidence_scores["full_name"] = FieldConfidence(
            field_name="full_name",
            confidence=conf,
            extraction_method=method,
            reasons=["Extracted from resume header area", f"Near email: {near_email}", f"At top: {is_top}"],
            required=True,
        )
    else:
        confidence_scores["full_name"] = FieldConfidence(
            field_name="full_name",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No candidate name found"],
            required=True,
        )
    
    # Location confidence
    if candidate.location:
        has_comma = "," in candidate.location
        conf, method = ConfidenceCalculator.location(
            candidate.location,
            extraction_method="regex_pattern",
            has_comma=has_comma,
            is_valid_format=has_comma,
        )
        confidence_scores["location"] = FieldConfidence(
            field_name="location",
            confidence=conf,
            extraction_method=method,
            reasons=["Extracted from geographic pattern"],
            required=False,
        )
    else:
        confidence_scores["location"] = FieldConfidence(
            field_name="location",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No location found"],
            required=False,
        )
    
    # Links confidence
    if candidate.links:
        confidence_scores["links"] = FieldConfidence(
            field_name="links",
            confidence=0.95,
            extraction_method="regex_url_extraction",
            reasons=[f"Found {len(candidate.links)} URL(s) via regex"],
            required=False,
        )
    else:
        confidence_scores["links"] = FieldConfidence(
            field_name="links",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No URLs found"],
            required=False,
        )
    
    # Skills confidence
    if candidate.skills:
        confidence_scores["skills"] = FieldConfidence(
            field_name="skills",
            confidence=0.85,
            extraction_method="section_extraction",
            reasons=[f"Found {len(candidate.skills)} skills"],
            required=False,
        )
    else:
        confidence_scores["skills"] = FieldConfidence(
            field_name="skills",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No skills found"],
            required=False,
        )
    
    # Experiences confidence
    if experiences:
        confidence_scores["experiences"] = FieldConfidence(
            field_name="experiences",
            confidence=0.85,
            extraction_method="multi_line_experience_parsing",
            reasons=[f"Found {len(experiences)} experience entries"],
            required=False,
        )
    else:
        confidence_scores["experiences"] = FieldConfidence(
            field_name="experiences",
            confidence=0.0,
            extraction_method="not_found",
            reasons=["No experience section found"],
            required=False,
        )

    # --- 9) Parse quality (now confidence-informed) ---
    found = sum(1 for v in [candidate.full_name, candidate.email, candidate.phone] if v)
    has_experiences = len(experiences) > 0
    
    # Use confidence-based calculation
    parse_quality = ConfidenceCalculator.calculate_overall_parse_quality({
        field: conf.confidence for field, conf in confidence_scores.items()
    })
    
    # Warnings based on low-confidence fields
    if confidence_scores.get("email", FieldConfidence(field_name="email", confidence=0.0, extraction_method="")).confidence < 0.8:
        if not candidate.email:
            warnings.append("Could not extract email. User clarification needed.")
        else:
            warnings.append(f"Email extraction has low confidence: {confidence_scores['email'].confidence:.2f}")
    
    if confidence_scores.get("full_name", FieldConfidence(field_name="full_name", confidence=0.0, extraction_method="")).confidence < 0.8:
        if not candidate.full_name:
            warnings.append("Could not extract candidate name. User clarification needed.")
        else:
            warnings.append(f"Name extraction has low confidence: {confidence_scores['full_name'].confidence:.2f}")

    # Stable keys for contract
    for key in ["full_name", "email", "phone", "location", "links", "skills", "experiences", "education"]:
        evidence_map.setdefault(key, [])

    return ParseResponse(
        candidate_profile=candidate,
        evidence_map=evidence_map,
        confidence_scores=confidence_scores,
        parse_quality=parse_quality,
        warnings=warnings,
    )
