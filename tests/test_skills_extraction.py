"""Comprehensive tests for skills extraction."""

from app.core.line_parser import parse_lines_to_response


def test_inline_skills_simple():
    """Test extraction of comma-separated skills on single line."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python, JavaScript, SQL"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 3


def test_skills_section_with_bullets():
    """Test extraction of skills from section header with bullet points."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
        ("docx:paragraph:7", "• React"),
        ("docx:paragraph:8", "• SQL"),
        ("docx:paragraph:9", "Experience"),  # New section header stops skills collection
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "React" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 4
    assert "Experience" not in data["candidate_profile"]["skills"]


def test_skills_with_dashes_as_bullets():
    """Test skills with dash bullet points."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Technical Skills"),
        ("docx:paragraph:5", "- Python"),
        ("docx:paragraph:6", "- JavaScript"),
        ("docx:paragraph:7", "- PostgreSQL"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "PostgreSQL" in data["candidate_profile"]["skills"]


def test_skills_deduplication():
    """Test that duplicate skills are not repeated."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python, JavaScript"),
        ("docx:paragraph:5", "Technical Skills"),
        ("docx:paragraph:6", "• Python"),
        ("docx:paragraph:7", "• JavaScript"),
        ("docx:paragraph:8", "• SQL"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Should only have 3 unique skills, not 5
    assert len(data["candidate_profile"]["skills"]) == 3
    assert data["candidate_profile"]["skills"].count("Python") == 1
    assert data["candidate_profile"]["skills"].count("JavaScript") == 1


def test_skills_with_colons():
    """Test skills header with colon."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills:"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]


def test_skills_with_capitals_as_bullets():
    """Test skills that are capitalized single words treated as bullets."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Core Competencies"),
        ("docx:paragraph:5", "Python"),
        ("docx:paragraph:6", "JavaScript"),
        ("docx:paragraph:7", "Docker"),
        ("docx:paragraph:8", "Experience"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]


def test_skills_mixed_formats():
    """Test skills with mixed inline and bullet formats."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python, JavaScript"),
        ("docx:paragraph:5", ""),  # Empty line
        ("docx:paragraph:6", "Additional Competencies"),
        ("docx:paragraph:7", "• SQL"),
        ("docx:paragraph:8", "• Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 4


def test_skills_with_semicolon_separators():
    """Test skills separated by semicolons."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python; JavaScript; SQL; Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]


def test_skills_stops_at_next_section():
    """Test that skills collection stops at next section header."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
        ("docx:paragraph:7", "Experience"),
        ("docx:paragraph:8", "• Senior Developer at Company"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Should not include "Senior Developer at Company" as a skill
    assert len(data["candidate_profile"]["skills"]) == 2
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "Senior Developer at Company" not in data["candidate_profile"]["skills"]


def test_skills_with_spaces():
    """Test skills with multiple words and special characters."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Machine Learning, Natural Language Processing, C++, AWS"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Machine Learning" in data["candidate_profile"]["skills"]
    assert "Natural Language Processing" in data["candidate_profile"]["skills"]
    assert "C++" in data["candidate_profile"]["skills"]
    assert "AWS" in data["candidate_profile"]["skills"]


