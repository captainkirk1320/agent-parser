"""Tests for H2/H3 hierarchical experience format parsing."""

from fastapi.testclient import TestClient
from app.main import app
from app.core.line_parser import parse_lines_to_response

client = TestClient(app)


def test_h2_h3_hierarchical_experience_format():
    """Test parsing of H2/H3 hierarchical experience format.
    
    Format:
      H2: Company, Location
      H3: Job Title
      Line: Dates
      Lines: Description, achievements
    """
    # Simulate the resume format from the user's image
    lines = [
        ("docx:0", "CAREER EXPERIENCE & ACHIEVEMENTS"),
        ("docx:1", "Bausch & Lomb, Phoenix Valley, AZ"),
        ("docx:2", "BUSINESS DEVELOPMENT MANAGER"),
        ("docx:3", "04/2025 - PRESENT"),
        ("docx:4", "One of four new business development managers hired to grow adoption and use of new private-practice e-commerce software."),
        ("docx:5", "• Finished Q2 2nd in percent attainment and 2nd in total number of accounts adopted out of six BDMs"),
        ("docx:6", "• Completed department leadership EQ training course hosted by TalentSmartEQ"),
    ]
    
    response = parse_lines_to_response(lines, source="docx")
    
    # Should extract one experience
    assert len(response.candidate_profile.experiences) == 1, "Should extract one experience entry"
    
    exp = response.candidate_profile.experiences[0]
    
    # Verify all fields are extracted correctly
    assert exp["company"] == "Bausch & Lomb", f"Expected company 'Bausch & Lomb', got {exp['company']}"
    assert exp["job_title"] == "Business Development Manager", f"Expected job title 'Business Development Manager', got {exp['job_title']}"
    assert exp["location"] == "Phoenix Valley, AZ", f"Expected location 'Phoenix Valley, AZ', got {exp['location']}"
    assert exp["start_date"] == "04/2025", f"Expected start_date '04/2025', got {exp['start_date']}"
    assert exp["end_date"] == "PRESENT", f"Expected end_date 'PRESENT', got {exp['end_date']}"
    
    # Should have achievements
    assert len(exp["achievements"]) > 0, "Should extract achievements"
    assert "Finished Q2 2nd in percent attainment" in exp["achievements"][0], "Should preserve achievement text"


def test_h2_h3_format_with_multiple_entries():
    """Test H2/H3 format with multiple experience entries."""
    lines = [
        ("docx:0", "CAREER EXPERIENCE"),
        ("docx:1", "Company A, New York, NY"),
        ("docx:2", "SENIOR MANAGER"),
        ("docx:3", "01/2023 - 12/2024"),
        ("docx:4", "Led a team of 10 people"),
        ("docx:5", "• Increased revenue by 50%"),
        ("docx:6", "Company B, San Francisco, CA"),
        ("docx:7", "JUNIOR DEVELOPER"),
        ("docx:8", "06/2020 - 12/2022"),
        ("docx:9", "Developed backend services"),
        ("docx:10", "• Built REST APIs"),
    ]
    
    response = parse_lines_to_response(lines, source="docx")
    
    # Should extract two experiences
    assert len(response.candidate_profile.experiences) == 2, f"Expected 2 experiences, got {len(response.candidate_profile.experiences)}"
    
    # First entry
    exp1 = response.candidate_profile.experiences[0]
    assert exp1["company"] == "Company A", f"Expected 'Company A', got {exp1['company']}"
    assert exp1["job_title"] == "Senior Manager", f"Expected 'Senior Manager', got {exp1['job_title']}"
    assert exp1["location"] == "New York, NY", f"Expected 'New York, NY', got {exp1['location']}"
    
    # Second entry
    exp2 = response.candidate_profile.experiences[1]
    assert exp2["company"] == "Company B", f"Expected 'Company B', got {exp2['company']}"
    assert exp2["job_title"] == "Junior Developer", f"Expected 'Junior Developer', got {exp2['job_title']}"
    assert exp2["location"] == "San Francisco, CA", f"Expected 'San Francisco, CA', got {exp2['location']}"


def test_h2_h3_format_with_inline_dates():
    """Test H2/H3 format where dates are inline with the location."""
    lines = [
        ("docx:0", "EXPERIENCE"),
        ("docx:1", "Tech Corp, Austin, TX"),
        ("docx:2", "PRODUCT ENGINEER"),
        ("docx:3", "January 2020 - Present"),
        ("docx:4", "• Architected new features"),
    ]
    
    response = parse_lines_to_response(lines, source="docx")
    
    # Should extract one experience
    assert len(response.candidate_profile.experiences) == 1, "Should extract one experience"
    
    exp = response.candidate_profile.experiences[0]
    assert exp["company"] == "Tech Corp", f"Got company: {exp['company']}"
    assert exp["job_title"] == "Product Engineer", f"Got title: {exp['job_title']}"
    assert exp["location"] == "Austin, TX", f"Got location: {exp['location']}"
    assert exp["start_date"] == "January 2020", f"Got start_date: {exp['start_date']}"
    assert exp["end_date"] == "Present", f"Got end_date: {exp['end_date']}"


