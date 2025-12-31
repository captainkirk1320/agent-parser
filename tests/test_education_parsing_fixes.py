"""
Regression tests for education parsing fixes.

These tests validate three critical bug fixes:
1. Bullets with colons are preserved as details (not dropped)
2. Study abroad location/date parsing (city, country, term – year)
3. Degree and field_of_study splitting on " in "
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_gonzaga_bullet_with_colon_preserved():
    """
    Regression test: Bullet with colon must be preserved in details.
    
    Bug: "● Applied Communications Major: Social Media/Marketing" was being dropped
    because the colon was misinterpreted as a new entry header.
    
    Fix: Handle bullets FIRST before any colon-based header detection.
    """
    
    resume_text = """
EDUCATION

GONZAGA UNIVERSITY
Spokane, Washington
2012 – 2016
Bachelor of Science in Communication Studies
● Applied Communications Major: Social Media/Marketing
● Focus in Cross Cultural Communications / Journalism Minor
● Student Journalist for Gonzaga Bulletin Newspaper
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    education = data["candidate_profile"].get("education", [])
    assert len(education) >= 1, "Should have at least 1 education entry"
    
    gonzaga = education[0]
    details = gonzaga.get("details", [])
    
    # Critical assertion: The bullet with colon must be in details
    details_text = " ".join(details)
    assert "Applied Communications Major: Social Media/Marketing" in details_text or \
           "Applied Communications Major: Social Media/ Marketing" in details_text, \
           f"Bullet with colon should be in details. Got: {details}"
    
    # Should have all 3 bullets
    assert len(details) >= 3, f"Should have at least 3 detail bullets, got {len(details)}: {details}"


def test_study_abroad_location_date_parsing():
    """
    Regression test: Study abroad "city, country, term – year" format must parse correctly.
    
    Bug: "Copenhagen, Denmark, Spring Trimester – 2015" was being parsed as:
        location: "Denmark, Spring"
        dates: null
    
    Fix: Add specific regex pattern for study abroad location/date lines.
    """
    
    resume_text = """
EDUCATION

DANISH INSTITUTE OF STUDY ABROAD: STUDENT
Copenhagen, Denmark, Spring Trimester – 2015
● Study abroad program
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    education = data["candidate_profile"].get("education", [])
    assert len(education) >= 1, "Should have at least 1 education entry"
    
    dis = education[0]
    
    # Critical assertions for location and dates
    assert dis.get("location") == "Copenhagen, Denmark", \
        f"Location should be 'Copenhagen, Denmark', got: {dis.get('location')}"
    
    assert dis.get("start_date") == "2015", \
        f"Start date should be '2015', got: {dis.get('start_date')}"
    
    assert dis.get("end_date") == "2015", \
        f"End date should be '2015', got: {dis.get('end_date')}"
    
    # Term should be in details
    details_text = " ".join(dis.get("details", []))
    assert "Spring Trimester" in details_text, \
        f"'Spring Trimester' should be in details. Got: {dis.get('details')}"
    
    # Degree should be set from colon part
    assert dis.get("degree") == "STUDENT", \
        f"Degree should be 'STUDENT', got: {dis.get('degree')}"


def test_degree_field_splitting():
    """
    Regression test: Degree and field_of_study should be split on " in ".
    
    Enhancement: "Bachelor of Science in Communication Studies" should become:
        degree: "Bachelor of Science"
        field_of_study: "Communication Studies"
    """
    
    resume_text = """
EDUCATION

GONZAGA UNIVERSITY
Spokane, Washington
2012 – 2016
Bachelor of Science in Communication Studies
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    education = data["candidate_profile"].get("education", [])
    assert len(education) >= 1, "Should have at least 1 education entry"
    
    gonzaga = education[0]
    
    # Should have degree split from field
    assert gonzaga.get("degree") == "Bachelor of Science", \
        f"Degree should be 'Bachelor of Science', got: {gonzaga.get('degree')}"
    
    assert gonzaga.get("field_of_study") == "Communication Studies", \
        f"Field should be 'Communication Studies', got: {gonzaga.get('field_of_study')}"


def test_all_gonzaga_bullets_present():
    """
    End-to-end test: Gonzaga should have ALL bullets, including the one with a colon.
    """
    
    resume_text = """
EDUCATION

GONZAGA UNIVERSITY
Spokane, Washington
2012 – 2016
Bachelor of Science in Communication Studies
● Applied Communications Major: Social Media/Marketing
● Focus in Cross Cultural Communications / Journalism Minor
● Student Journalist for Gonzaga Bulletin Newspaper
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    education = data["candidate_profile"].get("education", [])
    gonzaga = education[0]
    details = gonzaga.get("details", [])
    
    details_text = " ".join(details).lower()
    
    # All three bullets should be present
    assert "applied communications" in details_text, "First bullet should be present"
    assert "cross cultural" in details_text or "journalism" in details_text, "Second bullet should be present"
    assert "student journalist" in details_text or "gonzaga bulletin" in details_text, "Third bullet should be present"


def test_study_abroad_complete_entry():
    """
    End-to-end test: Study abroad entry should have all fields populated correctly.
    """
    
    resume_text = """
EDUCATION

DANISH INSTITUTE OF STUDY ABROAD: STUDENT
Copenhagen, Denmark, Spring Trimester – 2015
● Study abroad program
● International business focus
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    education = data["candidate_profile"].get("education", [])
    dis = education[0]
    
    # All fields should be populated
    assert "DANISH INSTITUTE" in dis.get("institution", "").upper(), \
        f"Institution should contain 'DANISH INSTITUTE', got: {dis.get('institution')}"
    
    assert dis.get("degree") is not None and dis.get("degree") != "", \
        f"Degree should not be null/empty, got: {dis.get('degree')}"
    
    assert dis.get("location") == "Copenhagen, Denmark", \
        f"Location should be 'Copenhagen, Denmark', got: {dis.get('location')}"
    
    assert dis.get("start_date") == "2015" and dis.get("end_date") == "2015", \
        f"Dates should both be '2015', got start={dis.get('start_date')}, end={dis.get('end_date')}"
    
    details = dis.get("details", [])
    assert len(details) >= 1, f"Should have at least 1 detail, got {len(details)}"
