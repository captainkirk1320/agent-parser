# agent-parser
Resume parsing agent.
## 🚀 Quick Start for Swagger Testing

```bash
# Start the API server
./start_server.sh
# OR: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Then access Swagger UI at:
# http://localhost:8000/docs
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/parse -F "file=@resume.pdf"
```

**Documentation:**
- [SWAGGER_READY.md](SWAGGER_READY.md) - Testing checklist (✅ All systems ready)
- [SWAGGER_TESTING.md](SWAGGER_TESTING.md) - Detailed testing guide

---
Below is a **clean, GitHub-ready `README.txt`** you can paste directly into your repo.
It’s written to support **vibe coding with Claude** while keeping the system grounded, deterministic, and cost-aware.

No fluff. Clear intent. Clear guardrails.

---

# Ranked Resume

**ATS-First Resume Parsing, Scoring, and Enhancement Platform**

---

## Overview

**Ranked Resume** is a resume intelligence platform designed to simulate how modern Applicant Tracking Systems (ATS) actually evaluate candidates.

Your resume undergoes an **invisible digital interview**:

* Parsed
* Normalized
* Evaluated against hard requirements
* Scored and categorized (Great Match / Good Match / Unqualified)

The goal is not a “pretty resume.”
The goal is **ranking higher in ATS and passing recruiter filters**.

---

## Core Problem We Solve

Most candidates fail ATS before a human ever sees them.

Recruiter filtering behavior (approximate):

* 76% filter by **specific skills**
* 60% by **education**
* 55% by **job title**
* 50% by **certifications**
* 44% by **years of experience**

Templates sell *confidence*.
**Content and structure win interviews.**

---

## Product Principles

1. **ATS > Aesthetics**
2. **Deterministic first, LLMs second**
3. **No hallucinations, no lying**
4. **Evidence-backed claims only**
5. **User confirmation for risk**
6. **Charge at peak perceived value**

---

## High-Level Workflow

1. User uploads resume (DOCX/PDF)
2. Resume is parsed and normalized
3. Parse quality is scored
4. User provides job link (recommended)
5. ATS simulation runs
6. Non-negotiables are evaluated
7. Gaps are flagged
8. Resume is enhanced (ethically)
9. ATS-friendly resume is generated
10. Paywall unlocks final download

---

## Resume Parsing & Normalization Rules

### Structural Rules

* Standard section headings only
  (Experience, Skills, Education, Certifications)
* Header content may be ignored by ATS → duplicate important info in body
* Single-column reading order enforced
* Tables and multi-column layouts flagged

### Formatting Rules

* Font size: 10–12
* Sans-serif fonts only
* No underlining or italics
* Caps used sparingly
* DOCX preferred format
* 1 page ideal, 2 pages acceptable
* Older roles condensed

---

## Date & Experience Handling

* All dates normalized to **MM/YYYY** or **Month YYYY**
* Non-standard dates (e.g. “Winter 2022”) flagged
* Start/end dates required for experience credit
* Gaps must be explained (freelance, caregiving, education, etc.)
* Recency weighting applied (recent roles matter more)

---

## Resume Content Enforcement

### Force Specificity

* Numbers required
* Tools required
* Outcomes required

### Ban Vague Phrases

Examples to rewrite:

* “Helped customers”
* “Answered questions”
* “Worked in a warehouse”

### Example Transformations

Bad:

> Helped customers with car questions

Good:

> Managed inbound and outbound calls during 10-hour shifts, maintaining a 95% satisfaction score in a high-volume environment

Bad:

> Answered customer questions

Good:

> Navigated Salesforce and Google Workspace while handling high-volume inbound calls, documenting cases in real time at 40 WPM

Bad:

> Picked orders in the warehouse

Good:

> Selected 500+ items per shift using a Reach Truck across freezer and dry environments with 99.9% accuracy

---

## Keyword Strategy (ATS-Aware)

* Job title alignment is critical
  (10.6× higher interview likelihood when titles match)
