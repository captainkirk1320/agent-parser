"""
Test suite to ensure bullet lines never start new entries.
This prevents education detail bullets like "● Applied Communications Major: Social Media/Marketing"
from being misclassified as experience entries.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_education_bullets_not_parsed_as_experiences():
    """
    Regression test: Education detail bullets containing colons must NOT
    become separate experience entries.
    
    This tests the specific bug where "● Applied Communications Major: Social Media/Marketing"
    was being parsed as:
        company = "Applied communications Major"
        job_title = "Social Media"
        location = "Marketing"
    """
    
    # Resume with education section containing bullet points with colons
    resume_text = """
SARAH CHEN
sarah.chen@email.com
(555) 123-4567
Seattle, Washington

EDUCATION

GONZAGA UNIVERSITY
Spokane, Washington
2012 – 2016
Bachelor of Science in Communication Studies
● Applied Communications Major: Social Media/Marketing
● Focus in Cross Cultural Communications / Journalism Minor
● Student Journalist for Gonzaga Bulletin Newspaper

EXPERIENCE

NEODENT
Territory Manager
Portland, Oregon
January 2024 – Present
● Grew territory sales by 25%
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    candidate = data["candidate_profile"]
    experiences = candidate.get("experiences", [])
    education = candidate.get("education", [])
    
    # Critical assertions: Bullets must NOT become experience entries
    for exp in experiences:
        company = (exp.get("company") or "").lower()
        title = (exp.get("job_title") or "").lower()
        
        # These terms should NEVER appear in experience entries
        assert "major" not in company, f"Education major incorrectly parsed as experience company: {company}"
        assert "minor" not in company, f"Education minor incorrectly parsed as experience company: {company}"
        assert "communications" not in company, f"Education field incorrectly parsed as experience: {company}"
        assert "social media" not in title, f"Education detail incorrectly parsed as job title: {title}"
    
    # Education should contain the bullets as details
    assert len(education) >= 1, "Education entry should exist"
    
    # Find Gonzaga entry
    gonzaga = next((e for e in education if "gonzaga" in (e.get("institution") or "").lower()), None)
    assert gonzaga is not None, "Gonzaga education entry should exist"
    
    # Gonzaga should have details (the bullet points)
    details = gonzaga.get("details", [])
    assert len(details) >= 3, f"Gonzaga should have at least 3 detail bullets, got {len(details)}"
    
    # Check that the bullets are present in details
    details_text = " ".join(details).lower()
    assert "applied communications" in details_text, "Applied Communications bullet should be in education details"
    assert "social media" in details_text or "marketing" in details_text, "Social Media/Marketing should be in education details"


def test_no_experiences_start_with_bullets():
    """
    Guardrail test: NO experience entry should ever start from a bullet line.
    Bullets are ALWAYS attachments to existing entries.
    """
    
    resume_text = """
JOHN DOE
john@email.com

EXPERIENCE

TECH CORP
Software Engineer
● Led team of 5 developers
● Shipped 3 major features

SALES CORP
Account Manager
● Managed $2M portfolio
""".strip()
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    experiences = data["candidate_profile"].get("experiences", [])
    
    # Check that no experience entry has a company name that looks like a bullet
    for exp in experiences:
        company = exp.get("company", "")
        
        # Company names should never start with bullet characters
        assert not company.startswith("●"), f"Experience company starts with bullet: {company}"
        assert not company.startswith("•"), f"Experience company starts with bullet: {company}"
        assert not company.startswith("-"), f"Experience company starts with dash bullet: {company}"
        assert not company.startswith("*"), f"Experience company starts with asterisk bullet: {company}"
        
        # Company names should be actual companies, not achievement descriptions
        assert "led team" not in company.lower(), f"Achievement bullet parsed as company: {company}"
        assert "managed" not in company.lower(), f"Achievement bullet parsed as company: {company}"


def test_gonzaga_education_entry_complete():
    """
    End-to-end test: Gonzaga entry should be complete with all fields and details.
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
    
    # Check all fields
    assert "gonzaga" in gonzaga.get("institution", "").lower(), f"Institution should be Gonzaga, got: {gonzaga.get('institution')}"
    assert gonzaga.get("location") == "Spokane, Washington", f"Location should be 'Spokane, Washington', got: {gonzaga.get('location')}"
    assert "bachelor" in gonzaga.get("degree", "").lower(), f"Degree should contain 'bachelor', got: {gonzaga.get('degree')}"
    assert gonzaga.get("start_date") == "2012", f"Start date should be 2012, got: {gonzaga.get('start_date')}"
    assert gonzaga.get("end_date") == "2016", f"End date should be 2016, got: {gonzaga.get('end_date')}"
    
    # Check details
    details = gonzaga.get("details", [])
    assert len(details) >= 3, f"Should have at least 3 detail bullets, got {len(details)}: {details}"
    
    details_text = " ".join(details).lower()
    assert "applied communications" in details_text, "Should contain 'Applied Communications' in details"
    assert "cross cultural" in details_text, "Should contain 'Cross Cultural' in details"
    assert "student journalist" in details_text, "Should contain 'Student Journalist' in details"
