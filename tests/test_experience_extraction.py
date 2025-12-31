"""Tests for experience extraction from resumes."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_parse_pdf_resume_extracts_experiences():
    """Test experience extraction from PDF resume (John Doe)."""
    with open("tests/fixtures/John Doe Resume 2024  final.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    files = {"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    # Check that experiences were extracted
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) > 0, "Should extract at least one experience"
    
    # First experience should be NEODENT Territory Manager
    first_exp = experiences[0]
    assert first_exp["company"] is not None, "Should extract company"
    assert "neodent" in first_exp["company"].lower(), f"First company should be Neodent, got {first_exp['company']}"
    
    # Job title may be parsed differently depending on spacing, so check for key words
    assert first_exp["job_title"] is not None, "Should extract job title"
    job_title_lower = first_exp["job_title"].lower().replace(" ", "")
    assert "territorymanager" in job_title_lower, f"Job title should contain territory/manager, got {first_exp['job_title']}"
    
    # Check evidence tracking
    assert len(data["evidence_map"]["experiences"]) > 0, "Should have experience evidence"


def test_parse_docx_resume_extracts_experiences():
    """Test experience extraction from DOCX resume (John Doe)."""
    with open("tests/fixtures/John Doe Resume 2025 (1).docx", "rb") as f:
        docx_bytes = f.read()
    
    files = {"file": ("resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    # Check that experiences were extracted
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) > 0, "Should extract at least one experience"
    
    # First experience should be Bausch & Lomb
    first_exp = experiences[0]
    assert first_exp["company"] is not None, "Should extract company"
    assert "bausch" in first_exp["company"].lower(), f"First company should be Bausch & Lomb, got {first_exp['company']}"
    
    # Check evidence tracking
    assert len(data["evidence_map"]["experiences"]) > 0, "Should have experience evidence"


def test_experience_extraction_inline_format():
    """Test experience extraction with inline Company:Title:Location format."""
    resume_text = """John Doe
john@example.com
(555) 123-4567

EXPERIENCE

ACME Corp: Senior Engineer: San Francisco, CA
January 2020 - Present
• Led team of 5 developers
• Architected microservices platform
• Improved system latency by 40%

TechStart Inc: Junior Developer: Austin, TX
June 2018 - December 2019
• Implemented REST API
• Wrote unit tests for core modules
"""
    
    files = {"file": ("resume.txt", resume_text.encode(), "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) >= 2, f"Should extract 2 experiences, got {len(experiences)}"
    
    # First experience
    first = experiences[0]
    assert "acme" in first["company"].lower(), f"Expected ACME Corp, got {first['company']}"
    assert "senior" in first["job_title"].lower(), f"Expected Senior Engineer, got {first['job_title']}"
    assert "san francisco" in first["location"].lower(), f"Expected San Francisco, got {first['location']}"
    assert len(first["achievements"]) >= 2, f"Should extract 3 achievements, got {len(first['achievements'])}"
    
    # Second experience
    second = experiences[1]
    assert "techstart" in second["company"].lower() or "tech start" in second["company"].lower(), f"Expected TechStart Inc, got {second['company']}"
    assert "junior" in second["job_title"].lower(), f"Expected Junior Developer, got {second['job_title']}"
    assert "austin" in second["location"].lower(), f"Expected Austin, got {second['location']}"


def test_experience_extraction_multiline_format():
    """Test experience extraction with multi-line format (company with location, then job title, then dates)."""
    resume_text = """Jane Smith
jane@example.com
555-987-6543

EXPERIENCE

Global Tech Solutions, San Francisco, California
Senior Product Manager
March 2021 - Present
• Managed product roadmap for mobile app
• Increased user engagement by 60%
• Led cross-functional team of 12

StartupXYZ, New York, New York
Product Analyst
July 2019 - February 2021
• Analyzed user behavior metrics
• Recommended feature prioritization
"""
    
    files = {"file": ("resume.txt", resume_text.encode(), "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) >= 2, f"Should extract at least 2 experiences, got {len(experiences)}"
    
    # First experience
    first = experiences[0]
    assert first["company"] is not None, "Should extract company"
    assert first["job_title"] is not None, "Should extract job title"
    assert len(first["achievements"]) > 0, "Should extract achievements"


def test_experience_extraction_without_dates():
    """Test that experience parsing works even when dates are missing."""
    resume_text = """Alice Johnson
alice@example.com
(555) 321-0987

EXPERIENCE

DataCorp Inc: Data Scientist: Seattle, WA
• Built ML pipelines for customer segmentation
• Reduced query latency by 50%
"""
    
    files = {"file": ("resume.txt", resume_text.encode(), "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) >= 1, f"Should extract experience even without dates, got {len(experiences)}"
    
    exp = experiences[0]
    assert exp["company"] is not None, "Should extract company"
    assert len(exp["achievements"]) > 0, "Should extract achievements"


def test_parse_quality_includes_experiences():
    """Test that parse quality scoring includes experience extraction."""
    # Resume with all key fields
    full_resume = """John Smith
john@example.com
(555) 123-4567
Austin, TX

EXPERIENCE

Tech Corp: Senior Engineer: Austin, TX
2020 - Present
• Led major project
"""
    
    files = {"file": ("resume.txt", full_resume.encode(), "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    # Should be "high" quality due to experiences + basic fields
    assert data["parse_quality"] in ["high", "medium"], f"Should be high/medium quality, got {data['parse_quality']}"
    assert len(data["candidate_profile"]["experiences"]) > 0, "Should extract experience"
