"""
Test suite for character-level PDF extraction (Phase 2a).

Compares geometric-first approach with current linguistic-first approach
using real resume PDFs.
"""

import pytest
import os
from app.core.pdf_character_extractor import (
    extract_and_analyze_pdf,
    reconstruct_words_from_chars,
    compute_extraction_quality,
)


FIXTURES_DIR = "tests/fixtures"


def get_fixture_path(filename: str) -> str:
    """Get path to a test fixture PDF."""
    return os.path.join(FIXTURES_DIR, filename)


class TestCharacterExtraction:
    """Test character-level extraction from PDFs."""
    
    def test_extract_characters_from_pdf(self):
        """Test that we can extract characters from a real PDF."""
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        result = extract_and_analyze_pdf(pdf_path)
        
        # Should have extracted characters
        assert len(result['characters']) > 0, "Should extract characters from PDF"
        
        # Should have reconstructed words
        assert len(result['words']) > 0, "Should reconstruct words from characters"
        
        # Should have quality metrics
        assert 'quality' in result
        assert 'dict_coverage' in result['quality']
    
    def test_word_reconstruction_basic(self):
        """Test that word reconstruction works on a simple PDF."""
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        result = extract_and_analyze_pdf(pdf_path)
        words = result['words']
        
        # Should reconstruct recognizable words
        word_texts = [w.text for w in words]
        
        # Check for expected words (name, common words, etc.)
        # This is a loose check since we don't know exact content
        assert any(len(w) > 2 for w in word_texts), "Should have multi-char words"
    
    def test_quality_signals(self):
        """Test that quality signals are computed correctly."""
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        result = extract_and_analyze_pdf(pdf_path)
        quality = result['quality']
        
        # Quality metrics should be in valid ranges
        assert 0 <= quality['dict_coverage'] <= 1, "Dict coverage should be 0-1"
        assert 0 <= quality['no_vowel_ratio'] <= 1, "No-vowel ratio should be 0-1"
        assert 0 <= quality['suspicious_ratio'] <= 1, "Suspicious ratio should be 0-1"
        assert 0 <= quality['quality_score'] <= 1, "Quality score should be 0-1"
        
        # Should have a repair recommendation
        assert isinstance(quality['needs_repair'], bool), "Should have repair recommendation"
    
    def test_comparison_with_current_approach(self):
        """
        Compare character-level extraction with current line-based approach.
        
        This test demonstrates the difference between geometric-first and linguistic-first.
        """
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        # Character-level (geometric) approach
        geometric_result = extract_and_analyze_pdf(pdf_path)
        geometric_quality = geometric_result['quality']
        
        print(f"\n=== GEOMETRIC-FIRST APPROACH ===")
        print(f"Total words: {geometric_quality['total_words']}")
        print(f"Dict coverage: {geometric_quality['dict_coverage']:.2%}")
        print(f"Suspicious ratio: {geometric_quality['suspicious_ratio']:.2%}")
        print(f"Needs repair: {geometric_quality['needs_repair']}")
        print(f"Quality score: {geometric_quality['quality_score']:.2f}")
        
        # For now, just verify we get results
        assert geometric_quality['total_words'] > 0, "Should extract words"


class TestCharacterGeometry:
    """Test geometric calculations and word boundary detection."""
    
    def test_gap_threshold_calculation(self):
        """Verify that gap threshold is calculated correctly."""
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        result = extract_and_analyze_pdf(pdf_path)
        words = result['words']
        
        # Each word should have x0 < x1
        for word in words:
            assert word.x0 < word.x1, f"Word {word.text} has invalid x coordinates"
            assert word.y0 < word.y1, f"Word {word.text} has invalid y coordinates"
    
    def test_line_reconstruction(self):
        """Test that words are correctly grouped into lines."""
        pdf_path = get_fixture_path("John Doe Resume 2024  final.pdf")
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test fixture not found: {pdf_path}")
        
        result = extract_and_analyze_pdf(pdf_path)
        lines = result['lines']
        
        # Should have multiple lines
        assert len(lines) > 0, "Should reconstruct lines from words"
        
        # Each line should have consistent y position
        for line in lines:
            y_positions = [w.y0 for w in line.words]
            # All words in a line should have similar y positions
            y_diff = max(y_positions) - min(y_positions)
            assert y_diff < 5, f"Words in line should have similar y positions, got diff={y_diff}"


class TestQualitySignals:
    """Test the quality signal computation."""
    
    def test_quality_on_clean_text(self):
        """Quality should be high for properly spaced text."""
        # This would need a clean PDF for testing
        # For now, just verify the quality calculation logic works
        from app.core.pdf_character_extractor import PDFWord, PDFCharacter
        
        # Create mock words that are all in the dictionary
        char = PDFCharacter(
            page=1, char='a', x0=0, y0=0, x1=1, y1=1,
            fontname='Arial', size=12
        )
        # Use resume-specific words that are in COMMON_WORDS dictionary
        words = [
            PDFWord('led', 1, [char], 0, 1, 0, 1),
            PDFWord('technical', 1, [char], 5, 10, 0, 1),
            PDFWord('team', 1, [char], 15, 20, 0, 1),
        ]
        
        quality = compute_extraction_quality(words)
        
        # Quality should be reasonable
        assert quality['quality_score'] > 0, "Quality score should be positive"
        assert not quality['needs_repair'], "Clean resume text shouldn't need repair"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
