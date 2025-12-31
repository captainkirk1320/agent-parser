# Swagger Testing Preparation Checklist

## ✅ Pre-Swagger Testing Status

### API Setup
- ✅ FastAPI application properly configured
- ✅ OpenAPI schema generation enabled
- ✅ Swagger UI available at `/docs`
- ✅ ReDoc documentation at `/redoc`
- ✅ OpenAPI JSON schema at `/openapi.json`
- ✅ 7 API endpoints configured

### Core Implementation
- ✅ `/parse` POST endpoint with full file upload support
- ✅ Support for DOCX, PDF, and TXT formats
- ✅ CandidateProfile schema with complete field documentation
- ✅ ParseResponse wrapper with evidence tracking
- ✅ Error handling for unsupported formats and empty files

### Resume Parsing Features
- ✅ Full name extraction with evidence tracking
- ✅ Email and phone number extraction
- ✅ Location parsing (City, State/Country)
- ✅ URL/link extraction (LinkedIn, GitHub, etc.)
- ✅ Work experience extraction with multiple format support:
  - ✅ Single-line format: `Company: Title: Location`
  - ✅ Multi-line format with separate title/date lines
  - ✅ **NEW** Hierarchical H2/H3 format: Company header → Job title with dates
- ✅ Job achievement/bullet point extraction
- ✅ Skills extraction
- ✅ Education information extraction

### Testing
- ✅ All 7 core experience extraction tests passing
- ✅ All 1 H2/H3 hierarchical format tests passing
- ✅ Health check endpoint verified
- ✅ API schema validation complete

### Documentation
- ✅ Endpoint documentation with examples
- ✅ Response schema documentation
- ✅ Field descriptions and constraints
- ✅ Error codes and messages documented
- ✅ Comprehensive testing guide created (SWAGGER_TESTING.md)

### Recent Enhancements
- ✅ Fixed H2/H3 hierarchical resume format support
- ✅ Enhanced date extraction with PDF/DOCX whitespace handling
- ✅ Added section header blacklist to prevent false positives
- ✅ Improved endpoint documentation with examples and descriptions

## 🚀 How to Start Testing

### Option 1: Using Shell Script
```bash
cd /workspaces/agent-parser
./start_server.sh
```

### Option 2: Direct Command
```bash
cd /workspaces/agent-parser
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Using Python
```bash
cd /workspaces/agent-parser
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📋 Swagger Testing URL

Once the server is running, access:
- **Swagger UI (Interactive)**: http://localhost:8000/docs
- **ReDoc (Read-only)**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🧪 Quick Smoke Test

```bash
# Health check (no file needed)
curl -X GET http://localhost:8000/health

# Parse a text resume
curl -X POST http://localhost:8000/parse \
  -F "file=@tests/fixtures/sample_resume.txt"
```

## 📊 Example Response Structure

The API will return:
```json
{
  "candidate_profile": {
    "full_name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
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
    "education": [...]
  },
  "evidence_map": {
    "field_name": [
      {
        "source": "docx|pdf|ocr|user",
        "locator": "string",
        "text": "string",
        "confidence": 1.0
      }
    ]
  },
  "confidence_scores": {},
  "parse_quality": "high|medium|low",
  "warnings": ["string"]
}
```

## ✨ Key Features to Test

1. **File Format Support**
   - Upload .txt files
   - Upload .docx files
   - Upload .pdf files
   - Verify error handling for unsupported formats

2. **Data Extraction**
   - Verify full name extraction
   - Check email/phone parsing
   - Validate location extraction
   - Confirm experience parsing with multiple formats
   - Validate skill extraction

3. **Evidence Tracking**
   - Verify all extracted fields have evidence_map entries
   - Check source attribution (docx/pdf/user)
   - Validate locator formatting

4. **Error Handling**
   - Test empty file upload (400 error)
   - Test unsupported file type (415 error)
   - Test PDF without text layer (422 error)

5. **Hierarchical H2/H3 Format** (NEW)
   - Test company header with location
   - Test job title header with dates
   - Verify date extraction from title line
   - Verify achievement capture

## 📝 Additional Notes

- All files are UTF-8 compatible
- File upload limit: Configurable (currently no limit in code)
- PDF support: Text-layer only (no OCR)
- Response times: Typically < 2 seconds per resume
- Concurrent requests: FastAPI handles automatically

## 🔧 Troubleshooting

If the server won't start:
1. Check Python is installed: `python --version`
2. Verify FastAPI is installed: `pip install fastapi uvicorn`
3. Check port 8000 is available: `lsof -i :8000`
4. Try alternate port: `uvicorn app.main:app --port 8001`

## 📚 Related Documentation

- [SWAGGER_TESTING.md](SWAGGER_TESTING.md) - Detailed testing guide
- [docs/agent-parser-contract.md](docs/agent-parser-contract.md) - API contract
- [docs/EXTRACTION_AUDIT.md](docs/EXTRACTION_AUDIT.md) - Feature status
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Development guide
