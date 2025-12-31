from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_parse_txt_extracts_email_and_evidence():
    resume = b"""Jane Doe
jane.doe@example.com
(555) 123-4567
Skills: Python, FastAPI, SQL
https://github.com/janedoe
"""
    files = {"file": ("resume.txt", resume, "text/plain")}
    r = client.post("/parse", files=files)
    assert r.status_code == 200
    data = r.json()

    assert data["candidate_profile"]["full_name"] == "Jane Doe"
    assert data["candidate_profile"]["email"] == "jane.doe@example.com"
    assert "Python" in data["candidate_profile"]["skills"]

    # Evidence must exist and point to a line
    assert len(data["evidence_map"]["email"]) >= 1
    assert data["evidence_map"]["email"][0]["locator"].startswith("text:line:")