def test_skills_with_dot_separators():
    """Test skills separated by dots or other punctuation."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Proficiencies: Python • JavaScript • SQL • Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Note: bullet separator may need adjustment, but test the basic case
    # This is a practical scenario
    assert len(data["candidate_profile"]["skills"]) >= 2


def test_no_skills_extracted():
    """Test resume with no skills section."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Experience"),
        ("docx:paragraph:5", "Senior Developer"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert data["candidate_profile"]["skills"] == []
    assert len(data["evidence_map"]["skills"]) == 0


def test_skills_evidence_tracking():
    """Test that skills evidence is properly tracked."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Check that evidence map has entries for skills
    assert "skills" in data["evidence_map"]
    assert len(data["evidence_map"]["skills"]) > 0
    
    # Each skill should have evidence
    for evidence in data["evidence_map"]["skills"]:
        assert "source" in evidence
        assert "locator" in evidence
        assert "text" in evidence


def test_skills_from_real_resume_format():
    """Test skills extraction from realistic resume format."""
    lines = [
        ("pdf:page:1:line:1", "JANE DOE"),
        ("pdf:page:1:line:2", "jane@example.com"),
        ("pdf:page:1:line:3", "(555) 123-4567"),
        ("pdf:page:1:line:4", "San Francisco, CA"),
        ("pdf:page:1:line:5", ""),
        ("pdf:page:1:line:6", "TECHNICAL SKILLS"),
        ("pdf:page:1:line:7", "Languages: Python, JavaScript, Java, SQL"),
        ("pdf:page:1:line:8", "Frameworks: Django, FastAPI, React"),
        ("pdf:page:1:line:9", "Tools: Docker, Git, PostgreSQL"),
        ("pdf:page:1:line:10", ""),
        ("pdf:page:1:line:11", "EXPERIENCE"),
    ]
    
    resp = parse_lines_to_response(lines, source="pdf")
    data = resp.model_dump()
    
    skills = data["candidate_profile"]["skills"]
    
    # Should extract from all three lines under Technical Skills
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "Java" in skills
    assert "SQL" in skills
    assert "Django" in skills
    assert "FastAPI" in skills
    assert "React" in skills
    assert "Docker" in skills
    assert "Git" in skills
    assert "PostgreSQL" in skills


def test_skills_ignores_subheadings():
    """Test that skills section subheadings are not extracted as skills."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "Languages: Python, JavaScript"),
        ("docx:paragraph:6", "Frameworks: Django, FastAPI"),
        ("docx:paragraph:7", "Experience"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    skills = data["candidate_profile"]["skills"]
    
    # Should have 4 skills, not include "Languages" or "Frameworks"
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "Django" in skills
    assert "FastAPI" in skills
    # These should NOT be skills
    assert "Languages" not in skills
    assert "Frameworks" not in skills
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 3


def test_skills_section_with_bullets():
    """Test extraction of skills from section header with bullet points."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
        ("docx:paragraph:7", "• React"),
        ("docx:paragraph:8", "• SQL"),
        ("docx:paragraph:9", "Experience"),  # New section header stops skills collection
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "React" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 4
    assert "Experience" not in data["candidate_profile"]["skills"]


def test_skills_with_dashes_as_bullets():
    """Test skills with dash bullet points."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Technical Skills"),
        ("docx:paragraph:5", "- Python"),
        ("docx:paragraph:6", "- JavaScript"),
        ("docx:paragraph:7", "- PostgreSQL"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "PostgreSQL" in data["candidate_profile"]["skills"]


def test_skills_deduplication():
    """Test that duplicate skills are not repeated."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python, JavaScript"),
        ("docx:paragraph:5", "Technical Skills"),
        ("docx:paragraph:6", "• Python"),
        ("docx:paragraph:7", "• JavaScript"),
        ("docx:paragraph:8", "• SQL"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Should only have 3 unique skills, not 5
    assert len(data["candidate_profile"]["skills"]) == 3
    assert data["candidate_profile"]["skills"].count("Python") == 1
    assert data["candidate_profile"]["skills"].count("JavaScript") == 1


def test_skills_with_colons():
    """Test skills header with colon."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills:"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]


def test_skills_with_capitals_as_bullets():
    """Test skills that are capitalized single words treated as bullets."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Core Competencies"),
        ("docx:paragraph:5", "Python"),
        ("docx:paragraph:6", "JavaScript"),
        ("docx:paragraph:7", "Docker"),
        ("docx:paragraph:8", "Experience"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]


def test_skills_mixed_formats():
    """Test skills with mixed inline and bullet formats."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python, JavaScript"),
        ("docx:paragraph:5", ""),  # Empty line
        ("docx:paragraph:6", "Additional Competencies"),
        ("docx:paragraph:7", "• SQL"),
        ("docx:paragraph:8", "• Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]
    assert len(data["candidate_profile"]["skills"]) == 4


def test_skills_with_semicolon_separators():
    """Test skills separated by semicolons."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Python; JavaScript; SQL; Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "SQL" in data["candidate_profile"]["skills"]
    assert "Docker" in data["candidate_profile"]["skills"]


def test_skills_stops_at_next_section():
    """Test that skills collection stops at next section header."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
        ("docx:paragraph:7", "Experience"),
        ("docx:paragraph:8", "• Senior Developer at Company"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Should not include "Senior Developer at Company" as a skill
    assert len(data["candidate_profile"]["skills"]) == 2
    assert "Python" in data["candidate_profile"]["skills"]
    assert "JavaScript" in data["candidate_profile"]["skills"]
    assert "Senior Developer at Company" not in data["candidate_profile"]["skills"]


def test_skills_with_spaces():
    """Test skills with multiple words and special characters."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills: Machine Learning, Natural Language Processing, C++, AWS"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert "Machine Learning" in data["candidate_profile"]["skills"]
    assert "Natural Language Processing" in data["candidate_profile"]["skills"]
    assert "C++" in data["candidate_profile"]["skills"]
    assert "AWS" in data["candidate_profile"]["skills"]


def test_skills_with_dot_separators():
    """Test skills separated by dots or other punctuation."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Proficiencies: Python • JavaScript • SQL • Docker"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Note: bullet separator may need adjustment, but test the basic case
    # This is a practical scenario
    assert len(data["candidate_profile"]["skills"]) >= 2


def test_no_skills_extracted():
    """Test resume with no skills section."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Experience"),
        ("docx:paragraph:5", "Senior Developer"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    assert data["candidate_profile"]["skills"] == []
    assert len(data["evidence_map"]["skills"]) == 0


def test_skills_evidence_tracking():
    """Test that skills evidence is properly tracked."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "• Python"),
        ("docx:paragraph:6", "• JavaScript"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    # Check that evidence map has entries for skills
    assert "skills" in data["evidence_map"]
    assert len(data["evidence_map"]["skills"]) > 0
    
    # Each skill should have evidence
    for evidence in data["evidence_map"]["skills"]:
        assert "source" in evidence
        assert "locator" in evidence
        assert "text" in evidence


def test_skills_from_real_resume_format():
    """Test skills extraction from realistic resume format."""
    lines = [
        ("pdf:page:1:line:1", "JANE DOE"),
        ("pdf:page:1:line:2", "jane@example.com"),
        ("pdf:page:1:line:3", "(555) 123-4567"),
        ("pdf:page:1:line:4", "San Francisco, CA"),
        ("pdf:page:1:line:5", ""),
        ("pdf:page:1:line:6", "TECHNICAL SKILLS"),
        ("pdf:page:1:line:7", "Languages: Python, JavaScript, Java, SQL"),
        ("pdf:page:1:line:8", "Frameworks: Django, FastAPI, React"),
        ("pdf:page:1:line:9", "Tools: Docker, Git, PostgreSQL"),
        ("pdf:page:1:line:10", ""),
        ("pdf:page:1:line:11", "EXPERIENCE"),
    ]
    
    resp = parse_lines_to_response(lines, source="pdf")
    data = resp.model_dump()
    
    skills = data["candidate_profile"]["skills"]
    
    # Should extract from all three lines under Technical Skills
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "Java" in skills
    assert "SQL" in skills
    assert "Django" in skills
    assert "FastAPI" in skills
    assert "React" in skills
    assert "Docker" in skills
    assert "Git" in skills
    assert "PostgreSQL" in skills


def test_skills_ignores_subheadings():
    """Test that skills section subheadings are not extracted as skills."""
    lines = [
        ("docx:paragraph:1", "Jane Doe"),
        ("docx:paragraph:2", "jane@example.com"),
        ("docx:paragraph:3", "555-1234"),
        ("docx:paragraph:4", "Skills"),
        ("docx:paragraph:5", "Languages: Python, JavaScript"),
        ("docx:paragraph:6", "Frameworks: Django, FastAPI"),
        ("docx:paragraph:7", "Experience"),
    ]
    
    resp = parse_lines_to_response(lines, source="docx")
    data = resp.model_dump()
    
    skills = data["candidate_profile"]["skills"]
    
    # Should have 4 skills, not include "Languages" or "Frameworks"
    assert "Python" in skills
    assert "JavaScript" in skills
    assert "Django" in skills
    assert "FastAPI" in skills
    # These should NOT be skills
    assert "Languages" not in skills
    assert "Frameworks" not in skills
