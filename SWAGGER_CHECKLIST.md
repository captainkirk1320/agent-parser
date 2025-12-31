# Swagger Testing Checklist

## Pre-Testing Setup

- [ ] Navigate to workspace: `cd /workspaces/agent-parser`
- [ ] Start server: `./start_server.sh`
- [ ] Wait for message: "Application startup complete"
- [ ] Server running on: `http://localhost:8000`

## Access Points Verification

- [ ] Swagger UI loads: http://localhost:8000/docs
- [ ] ReDoc loads: http://localhost:8000/redoc
- [ ] OpenAPI JSON accessible: http://localhost:8000/openapi.json
- [ ] Health check responds: http://localhost:8000/health → `{"status": "ok"}`

## Basic Endpoint Testing

### Health Endpoints
- [ ] `GET /` returns: `{"service": "agent-parser", "status": "running"}`
- [ ] `GET /health` returns: `{"status": "ok"}`

### Parse Endpoint - Text File
- [ ] Upload text resume (.txt)
- [ ] Response status: 200 OK
- [ ] Response has `candidate_profile` object
- [ ] Response has `evidence_map`
- [ ] Response has `parse_quality` ("high", "medium", or "low")
- [ ] Full name extracted
- [ ] Email extracted
- [ ] Phone extracted
- [ ] At least one experience entry

### Parse Endpoint - DOCX File
- [ ] Upload DOCX resume (.docx)
- [ ] Response status: 200 OK
- [ ] All fields from text test verified
- [ ] Check for experiences array
- [ ] Verify parse_quality assessment

### Parse Endpoint - PDF File
- [ ] Upload PDF resume with text layer (.pdf)
- [ ] Response status: 200 OK
- [ ] All fields extracted
- [ ] Evidence shows source="pdf"
- [ ] Locators show page/line information

## Error Handling Tests

### Empty File
- [ ] Upload empty file
- [ ] Status: 400 Bad Request
- [ ] Message: "Empty file uploaded"

### Unsupported Format
- [ ] Upload .doc file (legacy Word format)
- [ ] Status: 415 Unsupported Media Type
- [ ] Message indicates unsupported format

### PDF Without Text
- [ ] Upload scanned PDF (image-only, no text layer)
- [ ] Status: 422 Unprocessable Entity
- [ ] Message mentions no extractable text

## Data Quality Tests

### Name Extraction
- [ ] Names with spaces parsed correctly
- [ ] Multiple-word names working
- [ ] Names don't include contact info

### Email Extraction
- [ ] Email addresses detected
- [ ] Handles various formats (firstname.lastname@, etc.)
- [ ] Spaces around @ handled
- [ ] Evidence shows original text

### Phone Extraction
- [ ] Phone with parentheses: (555) 123-4567
- [ ] Phone with dashes: 555-123-4567
- [ ] Phone with dots: 555.123.4567
- [ ] Phone properly formatted in response

### Location Extraction
- [ ] City, State format recognized
- [ ] City, Country format recognized
- [ ] Handles abbreviations (CA, NY, etc.)
- [ ] Handles full state names

### Experience Extraction
- [ ] Company name captured
- [ ] Job title captured
- [ ] Location parsed
- [ ] Start date extracted
- [ ] End date extracted
- [ ] Achievements/bullets captured
- [ ] Multiple experiences grouped correctly

### NEW: Hierarchical H2/H3 Format
- [ ] Company with location header recognized
- [ ] Job title with dates on next line extracted
- [ ] Dates properly separated (start/end)
- [ ] Achievements associated with correct job
- [ ] Multiple companies/jobs handled
- [ ] Location correctly extracted from header

### Skills Extraction
- [ ] Skills list populated
- [ ] Multiple skills separated
- [ ] Technical skills identified
- [ ] Soft skills captured

## Response Structure Validation

### CandidateProfile Object
- [ ] full_name: string or null
- [ ] email: string or null
- [ ] phone: string or null
- [ ] location: string or null
- [ ] links: array of strings
- [ ] skills: array of strings
- [ ] experiences: array of objects
- [ ] education: array of objects

### Experience Entry
- [ ] company: string
- [ ] job_title: string
- [ ] location: string
- [ ] start_date: string
- [ ] end_date: string
- [ ] achievements: array of strings

### Evidence Mapping
- [ ] Every field has entries in evidence_map
- [ ] Each evidence has:
  - [ ] source: "docx", "pdf", or "user"
  - [ ] locator: properly formatted
  - [ ] text: exact snippet from resume
  - [ ] confidence: 0.0 to 1.0

### Parse Quality
- [ ] "high": all major fields found
- [ ] "medium": most fields found
- [ ] "low": minimal fields found
- [ ] Quality reflects data completeness

## Performance Tests

- [ ] Text file parsing: < 200ms
- [ ] DOCX file parsing: < 1000ms
- [ ] PDF file parsing: < 2000ms
- [ ] Response doesn't timeout
- [ ] Multiple sequential requests work

## Schema Validation

- [ ] Swagger schema matches responses
- [ ] Required fields marked correctly
- [ ] Optional fields nullable
- [ ] Array types consistent
- [ ] No unexpected fields in response

## Documentation Review

- [ ] Endpoint descriptions clear
- [ ] Parameter descriptions present
- [ ] Response examples match reality
- [ ] Error codes documented
- [ ] Supported formats listed

## Edge Cases

- [ ] Resume with no experiences
- [ ] Resume with no skills
- [ ] Resume with special characters
- [ ] Resume with multiple locations
- [ ] Resume with date ranges (date gaps)
- [ ] Resume with employment gaps
- [ ] Very long resume (5000+ lines)
- [ ] Resume in different languages (if supported)

## Integration Tests

- [ ] Can chain multiple requests
- [ ] Server handles concurrent uploads
- [ ] File cleanup after processing
- [ ] No memory leaks on repeated uploads
- [ ] Rate limiting works (if implemented)

## Final Verification

- [ ] All required features working
- [ ] Documentation matches implementation
- [ ] Error messages clear and helpful
- [ ] Response times acceptable
- [ ] No console errors
- [ ] Ready for production use

---

## Notes Section

**Date Tested:** _______________

**Tester:** _______________

**Issues Found:**
```

```

**Additional Comments:**
```

```

---

## Sign-Off

- [ ] All checks completed
- [ ] System ready for production
- [ ] Documentation reviewed
- [ ] Performance acceptable
- [ ] Ready for deployment

**Approved by:** _______________

**Date:** _______________
