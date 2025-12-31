from app.core.line_parser import parse_lines_to_response

def test_name_anchored_above_email_beats_headers():
    # Simulates extracted PDF lines similar to your resume
    lines = [
        ("pdf:page:1:line:1", "JOHN DOE"),
        ("pdf:page:1:line:2", "New York, New York"),
        ("pdf:page:1:line:3", "john.doe@example.com"),
        ("pdf:page:1:line:4", "(555) 123-4567"),
        ("pdf:page:1:line:5", "EXPERIENCE"),
    ]

    resp = parse_lines_to_response(lines, source="pdf")
    data = resp.model_dump()

    assert data["candidate_profile"]["full_name"] == "John Doe"
    assert data["candidate_profile"]["email"] == "john.doe@example.com"
    assert data["candidate_profile"]["phone"] == "(555) 123-4567"
    assert data["candidate_profile"]["location"] == "New York, New York"

    # Evidence should point to the correct line (name line, not EXPERIENCE)
    assert data["evidence_map"]["full_name"][0]["locator"] == "pdf:page:1:line:1"
