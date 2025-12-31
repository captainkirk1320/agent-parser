"""Tests for H2/H3 hierarchical experience format extraction."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_h2h3_hierarchical_experience_format():
    """Test experience extraction from H2/H3 hierarchical format.
    
    This format is commonly used in formatted resumes:
    - H2: Company Name, Location
    - H3: Job Title [with dates on same line]
    - Description/bullets
    """
    resume_text = """
John Doe
john.doe@example.com
(555) 123-4567
San Francisco, CA

CAREER EXPERIENCE & ACHIEVEMENTS

Bausch & Lomb, Phoenix Valley, AZ
BUSINESS DEVELOPMENT MANAGER                04/2025 - PRESENT
One of four new business development managers hired to grow adoption and use of new private-practice e-commerce software.
- Finished Q2 2nd in percent attainment and 2nd in total number of accounts adopted out of six BDMs
- Completed department leadership E2 training course hosted by TalentSmartEQ

Google, Mountain View, CA
SENIOR ACCOUNT MANAGER                01/2023 - 12/2024
Responsible for managing key accounts and driving revenue growth across California territory.
- Grew territory by 40% year-over-year
- Acquired 12 major new accounts leading to $2M in additional revenue
- Ranked #1 in sales performance among 50+ account managers nationally
"""
    
    files = {"file": ("resume.txt", resume_text.encode(), "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()
    
    # Check basic extraction
    assert data["candidate_profile"]["full_name"] is not None
    assert data["candidate_profile"]["email"] == "john.doe@example.com"
    assert data["candidate_profile"]["phone"] is not None
    
    # Check that experiences were extracted
    experiences = data["candidate_profile"]["experiences"]
    assert len(experiences) == 2, f"Should extract 2 experiences, got {len(experiences)}"
    
    # Check first experience (Bausch & Lomb)
    first_exp = experiences[0]
    assert first_exp["company"] is not None, "Should extract company"
    assert "bausch" in first_exp["company"].lower(), f"Company should be Bausch & Lomb, got {first_exp['company']}"
    
    assert first_exp["job_title"] is not None, "Should extract job title"
    assert "business" in first_exp["job_title"].lower() and "manager" in first_exp["job_title"].lower(), \
        f"Job title should contain 'business' and 'manager', got {first_exp['job_title']}"
    
    assert first_exp["location"] is not None, "Should extract location"
    assert "phoenix" in first_exp["location"].lower(), f"Location should contain Phoenix, got {first_exp['location']}"
    
    assert first_exp["start_date"] is not None, "Should extract start date"
    assert "04" in first_exp["start_date"] or "2025" in first_exp["start_date"], \
        f"Start date should be 04/2025, got {first_exp['start_date']}"
    
    assert first_exp["end_date"] is not None, "Should extract end date"
    assert "present" in first_exp["end_date"].lower(), f"End date should be Present, got {first_exp['end_date']}"
    
    assert len(first_exp["achievements"]) > 0, "Should extract achievements"
    
    # Check second experience (Google)
    second_exp = experiences[1]
    assert second_exp["company"] is not None, "Should extract company"
    assert "google" in second_exp["company"].lower(), f"Company should be Google, got {second_exp['company']}"
    
    assert second_exp["job_title"] is not None, "Should extract job title"
    assert "account" in second_exp["job_title"].lower() and "manager" in second_exp["job_title"].lower(), \
        f"Job title should contain 'account' and 'manager', got {second_exp['job_title']}"
    
    assert second_exp["location"] is not None, "Should extract location"
    assert "mountain view" in second_exp["location"].lower(), f"Location should be Mountain View, got {second_exp['location']}"
    
    assert second_exp["start_date"] is not None, "Should extract start date"
    assert second_exp["end_date"] is not None, "Should extract end date"
    
    assert len(second_exp["achievements"]) > 0, "Should extract achievements"
