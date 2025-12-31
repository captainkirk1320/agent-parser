"""
Test suite for per-field confidence scoring.

Demonstrates how confidence scores guide downstream decision-making about
whether extraction requires user clarification.
"""

import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_confidence_scores_present_in_response():
    """Verify that all responses include confidence_scores."""
    resume_text = """JOHN DOE
john.doe@example.com
555-123-4567
San Francisco, California

Python, JavaScript, AWS
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify confidence_scores exist
    assert "confidence_scores" in data
    assert isinstance(data["confidence_scores"], dict)
    
    # Should have confidence scores for each field
    assert "full_name" in data["confidence_scores"]
    assert "email" in data["confidence_scores"]
    assert "phone" in data["confidence_scores"]
    assert "location" in data["confidence_scores"]
    assert "skills" in data["confidence_scores"]


def test_email_confidence_high_when_found():
    """Email should have high confidence when extracted via regex."""
    resume_text = """
John Doe
john.doe@example.com
555-123-4567
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    email_conf = data["confidence_scores"]["email"]
    
    assert email_conf["confidence"] == 1.0
    assert email_conf["extraction_method"] == "regex_exact_single"
    assert email_conf["required"] is True


def test_email_confidence_zero_when_not_found():
    """Email confidence should be 0 when no email is found."""
    resume_text = """
John Doe
Some Company
San Francisco, California
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    email_conf = data["confidence_scores"]["email"]
    
    assert email_conf["confidence"] == 0.0
    assert email_conf["extraction_method"] == "not_found"


def test_phone_confidence_high_when_found():
    """Phone should have high confidence when extracted via regex."""
    resume_text = """
Jane Smith
jane.smith@company.com
503-804-0032
Portland, Oregon
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    phone_conf = data["confidence_scores"]["phone"]
    
    assert phone_conf["confidence"] == 1.0
    assert phone_conf["extraction_method"] == "regex_exact_single"


def test_parse_quality_based_on_confidence():
    """Parse quality should reflect confidence in core fields."""
    # High confidence case: all core fields present
    high_confidence_resume = """
JOHN DOE
john.doe@example.com
(555) 123-4567
New York, New York
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", high_confidence_resume.encode(), "text/plain")}
    )
    
    data = response.json()
    assert data["parse_quality"] == "high"
    
    # Check that core field confidences are high
    assert data["confidence_scores"]["email"]["confidence"] >= 0.85
    assert data["confidence_scores"]["phone"]["confidence"] >= 0.85


def test_parse_quality_medium_without_phone():
    """Parse quality should be medium if core fields are missing."""
    medium_confidence_resume = """
John Smith
john.smith@example.com
San Francisco, California
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", medium_confidence_resume.encode(), "text/plain")}
    )
    
    data = response.json()
    assert data["parse_quality"] in ["medium", "low"]
    
    # Phone confidence should be 0
    assert data["confidence_scores"]["phone"]["confidence"] == 0.0


def test_confidence_scores_structure():
    """Confidence scores should have required metadata fields."""
    resume_text = """
Bob Johnson
bob@work.com
415-555-1234
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    
    for field_name, conf_obj in data["confidence_scores"].items():
        # Each confidence object should have required fields
        assert "field_name" in conf_obj
        assert "confidence" in conf_obj
        assert "extraction_method" in conf_obj
        assert "reasons" in conf_obj
        assert "required" in conf_obj
        
        # Confidence should be 0.0-1.0
        assert 0.0 <= conf_obj["confidence"] <= 1.0
        
        # Reasons should be a list
        assert isinstance(conf_obj["reasons"], list)


def test_location_confidence_with_comma():
    """Location confidence higher with city, state format."""
    resume_text = """
Sarah Williams
sarah.w@example.com
555-222-3333
Austin, Texas
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    loc_conf = data["confidence_scores"]["location"]
    
    # Should have good confidence
    assert loc_conf["confidence"] >= 0.85
    assert loc_conf["extraction_method"] == "regex_pattern"


def test_skills_confidence():
    """Skills should have appropriate confidence."""
    resume_text = """
MICHAEL CHEN
michael.chen@tech.com
415-555-9876

Skills: Python, Java, JavaScript, AWS, Docker
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    skills_conf = data["confidence_scores"]["skills"]
    
    # Skills found should have good confidence
    assert skills_conf["confidence"] >= 0.80
    assert skills_conf["extraction_method"] == "section_extraction"
    assert len(data["candidate_profile"]["skills"]) > 0


def test_confidence_in_evidence():
    """Evidence items should also track confidence."""
    resume_text = """
Patricia Lopez
patricia.lopez@startup.io
650-555-2020
"""
    
    response = client.post(
        "/parse",
        files={"file": ("resume.txt", resume_text.encode(), "text/plain")}
    )
    
    data = response.json()
    
    # Check email evidence has confidence
    email_evidence = data["evidence_map"].get("email", [])
    assert len(email_evidence) > 0
    
    for ev in email_evidence:
        assert "confidence" in ev
        assert 0.0 <= ev["confidence"] <= 1.0
