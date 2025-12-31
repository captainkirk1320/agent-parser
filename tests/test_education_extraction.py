"""
Tests for education entry extraction and classification.

Tests the deterministic, rule-based section classification and education-specific parsing.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.education_parser import (
    detect_section_type,
    has_degree_keyword,
    is_high_school,
    is_institution_keyword,
    is_study_abroad,
    classify_entry_as_education,
)

client = TestClient(app)


# ===== SECTION DETECTION TESTS =====

def test_education_section_header_detection():
    """Test detection of education section headers."""
    assert detect_section_type("EDUCATION") == "education"
    assert detect_section_type("  Education  ") == "education"
    assert detect_section_type("Academic Background") == "education"
    assert detect_section_type("Education & Training") == "education"


def test_experience_section_header_detection():
    """Test detection of experience section headers."""
    assert detect_section_type("EXPERIENCE") == "experience"
    assert detect_section_type("Professional Experience") == "experience"
    assert detect_section_type("Work Experience") == "experience"
    assert detect_section_type("Employment") == "experience"


def test_non_section_header():
    """Test that non-headers return None."""
    assert detect_section_type("John Doe") is None
    assert detect_section_type("Some company name") is None
    assert detect_section_type("") is None


# ===== DEGREE KEYWORD TESTS =====

def test_degree_keywords_detected():
    """Test detection of degree keywords."""
    assert has_degree_keyword("Bachelor of Science in Computer Science")
    assert has_degree_keyword("Master of Arts")
    assert has_degree_keyword("B.S. in Engineering")
    assert has_degree_keyword("M.A. in Philosophy")
    assert has_degree_keyword("PhD in Physics")
    assert has_degree_keyword("Doctorate in Medicine")


def test_degree_keywords_case_insensitive():
    """Test that degree detection is case-insensitive."""
    assert has_degree_keyword("bachelor of science")
    assert has_degree_keyword("MASTER OF ARTS")
    assert has_degree_keyword("Ph.D.")


def test_non_degree_text():
    """Test that non-degree text doesn't match."""
    assert not has_degree_keyword("Senior Software Engineer")
    assert not has_degree_keyword("Project Manager at Acme Corp")


# ===== HIGH SCHOOL TESTS =====

def test_high_school_detection():
    """Test detection of high school."""
    assert is_high_school("High School")
    assert is_high_school("Lincoln High School")
    assert is_high_school("Secondary School")
    assert is_high_school("Prep School")


def test_high_school_case_insensitive():
    """Test that high school detection is case-insensitive."""
    assert is_high_school("HIGH SCHOOL")
    assert is_high_school("high school")


def test_non_high_school():
    """Test that non-high school doesn't match."""
    assert not is_high_school("University of California")


# ===== INSTITUTION KEYWORD TESTS =====

def test_institution_keywords_detected():
    """Test detection of institution keywords."""
    assert is_institution_keyword("University of California")
    assert is_institution_keyword("Stanford University")
    assert is_institution_keyword("College of Engineering")
    assert is_institution_keyword("Institute of Technology")
    assert is_institution_keyword("State University")


def test_institution_case_insensitive():
    """Test that institution detection is case-insensitive."""
    assert is_institution_keyword("UNIVERSITY")
    assert is_institution_keyword("university")


def test_non_institution():
    """Test that non-institution names don't match."""
    assert not is_institution_keyword("Acme Corporation")


# ===== STUDY ABROAD TESTS =====

def test_study_abroad_detection():
    """Test detection of study abroad programs."""
    assert is_study_abroad("Study Abroad Program")
    assert is_study_abroad("DIS Study Abroad")
    assert is_study_abroad("Institute of Study Abroad")


def test_study_abroad_case_insensitive():
    """Test that study abroad detection is case-insensitive."""
    assert is_study_abroad("STUDY ABROAD")
    assert is_study_abroad("study abroad")


# ===== CLASSIFICATION TESTS =====

def test_classify_degree_as_education():
    """Test that entries with degree keywords are classified as education."""
    entry_lines = [
        "Gonzaga University: Bachelor of Science in Communication Studies",
        "Spokane, Washington, 2012 – 2016",
    ]
    assert classify_entry_as_education(entry_lines)


def test_classify_high_school_as_education():
    """Test that high school is always education."""
    entry_lines = ["Lincoln High School", "Lincoln, Nebraska, 2008 – 2012"]
    assert classify_entry_as_education(entry_lines)


def test_classify_study_abroad_as_education():
    """Test that study abroad is classified as education."""
    entry_lines = [
        "DIS Study Abroad, Copenhagen",
        "Spring Trimester 2015",
    ]
    assert classify_entry_as_education(entry_lines)


def test_classify_with_education_section_context():
    """Test that institution keywords in education section classify as education."""
    entry_lines = ["University of Washington", "Seattle, Washington, 2010 – 2014"]
    assert classify_entry_as_education(entry_lines, current_section="education")


# ===== API ENDPOINT TESTS =====