def test_h2_h3_format_multiple_jobs_same_company():
    """Test H2/H3 format with multiple job titles under the same company.
    
    This tests the scenario where one company header (H2) is followed by multiple
    job title headers (H3), such as:
      H2: Bausch & Lomb, Phoenix Valley, AZ
      H3: Business Development Manager (04/2025 - Present)
      H3: Executive Vision Territory Manager (02/2019 - 04/2025)
    
    Both jobs should correctly inherit the company name and location from H2.
    """
    lines = [
        ("docx:0", "CAREER EXPERIENCE & ACHIEVEMENTS"),
        ("docx:1", "Bausch & Lomb, Phoenix Valley, AZ"),
        ("docx:2", "Bausch & Lomb is a historical leader in the eye care industry."),
        ("docx:3", "BUSINESS DEVELOPMENT MANAGER"),
        ("docx:4", "04/2025 - PRESENT"),
        ("docx:5", "One of four new business development managers hired."),
        ("docx:6", "• Finished Q2 2nd in percent attainment"),
        ("docx:7", "EXECUTIVE VISION TERRITORY MANAGER"),
        ("docx:8", "02/2019 - 04/2025"),
        ("docx:9", "Responsible for growing three contact lens product families."),
        ("docx:10", "• Selected to join the company's Emerging Leaders Program"),
        ("docx:11", "Funderbolt, Scottsdale, AZ"),
        ("docx:12", "DIRECTOR OF SALES"),
        ("docx:13", "07/2016 - 06/2018"),
        ("docx:14", "Led sales team."),
    ]
    
    response = parse_lines_to_response(lines, source="docx")
    
    # Should extract 3 experiences (2 at Bausch & Lomb, 1 at Funderbolt)
    assert len(response.candidate_profile.experiences) == 3, f"Expected 3 experiences, got {len(response.candidate_profile.experiences)}"
    
    # First entry: Bausch & Lomb - Business Development Manager
    exp1 = response.candidate_profile.experiences[0]
    assert exp1["company"] == "Bausch & Lomb", f"Expected 'Bausch & Lomb' for first job, got {exp1['company']}"
    assert exp1["job_title"] == "Business Development Manager", f"Expected 'Business Development Manager', got {exp1['job_title']}"
    assert exp1["location"] == "Phoenix Valley, AZ", f"Expected 'Phoenix Valley, AZ', got {exp1['location']}"
    assert exp1["start_date"] == "04/2025", f"Expected '04/2025', got {exp1['start_date']}"
    assert exp1["end_date"] == "PRESENT", f"Expected 'PRESENT', got {exp1['end_date']}"
    assert exp1["company_description"] and "eye care industry" in exp1["company_description"], "Should have company description"
    
    # Second entry: Bausch & Lomb - Executive Vision Territory Manager
    # CRITICAL: This should also have "Bausch & Lomb" as company (inherited from H2 header)
    exp2 = response.candidate_profile.experiences[1]
    assert exp2["company"] == "Bausch & Lomb", f"Expected 'Bausch & Lomb' for second job, got {exp2['company']}"
    assert exp2["job_title"] == "Executive Vision Territory Manager", f"Expected 'Executive Vision Territory Manager', got {exp2['job_title']}"
    assert exp2["location"] == "Phoenix Valley, AZ", f"Expected 'Phoenix Valley, AZ' (inherited from H2), got {exp2['location']}"
    assert exp2["start_date"] == "02/2019", f"Expected '02/2019', got {exp2['start_date']}"
    assert exp2["end_date"] == "04/2025", f"Expected '04/2025', got {exp2['end_date']}"
    
    # Third entry: Funderbolt - Director of Sales (new company)
    exp3 = response.candidate_profile.experiences[2]
    assert exp3["company"] == "Funderbolt", f"Expected 'Funderbolt', got {exp3['company']}"
    assert exp3["job_title"] == "Director Of Sales", f"Expected 'Director Of Sales', got {exp3['job_title']}"
    assert exp3["location"] == "Scottsdale, AZ", f"Expected 'Scottsdale, AZ', got {exp3['location']}"
    assert exp3["start_date"] == "07/2016", f"Expected '07/2016', got {exp3['start_date']}"
    assert exp3["end_date"] == "06/2018", f"Expected '06/2018', got {exp3['end_date']}"