* Keyword placement matters more than raw count
* Titles and summaries carry more weight than buried bullets
* Controlled repetition is beneficial
* Keyword stuffing is penalized
* Semantic grouping replaces raw keyword lists
* Language mirrors the job description but remains in the user’s voice
* Resume entropy added:

  * Mixed bullet lengths
  * Varied sentence structure
  * Real-world phrasing

---

## Location & Availability Checks

* Commute feasibility calculated
* Relocation intent flagged if missing
* Location mismatches surfaced
* Availability timing noted (minor but relevant factor)

---

## ATS Simulation Output

### Match Categories

* Great Match
* Good Match
* Unqualified

### Non-Negotiables Review

* Degree / certifications
* Years of experience
* Location / work authorization
* Licenses / clearance

Green ✓ = confirmed
Red ✗ = missing or unclear

Users can:

* Confirm missing info (if truthful)
* Accept risk and proceed
* Stop and revise strategy

---

## User Interaction Design

* Upload resume
* Provide phone + email
* Receive extraction confidence score
* Prompted to upload alternate format if score is low
* Prompted for job link (recommended)
* Progress bar throughout
* Optional “You’re more than your resume” input
* Resume preview blurred before payment
* Payment unlocks download

---

## Monetization Strategy

* Charge at:

  * Highest perceived value
  * Lowest uncertainty
  * Maximum sunk effort

### Pricing Concepts

* ATS-Friendly Resume (core)
* Upsell: Human-Friendly Resume (Canva-style) +$2
* Multiple resume versions per job encouraged
* Templates sell assurance, not results

---

## Agent Architecture (Critical)

### Core Principle

**LLMs are writers and reasoners — not readers.**

---

### Agent 0 — Orchestrator

* Routes by file type and quality
* Selects model tier
* Enforces token budgets
* Triggers user confirmations

---

### Agent 1 — Intake & Parsing (Most Important)

**Mostly non-LLM**

**Inputs**

* Resume file

**Outputs**

* `CandidateProfile.json`
* `CanonicalText.txt`
* `EvidenceMap.json`
* `ParseQualityScore`
* `Warnings[]`

**Responsibilities**

* Deterministic DOCX/PDF parsing
* OCR only when required
* Section detection
* Date normalization
* Evidence + confidence for every field

---

### Agent 2 — Job Posting Interpreter

**Light LLM + rules**

**Outputs**

* `JobSpec.json`

  * Non-negotiables
  * Required vs preferred skills
  * Title variants
  * Responsibilities
  * Industry signals

---

### Agent 3 — Matching & Scoring

**Mostly deterministic**

**Outputs**

* `MatchReport.json`

  * Pass/fail on non-negotiables
  * Skill coverage
  * Title alignment
  * Recency weighting
  * Gaps and risks
  * Evidence-backed explanations

---

### Agent 4 — Resume Enhancement

**LLM (surgical use only)**

**Inputs**

* CandidateProfile
* JobSpec
* MatchReport

**Outputs**

* Improved resume sections
* Change log
* Claims audit requiring confirmation

---

### Optional Agent 5 — Verification / Reality Check

* Prevents over-claiming
* Flags unsupported additions
* Reduces churn and trust risk

---

## Cost Control Rules (Non-Negotiable)

1. **Never re-read raw resumes**
2. **Extract once, normalize once**
3. **All downstream agents read schema**
4. **Chunk only relevant sections**
5. **Route models by task**
6. **Cache aggressively**
7. **Confirm critical fields early**

---

## Golden Rule

If you do **only one thing right**:

> Build resume intake and parsing as a deterministic service
> and treat the LLM as a **precision editor**, not a reader.

That decision alone determines whether this product is:

* scalable
* affordable
* reliable

or:

* slow
* expensive
* inconsistent

---

## Status

This repository is focused on:

* Agent 1 (Intake & Parsing)
* Deterministic correctness
* Schema-first design
* Evidence-backed outputs

LLMs are added **only after** reliability is proven.