def test_parse_resume_with_education_section():
    """Test parsing a resume with EDUCATION section using test fixture."""
    
    # Create a simple resume with education section
    resume_text = """
    John Doe
    john.doe@example.com
    (555) 123-4567
    
    EDUCATION
    
    Gonzaga University: Bachelor of Science in Communication Studies
    Spokane, Washington, 2012 – 2016
    • Applied Communications Major: Social Media / Marketing
    • Focus in Cross Cultural Communications / Journalism Minor
    
    University of Washington: B.A. in Business Administration
    Seattle, Washington, 2008 – 2012
    • Graduated with Honors
    
    EXPERIENCE
    
    Tech Company: Senior Software Engineer
    San Francisco, California, 2020 – Present
    • Led team of 5 engineers
    • Shipped 3 major features
    
    Startup Inc: Software Engineer
    San Francisco, California, 2018 – 2020
    • Developed backend API
    """
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check education extraction
    educations = data["candidate_profile"].get("education", [])
    assert len(educations) == 2, f"Expected 2 education entries, got {len(educations)}"
    
    # Check Gonzaga entry
    gonzaga = next((e for e in educations if "Gonzaga" in str(e.get("institution", ""))), None)
    assert gonzaga is not None
    assert "Gonzaga" in gonzaga.get("institution", "")
    assert "Bachelor of Science" in gonzaga.get("degree", "")
    assert "Communication Studies" in gonzaga.get("field_of_study", "")
    assert len(gonzaga.get("details", [])) >= 2, "Gonzaga should have details/majors"
    
    # Check University of Washington entry
    uw = next((e for e in educations if "Washington" in str(e.get("institution", ""))), None)
    assert uw is not None
    assert "B.A." in uw.get("degree", "") or "Bachelor of Arts" in uw.get("degree", "")


def test_parse_resume_with_high_school():
    """Test that high school is correctly classified as education, not experience."""
    
    resume_text = """
    Jane Smith
    jane.smith@example.com
    555-456-7890
    
    EDUCATION
    
    Lincoln High School
    Lincoln, Nebraska, 2008 – 2012
    • Valedictorian
    • National Honor Society
    
    EXPERIENCE
    
    ABC Corp: Marketing Manager
    Denver, Colorado, 2015 – Present
    • Managed campaigns
    """
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    educations = data["candidate_profile"].get("education", [])
    assert len(educations) > 0, "Should have at least one education entry"
    
    # High school should be in education, not experience
    hs_entry = next((e for e in educations if "Lincoln" in str(e.get("institution", ""))), None)
    assert hs_entry is not None, "High School should be in education section"
    
    experiences = data["candidate_profile"].get("experiences", [])
    # Make sure high school is NOT in experiences
    for exp in experiences:
        assert "High School" not in str(exp.get("company", ""))


def test_parse_resume_with_study_abroad():
    """Test study abroad program classification."""
    
    resume_text = """
    Bob Johnson
    bob@example.com
    555-999-8888
    
    EDUCATION
    
    DIS Study Abroad, Copenhagen
    Spring Trimester 2015
    • Danish Culture and Society
    • European Business Practices
    
    Boston University: Bachelor of Science in Engineering
    Boston, Massachusetts, 2013 – 2017
    
    EXPERIENCE
    """
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    educations = data["candidate_profile"].get("education", [])
    
    # Study abroad should be in education
    study_abroad = next((e for e in educations if "Study Abroad" in str(e.get("institution", ""))), None)
    assert study_abroad is not None, "Study Abroad should be in education section"


def test_education_entry_not_split_into_multiple_jobs():
    """Test that Gonzaga education block is NOT split into multiple fake jobs."""
    
    # This is the critical Gonzaga test case
    resume_text = """
    John Doe
    john.doe@example.com
    (555) 123-4567
    
    EDUCATION
    
    GONZAGA UNIVERSITY: Bachelor of Science in Communication Studies
    Spokane, Washington, 2012 – 2016
    ● Applied Communications Major: Social Media / Marketing
    ● Focus in Cross Cultural Communications / Journalism Minor
    ● Student Journalist for Gonzaga Bulletin Newspaper
    
    EXPERIENCE
    
    Tech Corp: Senior Engineer
    San Francisco, CA, 2017 – Present
    """
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    educations = data["candidate_profile"].get("education", [])
    
    # CRITICAL: Should be exactly 1 education entry for Gonzaga, not 2 or 3
    assert len(educations) == 1, f"Expected 1 Gonzaga education entry, got {len(educations)}"
    
    gonzaga = educations[0]
    assert "Gonzaga" in gonzaga.get("institution", "") or "GONZAGA" in gonzaga.get("institution", "")
    assert "Bachelor of Science" in gonzaga.get("degree", "")
    assert len(gonzaga.get("details", [])) >= 2, "Should capture major and focus area"


def test_education_details_separated_from_experiences():
    """Test that education details (majors, minors) are NOT treated as work achievements."""
    
    resume_text = """
    Jane Doe
    jane@example.com
    555-123-4567
    
    EDUCATION
    
    University of California: Bachelor of Science in Computer Science
    Berkeley, California, 2016 – 2020
    ● Major: Computer Science
    ● Minor: Mathematics
    ● Cum Laude
    
    EXPERIENCE
    
    Google: Software Engineer
    Mountain View, California, 2020 – Present
    ● Developed features
    ● Improved performance
    """
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    educations = data["candidate_profile"].get("education", [])
    experiences = data["candidate_profile"].get("experiences", [])
    
    assert len(educations) == 1
    assert len(experiences) == 1
    
    # Major/Minor/Honors should be in education.details, not in experience achievements
    edu = educations[0]
    assert any("Major" in d or "major" in d for d in edu.get("details", [])), "Should have major in details"
    assert any("Minor" in d or "minor" in d for d in edu.get("details", [])), "Should have minor in details"
    
    exp = experiences[0]
    # Experience achievements should NOT contain education-specific keywords
    achievements = " ".join(exp.get("achievements", []))
    assert "Major:" not in achievements, "Experience should not contain education major"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
