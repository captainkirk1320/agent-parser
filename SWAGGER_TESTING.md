# Swagger Testing Guide

## Quick Start

### 1. Start the API Server

```bash
cd /workspaces/agent-parser
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`

### 2. Access Swagger UI

Open your browser and navigate to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### GET `/` - Health Status
Returns service status.

**Response:**
```json
{
  "service": "agent-parser",
  "status": "running"
}
```

### GET `/health` - Health Check
Simple health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### POST `/parse` - Parse Resume
Extract structured candidate information from a resume file.

**Supported Formats:**
- DOCX (.docx)
- PDF (.pdf) - Text-layer extraction only
- TXT (.txt)
- Markdown (.md)

**Request:**
- File: Resume file (multipart/form-data)

**Response Example:**
```json
{
  "candidate_profile": {
    "full_name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "(555) 123-4567",
    "location": "San Francisco, CA",
    "links": ["https://linkedin.com/in/johndoe"],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "experiences": [
      {
        "company": "Tech Corp",
        "job_title": "Senior Software Engineer",
        "location": "San Francisco, CA",
        "start_date": "01/2020",
        "end_date": "Present",
        "achievements": [
          "Led team of 5 engineers",
          "Shipped 3 major features"
        ]
      }
    ],
    "education": [
      {
        "institution": "University of California",
        "degree": "Bachelor of Science",
        "field_of_study": "Computer Science",
        "location": "Berkeley, CA",
        "start_date": "2016",
        "end_date": "2020"
      }
    ]
  },
  "evidence_map": {
    "full_name": [
      {
        "source": "pdf",
        "locator": "pdf:page:1:line:1",
        "text": "John Doe",
        "confidence": 1.0
      }
    ]
  },
  "confidence_scores": {},
  "parse_quality": "high",
  "warnings": []
}
```

## Testing with cURL

### Test Health Endpoint
```bash
curl -X GET http://localhost:8000/health
```

### Test Parse Endpoint with a Text File
```bash
curl -X POST http://localhost:8000/parse \
  -F "file=@path/to/resume.txt"
```

### Test Parse Endpoint with PDF
```bash
curl -X POST http://localhost:8000/parse \
  -F "file=@path/to/resume.pdf"
```

### Test Parse Endpoint with DOCX
```bash
curl -X POST http://localhost:8000/parse \
  -F "file=@path/to/resume.docx"
```

## Testing with Python

```python
import requests

# Start with a simple health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Parse a resume
with open("path/to/resume.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post("http://localhost:8000/parse", files=files)
    result = response.json()
    
    # Extract and display results
    profile = result["candidate_profile"]
    print(f"Name: {profile['full_name']}")
    print(f"Email: {profile['email']}")
    print(f"Experiences: {len(profile['experiences'])}")
```

## Features Supported

### ✅ Core Extraction
- Full name
- Email address
- Phone number
- Location (City, State/Country)
- Links (LinkedIn, GitHub, etc.)

### ✅ Work Experience
- Company name
- Job title
- Location
- Employment dates (start/end)
- Job achievements/bullets
- Multiple formats support:
  - Single-line: "Company: Title: Location"
  - Multi-line: Company on one line, Title/Location/Dates on following lines
  - Hierarchical (H2/H3): Company with location header, Job title with dates

### ✅ Skills
- Inline skills extraction (Skills: X, Y, Z format)

### ✅ Education
- Institution name
- Degree and field of study
- Graduation date
- Location
- GPA (if available)

### ⚠️ In Progress
- Comprehensive skills section parsing (bullet-point format)
- Advanced education extraction

## Response Structure

### CandidateProfile
```json
{
  "full_name": "string | null",
  "email": "string | null",
  "phone": "string | null",
  "location": "string | null",
  "links": ["string"],
  "skills": ["string"],
  "experiences": [
    {
      "company": "string",
      "job_title": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string",
      "achievements": ["string"]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field_of_study": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string",
      "gpa": "string | null",
      "details": ["string"]
    }
  ]
}
```

### ParseResponse
```json
{
  "candidate_profile": { /* CandidateProfile */ },
  "evidence_map": {
    "field_name": [
      {
        "source": "docx | pdf | ocr | user",
        "locator": "string",
        "text": "string",
        "confidence": 0.0 - 1.0
      }
    ]
  },
  "confidence_scores": {
    "field_name": {
      "field_name": "string",
      "confidence": 0.0 - 1.0,
      "extraction_method": "string",
      "reasons": ["string"],
      "required": boolean
    }
  },
  "parse_quality": "high | medium | low",
  "warnings": ["string"]
}
```

## Example Test Resumes

You can find test resumes in the [tests/fixtures/](tests/fixtures/) directory.

## Troubleshooting

### Port Already in Use
If port 8000 is already in use:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Module Import Errors
Ensure you're in the correct directory and environment:
```bash
cd /workspaces/agent-parser
python -m venv venv  # Create if needed
source venv/bin/activate  # Activate
pip install -r requirements.txt  # Install dependencies
```

### PDF Extraction Issues
- Only text-layer PDFs are supported (no OCR)
- Ensure PDF has selectable text, not scanned images

## Performance Notes

- **Text files**: < 100ms
- **DOCX files**: 100-500ms
- **PDF files**: 500ms-2s (depends on content layout)

All times are approximate and depend on file size and system performance.
