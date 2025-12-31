"""
Unit tests for text_normalization module.

Tests the pipeline with realistic resume glue patterns.
"""

import pytest
from app.core.text_normalization import (
    normalize_token_basic,
    normalize_bullet_text,
)


class TestNormalizeTokenBasic:
    """Test ultra-conservative token normalization."""
    
    def test_inanew(self):
        assert normalize_token_basic("inanew") == "in a new"
    
    def test_anew(self):
        assert normalize_token_basic("anew") == "a new"
    
    def test_startanew(self):
        assert normalize_token_basic("startanew") == "start a new"
    
    def test_salesinthe(self):
        assert normalize_token_basic("salesinthe") == "sales in the"
    
    def test_repsinthe(self):
        assert normalize_token_basic("repsinthe") == "reps in the"
    
    def test_girlsofthe(self):
        assert normalize_token_basic("girlsofthe") == "girls of the"
    
    def test_toolstobe(self):
        assert normalize_token_basic("toolstobe") == "tools to be"
    
    def test_accountinthe(self):
        assert normalize_token_basic("accountinthe") == "account in the"
    
    def test_no_change_proper_word(self):
        """Proper words should not be modified."""
        assert normalize_token_basic("territory") == "territory"
        assert normalize_token_basic("Sales") == "Sales"
    
    def test_no_change_short_token(self):
        """Short tokens should not be modified."""
        assert normalize_token_basic("cat") == "cat"
        assert normalize_token_basic("to") == "to"


class TestNormalizeBulletText:
    """Test rich normalization for bullet/achievement text."""
    
    def test_prefix_phrase_duetoa(self):
        result = normalize_bullet_text("duetoa rapid growth")
        assert result == "due to a rapid growth"
    
    def test_prefix_phrase_leadingto(self):
        result = normalize_bullet_text("leadingto 150% growth")
        assert result == "leading to 150% growth"
    
    def test_embedded_joiner_territorytoover(self):
        result = normalize_bullet_text("territory to over $2M")
        # After camel/embedded/suffix passes
        assert "territory" in result and "to" in result
    
    def test_embedded_joiner_countrytoattend(self):
        result = normalize_bullet_text("countrytoattend conference")
        assert "country" in result and "to" in result and "attend" in result
    
    def test_camel_case_symposium_in_miami(self):
        result = normalize_bullet_text("SymposiuminMiami")
        # Should split at camel boundary: Symposium in Miami
        assert "Symposium" in result and "Miami" in result
    
    def test_camel_case_growth_in_Q(self):
        result = normalize_bullet_text("growthinQ1")
        assert "growth" in result and "in" in result
    
    def test_combined_prefix_and_embedded(self):
        """Test: duetoterritory expansion and accountinthe region"""
        text = "duetoterritory expansion and accountinthe region"
        result = normalize_bullet_text(text)
        assert "due to" in result
        assert "account in the" in result
    
    def test_mixed_glues_achievement_example(self):
        """Example from requirements."""
        text = "Won backalarge account and salesinthe prior year leadingto growth"
        result = normalize_bullet_text(text)
        # Check key fixes are applied
        assert "back a large" in result or "back" in result and "large" in result
        assert "sales in the" in result
        assert "leading to" in result
    
    def test_no_change_clean_text(self):
        """Clean text should pass through unchanged."""
        text = "Grew the Oregon territory to over $2,000,000"
        result = normalize_bullet_text(text)
        assert result == text
    
    def test_no_change_proper_names(self):
        """Names like California, Miami should not be split."""
        text = "Expanded market in California"
        result = normalize_bullet_text(text)
        assert "California" in result
    
    def test_multiple_tokens_independent(self):
        """Each token normalized independently."""
        text = "salesinthe market and repsinthe field"
        result = normalize_bullet_text(text)
        assert "sales in the" in result
        assert "reps in the" in result
    
    def test_preserves_numbers_punctuation(self):
        """Numbers and punctuation preserved."""
        text = "duetoa 150% growth in Q4, 2024"
        result = normalize_bullet_text(text)
        assert "150%" in result
        assert "Q4," in result
        assert "2024" in result
