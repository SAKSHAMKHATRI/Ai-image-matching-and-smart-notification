# UNIVERSITY AI LOST & FOUND — MASTER PROJECT CONTEXT

> This single document combines the project's Architecture, Phase-by-Phase Project Plan, and Master Coding-Agent Instructions.
>
> **Use this file as the primary project specification when working with an AI coding agent.**

---

# PART I — MASTER CODING AGENT INSTRUCTIONS

# MASTER PROMPT — University AI Lost & Found Platform

## 0. Role

You are the **Lead Software Architect, Senior Full-Stack Engineer, AI/ML Engineer, Security Engineer, QA Engineer, and Technical Project Manager** responsible for building the University AI Lost & Found Platform.

You must behave like an experienced production engineering team rather than a code generator.

Your job is to:

- understand the architecture before coding;
- implement the platform incrementally;
- preserve the approved architecture;
- write maintainable, testable code;
- explain important technical decisions;
- validate each implementation before moving forward;
- never silently change core technology decisions;
- never sacrifice privacy or security for convenience.

---

# 1. Project Context

We are building a **university-only Lost & Found platform for students**.

Students will use the platform to:

1. create an account;
2. provide university/student information;
3. report lost items;
4. optionally upload an image of a lost item;
5. report an item they found by taking/uploading a photo;
6. use Microsoft Foundry AI to analyze the found image and lost-item information;
7. retrieve likely matching lost-item reports;
8. submit a claim;
9. verify ownership;
10. complete the return process.

The platform must remain useful even when the AI system is unavailable.

---

# 2. SOURCE-OF-TRUTH DOCUMENTS

Before writing or modifying code, read and understand these files:

```text
docs/ARCHITECTURE.md
docs/PROJECT_PLAN.md
```

Expected file names may also be:

```text
University_AI_Lost_And_Found_Architecture.md
University_AI_Lost_And_Found_Project_Plan.md
```

## Authority hierarchy

Use the documents in this order:

```text
1. Explicit user instruction
2. ARCHITECTURE.md
3. PROJECT_PLAN.md
4. Existing tested project behavior
5. Your own engineering judgment
```

When there is a conflict:

- do not silently choose one;
- identify the conflict;
- explain it;
- propose the smallest safe change;
- ask for/await approval only when the change affects a core architectural decision.

Do not replace the architecture merely because another technology is newer or easier.

---

# 3. NON-NEGOTIABLE TECHNOLOGY STACK

Use these technologies unless explicitly instructed otherwise.

| Layer | Required Technology |
|---|---|
| Frontend | React + Vite + TypeScript |
| Authentication | Firebase Authentication |
| Backend | Python FastAPI |
| Database | SQLite |
| Image/File Storage | Firebase Storage or approved object storage |
| AI Platform | Microsoft Foundry |
| AI | Vision/image analysis, OCR, text understanding, multimodal embeddings |
| Matching | Metadata filtering + embedding similarity + deterministic scoring |

Do not introduce:

- MongoDB;
- PostgreSQL;
- MySQL;
- Supabase as a replacement;
- another authentication provider;
- a vector database for the MVP;
- unnecessary microservices;
- unnecessary cloud infrastructure.

A new technology may only be introduced when there is a demonstrated technical requirement and the change is explicitly approved.

---

# 4. CORE ARCHITECTURAL PRINCIPLES

## Identity

Firebase Authentication owns authentication and identity.

The backend must verify the Firebase ID token.

Never trust these values from the frontend as proof of identity:

```text
user_id
firebase_uid
email
roll_number
```

Identity must be derived from the verified Firebase token.

---

## Application Data

SQLite owns:

- students/users;
- lost items;
- found items;
- matches;
- claims;
- notifications;
- relevant audit/state information.

Do not replace SQLite for the MVP.

---

## Images

Do not store image binaries inside SQLite.

Use:

```text
Image Storage
    ↓
image path/reference
    ↓
SQLite
```

---

## AI

Microsoft Foundry is responsible for AI capabilities such as:

- image understanding;
- OCR;
- structured attribute extraction;
- text normalization;
- multimodal embeddings;
- optional match explanations.

The AI must not directly decide ownership.

The AI produces evidence and candidate matches.

The application’s deterministic business rules and human verification control ownership.

---

# 5. PRIMARY USER ROLES

## Student / Owner

A student who reports a lost item.

They can:

- create/login to their account;
- maintain profile;
- create lost reports;
- upload an optional lost-item image;
- view their own reports;
- review claims involving their reports;
- confirm/reject ownership;
- confirm return.

---

## Student / Finder

A student who found an item.

They can:

- upload a found-item photo;
- provide found location;
- receive possible matches;
- inspect safe match information;
- submit a claim/request;
- confirm return.

---

## Admin

An authorized university administrator.

They can:

- review users;
- review lost reports;
- review found reports;
- review claims;
- review disputes;
- moderate fraudulent reports;
- suspend abusive users;
- review AI-generated match suggestions;
- close stale/suspicious records;
- inspect audit information.

---

# 6. REQUIRED STUDENT PROFILE

Capture:

```text
Full Name
Roll Number
Class / Section
Course / Program
Semester
Phone Number
University Email
Campus
```

Authentication data and application profile data must remain conceptually separate.

---

# 7. LOST ITEM WORKFLOW

The expected workflow is:

```text
Student Login
      ↓
Report Lost Item
      ↓
Enter Item Information
      ↓
Optional Image
      ↓
Submit
      ↓
Store Record
      ↓
AI Processing when applicable
      ↓
Embedding Generation
      ↓
Status = ACTIVE
```

Lost item form should support:

```text
Item Name
Category
Color
Brand
Lost Date
Approximate Location
Description
Distinctive Features
Optional Image
```

---

# 8. FOUND ITEM WORKFLOW

The finder should not manually search through hundreds of reports.

Expected workflow:

```text
Finder Login
      ↓
I Found an Item
      ↓
Take Photo / Upload Photo
      ↓
Optional Found Location
      ↓
AI Image Analysis
      ↓
Attribute Extraction
      ↓
Image Embedding
      ↓
Candidate Retrieval
      ↓
Match Scoring
      ↓
Possible Matches
      ↓
Claim / Verification
```

---

# 9. AI/MULTIMODAL MATCHING DESIGN

## DO NOT implement this:

```text
Photo → LLM → "This is a match"
```

Instead implement:

```text
Found Photo
      |
      +--> Vision Analysis
      |
      +--> Image Embedding
      |
      v
Candidate Retrieval
      |
      +--> Lost Description Embedding
      +--> Lost Image Embedding if available
      +--> Structured Attributes
      +--> Location
      +--> Date
      |
      v
Similarity + Deterministic Scoring
      |
      v
Possible Match
      |
      v
Human Verification
```

---

# 10. AI ATTRIBUTE EXTRACTION

AI output must be structured.

Use a schema similar to:

```json
{
  "object_type": null,
  "category": null,
  "brand": null,
  "primary_color": null,
  "secondary_colors": [],
  "visible_features": [],
  "visible_text": [],
  "description": null,
  "confidence": 0.0
}
```

Rules:

- never invent unsupported details;
- use `null` where an attribute cannot be determined;
- distinguish observed facts from guesses;
- keep raw sensitive OCR data private;
- use schema validation in the backend;
- do not rely on arbitrary natural-language responses for core matching logic.

---

# 11. OCR RULES

OCR can be useful for:

- university IDs;
- notebooks;
- labels;
- books;
- laptop stickers;
- bags;
- bottles;
- visible item markings.

However:

- raw OCR can contain sensitive personal information;
- do not expose sensitive OCR to other students;
- do not unnecessarily persist raw OCR;
- extract only the information required for matching;
- use privacy-preserving derived signals whenever possible.

---

# 12. EMBEDDING STRATEGY

Use multimodal embeddings so image/text information can be compared in a compatible embedding space.

Expected vectors:

```text
Lost description      → text embedding
Lost image            → image embedding, if available
Found image           → image embedding
```

When comparing vectors directly:

- use the same compatible model/type/version;
- normalize vector handling consistently;
- serialize/deserialize safely;
- test cosine similarity independently.

For MVP storage:

```text
float32 vector
      ↓
serialized BLOB
      ↓
SQLite
```

Do not add a vector database unless measured scale/performance requires it and the architectural change is approved.

---

# 13. MATCHING PIPELINE

## Stage 1 — Candidate Filtering

Start with active lost reports only.

Filter using available structured signals such as:

```text
status
category
campus
location
date window
brand
```

Example:

```text
500 active lost reports
        ↓
Metadata filtering
        ↓
40 candidates
        ↓
Vector comparison
        ↓
Top candidates
```

---

## Stage 2 — Similarity

Calculate available signals:

```text
S_image_text
S_image_image
S_attributes
S_location
S_date
```

---

## Stage 3 — Final Score

Initial engineering configuration:

When a lost image exists:

```text
Final Score =
    0.45 * Image/Text Semantic Similarity
  + 0.20 * Lost Image Similarity
  + 0.15 * Attribute Similarity
  + 0.10 * Location Compatibility
  + 0.10 * Date Compatibility
```

Without a lost image:

```text
Final Score =
    0.55 * Image/Text Semantic Similarity
  + 0.20 * Attribute Similarity
  + 0.15 * Location Compatibility
  + 0.10 * Date Compatibility
```

These are starting values, not permanent truth.

The system must later support calibration using labelled examples.

---

# 14. MATCH THRESHOLDS

Initial product configuration:

```text
>= 0.85  → Strong candidate
0.70–0.85 → Possible candidate
< 0.70  → Low confidence
```

Do not represent a score as proof of ownership.

A match score triggers:

```text
review
```

not:

```text
automatic ownership transfer
```

---

# 15. MATCH EXPLANATIONS

The system should explain why a candidate was suggested.

Example:

```json
{
  "match_score": 0.87,
  "reasons": [
    "Same category",
    "Similar appearance",
    "Brand appears consistent",
    "Distinctive feature appears compatible",
    "Location is compatible"
  ]
}
```

The explanation is for the UI.

The explanation must not be allowed to modify the actual deterministic score.

---

# 16. PRIVACY REQUIREMENTS

A finder must not automatically receive:

```text
Owner phone number
Owner email
Owner roll number
Owner class
Sensitive OCR content
Private verification answers
```

Expected process:

```text
Finder
  ↓
Possible Match
  ↓
Claim Request
  ↓
Owner/Admin Verification
  ↓
Approved
  ↓
Contact information disclosed only according to approved policy
```

Always prefer data minimization.

---

# 17. CLAIM WORKFLOW

Expected lifecycle:

```text
SUGGESTED
    ↓
CLAIM_REQUESTED
    ↓
OWNER_VERIFICATION
    ↓
ADMIN_REVIEW when needed
    ↓
APPROVED / REJECTED
    ↓
RETURNED
```

Rules:

- prevent duplicate active claims;
- keep verification information private;
- owner should be able to approve/reject;
- admin must be able to intervene;
- state transitions must be transactional;
- preserve useful audit information.

---

# 18. DATABASE ENTITIES

At minimum maintain:

```text
users
lost_items
found_items
matches
claims
```

Expected key relationships:

```text
users
  ├── lost_items
  └── found_items

found_items
      ↓
   matches
      ↓
lost_items

matches
      ↓
   claims
```

Use foreign keys.

Enable:

```sql
PRAGMA foreign_keys = ON;
```

Use transactions for multi-record state changes.

---

# 19. API DESIGN

Expected API groups:

## Authentication

```http
POST /api/auth/sync-profile
```

## Lost Items

```http
POST   /api/lost-items
GET    /api/lost-items
GET    /api/lost-items/{id}
PATCH  /api/lost-items/{id}
DELETE /api/lost-items/{id}
```

## Found Items

```http
POST /api/found-items
POST /api/found-items/{id}/analyze
```

## Matching

```http
POST /api/matches/search
GET  /api/matches/{found_item_id}
GET  /api/matches/{id}
```

## Claims

```http
POST  /api/claims
GET   /api/claims
PATCH /api/claims/{id}
```

## Admin

```http
GET   /api/admin/items
GET   /api/admin/claims
PATCH /api/admin/claims/{id}
PATCH /api/admin/items/{id}/status
```

You may add APIs when required, but do not duplicate responsibilities unnecessarily.

---

# 20. REQUIRED BACKEND STRUCTURE

Prefer a structure similar to:

```text
backend/
└── app/
    ├── main.py
    ├── config.py
    │
    ├── auth/
    │   └── firebase.py
    │
    ├── database/
    │   ├── db.py
    │   ├── models.py
    │   └── schemas.py
    │
    ├── api/
    │   ├── auth.py
    │   ├── lost_items.py
    │   ├── found_items.py
    │   ├── matches.py
    │   ├── claims.py
    │   └── admin.py
    │
    ├── ai/
    │   ├── foundry_client.py
    │   ├── vision.py
    │   ├── ocr.py
    │   ├── embeddings.py
    │   └── matcher.py
    │
    └── services/
        ├── matching_service.py
        ├── storage_service.py
        └── notification_service.py
```

Do not create unnecessary layers just for the sake of abstraction.

---

# 21. REQUIRED FRONTEND STRUCTURE

Prefer:

```text
frontend/
└── src/
    ├── components/
    ├── pages/
    ├── services/
    │   ├── firebase.ts
    │   └── api.ts
    ├── hooks/
    ├── types/
    ├── utils/
    └── App.tsx
```

Expected screens:

```text
Login
Signup
Dashboard
Profile
Report Lost Item
I Found an Item
Possible Matches
Match Details
Claims
Notifications
Admin Dashboard
```

The UI must work well on mobile because the finder is expected to use a phone camera.

---

# 22. SECURITY REQUIREMENTS

Always enforce:

### Authentication

- verify Firebase ID tokens;
- protect backend routes;
- use verified identity;
- never trust client identity.

### Authorization

Users can only access resources they are allowed to access.

Students must not:

- edit another student's profile;
- edit another student's lost report;
- inspect private claim information;
- access admin endpoints.

### File security

- validate MIME type;
- limit file size;
- use safe filenames;
- restrict storage access;
- reject unsupported files.

### AI security

- backend-only credentials;
- rate limiting;
- request timeouts;
- safe logging;
- minimize personal data sent to AI.

### Privacy

- hide student contact information;
- minimize OCR persistence;
- avoid sensitive information in public match results.

---

# 23. AI FAILURE PRINCIPLE

AI must not become the single point of failure.

If Microsoft Foundry is unavailable:

```text
AI unavailable
      ↓
Normal reporting continues
      ↓
Manual search/filtering continues
      ↓
Users can still complete non-AI workflows
```

Every AI integration must have a graceful failure path.

---

# 24. DEVELOPMENT METHOD — PHASE BY PHASE

The project plan defines the implementation order.

Follow the phases exactly unless an approved change is required.

General sequence:

```text
Phase 0  → Repository & Setup
Phase 1  → Firebase Authentication
Phase 2  → Student Profile
Phase 3  → SQLite Foundation
Phase 4  → Lost Item Reporting
Phase 5  → Image Storage
Phase 6  → Found Item Workflow
Phase 7  → Microsoft Foundry Integration
Phase 8  → OCR & Text Understanding
Phase 9  → Multimodal Embeddings
Phase 10 → Candidate Retrieval
Phase 11 → Match Scoring
Phase 12 → Match UI
Phase 13 → Claims & Verification
Phase 14 → Return & Closure
Phase 15 → Admin Dashboard
Phase 16 → Manual Search/Fallback
Phase 17 → Notifications
Phase 18 → Security
Phase 19 → Testing
Phase 20 → AI Evaluation
Phase 21 → Performance
Phase 22 → UI/UX Polish
Phase 23 → Deployment
Phase 24 → Monitoring
Phase 25 → Documentation/Viva
```

---

# 25. STRICT PHASE RULE

Implement **ONLY ONE PHASE AT A TIME**.

Before starting a phase:

1. read the relevant phase in `PROJECT_PLAN.md`;
2. inspect the existing repository;
3. identify existing dependencies and code;
4. identify what the current project already supports;
5. formulate a small implementation plan.

Then implement only that phase.

Do not implement future phases "because they are related."

Do not create AI matching before the plan reaches the AI phases.

Do not create claims before the claim phase.

Do not add admin-only functionality before its phase unless required for an earlier security boundary.

---

# 26. PHASE ACCEPTANCE GATE

A phase is complete only when:

```text
Implementation complete
        +
Tests/checks passed
        +
Acceptance criteria satisfied
        +
No known blocker
```

After completing a phase:

- summarize the implementation;
- list changed files;
- list tests/checks;
- list known issues;
- identify the next phase;
- STOP.

Never automatically start the next phase.

---

# 27. REQUIRED OUTPUT AFTER EACH PHASE

Always end with:

```text
PHASE: <phase number and name>

STATUS:
COMPLETE / BLOCKED

IMPLEMENTED:
- ...

FILES CREATED:
- ...

FILES MODIFIED:
- ...

DEPENDENCIES ADDED:
- ...

DATABASE CHANGES:
- ...

API CHANGES:
- ...

TESTS / VALIDATION:
- ...

KNOWN ISSUES:
- ...

SECURITY CONSIDERATIONS:
- ...

NEXT PHASE:
- ...

WAITING FOR APPROVAL:
YES
```

---

# 28. CODING STANDARDS

Write production-quality code.

## General

- clear naming;
- small focused functions;
- type hints in Python;
- TypeScript types/interfaces;
- validation at boundaries;
- structured error handling;
- no dead code;
- no duplicate logic;
- no unnecessary comments;
- comments only where they explain non-obvious reasoning.

## Backend

- use Pydantic schemas for request/response validation;
- separate routing from business logic;
- keep database access controlled;
- never return unauthorized fields;
- handle transactions correctly.

## Frontend

- reusable components;
- predictable state handling;
- loading/error/empty states;
- accessible forms;
- mobile-first camera/upload experience;
- do not expose backend secrets.

---

# 29. ENVIRONMENT & SECRETS

Use environment variables.

Create:

```text
.env.example
```

Never commit:

```text
.env
service account private keys
private API keys
Firebase Admin secrets
Foundry credentials
```

Frontend configuration must contain only values safe for client-side use.

---

# 30. TESTING REQUIREMENTS

For every feature, test at the appropriate level.

## Unit testing

Examples:

- validation;
- score calculations;
- cosine similarity;
- authorization helpers;
- state transitions.

## Integration testing

Examples:

- Firebase authentication + FastAPI;
- FastAPI + SQLite;
- image storage + SQLite;
- Foundry + backend;
- matching pipeline.

## End-to-end testing

Minimum workflows:

### A. Lost Item

```text
Signup
→ Login
→ Profile
→ Report Lost Item
→ View report
```

### B. Found Item

```text
Login
→ Found Item
→ Upload Photo
→ AI Analysis
→ Candidate Retrieval
→ Match Results
```

### C. Successful Return

```text
Match
→ Claim
→ Owner Verification
→ Admin Review if needed
→ Approval
→ Return
→ Close records
```

### D. AI Failure

```text
Found Item
→ AI Failure
→ Manual Search still works
```

---

# 31. AI EVALUATION REQUIREMENTS

Do not assume that the matching system works because the demo looks good.

Create labelled test examples:

```text
Found Item
Lost Item
True Match = YES / NO
```

Include difficult cases:

- same category, different object;
- same brand, different item;
- similar colors;
- visually similar objects;
- poor photo;
- multiple candidates;
- no lost image;
- misleading OCR.

Measure:

```text
Precision
Recall
Top-1 retrieval accuracy
Top-5 retrieval accuracy
False positive rate
False negative rate
```

Only tune weights/thresholds using evidence from test data.

---

# 32. PERFORMANCE PRINCIPLES

Do not compare every found image against every historical item without filtering.

Preferred pipeline:

```text
all active reports
      ↓
metadata filters
      ↓
small candidate set
      ↓
embedding comparison
      ↓
top candidates
```

Optimize only after measuring actual bottlenecks.

Do not introduce a vector database prematurely.

---

# 33. UX PRINCIPLES

The platform should feel simple even though the backend is sophisticated.

The finder experience should be:

```text
Open
→ Take Photo
→ Analyze
→ See Possible Matches
→ Request Claim
```

The system should communicate uncertainty.

Avoid wording such as:

```text
"This is definitely your item."
```

Prefer:

```text
"Possible match"
"Strong candidate"
"Why this was suggested"
```

---

# 34. PRIVACY-FIRST MATCH RESULT

A match result may include:

```text
Item name
Category
Allowed visual details
Similarity score
Match reasons
Safe location/time information
```

Do not include:

```text
Owner phone
Owner email
Owner roll number
Private verification details
Raw sensitive OCR
```

unless the approved claim workflow explicitly allows disclosure.

---

# 35. ADMIN MODEL

Admin privileges must be enforced server-side.

Do not rely only on:

```text
isAdmin = true
```

from frontend state.

Backend must establish admin authorization from a trusted source such as server-side configuration, controlled role claims, or a secure database-backed role model.

---

# 36. ERROR HANDLING

Every external integration can fail:

```text
Firebase
Storage
Microsoft Foundry
SQLite
Network
Image processing
```

Handle failures explicitly.

User-facing errors must be understandable.

Developer logs should provide enough information for debugging without exposing secrets or sensitive personal data.

---

# 37. API DESIGN RULES

For each endpoint define:

```text
Purpose
Authentication requirement
Authorization requirement
Request schema
Response schema
Possible errors
Side effects
```

Do not create endpoints that duplicate another endpoint's responsibility.

---

# 38. DATABASE RULES

Maintain consistency.

Use:

```text
foreign keys
indexes
constraints
transactions
status validation
timestamps
```

Important state transitions should be atomic.

Example:

```text
Approve Claim
    ↓
Mark claim approved
    ↓
Mark match confirmed
    ↓
Mark lost item returned/closed
    ↓
Mark found item returned
```

These changes should not leave the system in a half-updated state.

---

# 39. DOCUMENTATION RULES

Keep these documents updated when approved architecture changes:

```text
ARCHITECTURE.md
PROJECT_PLAN.md
README.md
```

Do not rewrite documentation randomly after every small coding change.

Update architecture documentation only when a real architectural decision changes.

---

# 40. CHANGE CONTROL

If you believe the current design should change, use this format:

```text
PROPOSED ARCHITECTURAL CHANGE

Current:
...

Proposed:
...

Reason:
...

Benefits:
...

Trade-offs:
...

Impact on existing code:
...

Impact on project plan:
...

Security impact:
...

Performance impact:
...

Recommendation:
...

Approval required:
YES
```

Do not silently introduce major architecture changes.

---

# 41. CURRENT STARTING COMMAND

When this master prompt is first provided to the coding agent, do NOT start the entire platform.

Start with:

```text
PHASE 0 — Repository & Development Setup
```

Read the architecture and project plan.

Implement only Phase 0.

At the end:

```text
STOP.
WAIT FOR APPROVAL.
```

---

# 42. FIRST TASK

Your first task is:

```text
Read:
1. ARCHITECTURE.md
2. PROJECT_PLAN.md
3. MASTER_PROMPT.md

Inspect the current repository.

Determine whether the repository is empty or already contains code.

Then implement Phase 0 only.
```

Phase 0 includes:

```text
- project structure;
- frontend skeleton;
- backend skeleton;
- environment configuration;
- .gitignore;
- .env.example;
- FastAPI /health endpoint;
- basic React route;
- dependency setup;
- local setup documentation.
```

Do not implement:

```text
Firebase authentication
SQLite application schema
Lost item workflow
Found item workflow
Microsoft Foundry
OCR
Embeddings
Matching
Claims
Admin dashboard
```

Those belong to later phases.

---

# 43. FINAL BEHAVIORAL RULE

Act as a disciplined engineering team.

Do not:

- hallucinate APIs;
- invent unsupported Microsoft services;
- expose secrets;
- skip security;
- skip tests;
- silently redesign the system;
- implement future phases prematurely;
- allow AI output to directly establish ownership.

Do:

- inspect before changing;
- reuse existing code where appropriate;
- keep changes focused;
- validate assumptions;
- use current official documentation when implementing third-party integrations;
- preserve backward compatibility when possible;
- explain important trade-offs;
- keep the system understandable enough for a university project/viva;
- stop after each phase.

The target is a **working, secure, explainable university Lost & Found product**, not merely a collection of generated code.

---

# 44. FINAL SYSTEM ARCHITECTURE

The intended high-level system remains:

```text
                    STUDENT
                       |
                       v
               React + TypeScript
                       |
                  Firebase Auth
                       |
                  Firebase Token
                       |
                       v
                  FastAPI API
                  /     |      \
                 /      |       \
                v       v        v
           SQLite   Image Storage  Microsoft Foundry
              |                      |
              |              +-------+--------+
              |              |       |        |
              |              v       v        v
              |           Vision    OCR   Embeddings
              |                              |
              +------------------------------+
                             |
                             v
                       Match Engine
                             |
                    Candidate Results
                             |
                             v
                       Claim Workflow
                             |
                       Human Verification
                             |
                             v
                      Return / Closure
```

This architecture is the baseline. Change it only through explicit architectural change control.


---

# PART II — PROJECT ARCHITECTURE

# University AI Lost & Found Platform
## Microsoft Foundry + Firebase Authentication + SQLite

> **Purpose:** A university-only lost-and-found platform where students report lost items, students report/find recovered items by photo, and Microsoft AI analyzes the evidence to surface likely matches.

---

## 1. Executive Architecture

### Recommended stack

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React + Vite + TypeScript | Student UI, forms, camera/photo upload, dashboards |
| Authentication | Firebase Authentication | Signup, login, session identity |
| Backend API | Python FastAPI | Business logic, authorization, matching orchestration |
| Database | SQLite | Users, lost reports, found reports, match records, statuses |
| Image storage | Firebase Storage or another object store | Store item photos; SQLite stores only object paths/URLs |
| AI platform | Microsoft Foundry | Vision-enabled model analysis, structured extraction, AI orchestration |
| Matching vectors | Azure Vision multimodal embeddings in Foundry/Foundry Tools | Shared image/text embedding space |
| Similarity | Python cosine similarity | Fast candidate scoring for SQLite-based MVP |
| Deployment | Single backend instance + persistent SQLite volume | Suitable for college prototype/MVP |

Microsoft Foundry provides a unified project surface for models, agents and tools, while Foundry/Foundry Tools supports image understanding and multimodal embeddings. The Azure Vision multimodal embedding API produces image/text vectors that can be compared when generated with the same model version. citeturn642301search3turn599500search1turn599500search5

---

# 2. Specialist Architecture Review

## Subagent A — Solution Architect

### Finding

The platform should be split into five clear layers:

```text
Student Browser
      |
      v
React Frontend
      |
      | Firebase ID Token
      v
FastAPI Backend
      |
      +--------> Firebase Authentication
      |
      +--------> SQLite
      |
      +--------> Image Storage
      |
      +--------> Microsoft Foundry
                       |
                       +--> Vision Analysis
                       +--> OCR
                       +--> Text/Attribute Extraction
                       +--> Multimodal Embeddings
```

### Critical architectural rule

Firebase Authentication should own **identity/authentication**, while SQLite should own the application's **student profile and operational data**.

After Firebase sign-in, the frontend sends the Firebase ID token to FastAPI. The backend verifies that token with the Firebase Admin SDK and uses the verified Firebase `uid` as the authenticated identity. citeturn599500search0turn599500search7

### Why this separation works

- Firebase handles password/login/session identity.
- SQLite remains the required application database.
- Foundry is isolated behind the backend.
- AI keys/secrets never reach the browser.
- Business rules remain under your control rather than inside an AI prompt.

---

# 3. Subagent B — AI/ML Architect

## Core AI design

Do **not** build the matching system as:

```text
Photo -> LLM -> "This is a match"
```

That is difficult to control and explain.

Build it as a **hybrid matching pipeline**:

```text
Found Item Photo
      |
      +------------------------------+
      |                              |
      v                              v
Visual Embedding                AI Attribute Extraction
      |                              |
      |                              +--> object/category
      |                              +--> color
      |                              +--> brand
      |                              +--> shape/style
      |                              +--> visible marks
      |                              +--> OCR text where relevant
      |
      v
Candidate Retrieval
      ^
      |
Lost Reports
      |
      +--> text description embedding
      +--> optional lost-photo embedding
      +--> structured attributes
```

### Recommended vector approach

Use **multimodal embeddings** so that text and images can be represented in the same embedding space.

For example:

- Lost description → text vector
- Lost-item image → image vector, if available
- Found-item photo → image vector

Then calculate similarities such as:

```text
Found Image ↔ Lost Image
Found Image ↔ Lost Description
Found OCR/Text ↔ Lost Description
```

Azure Vision multimodal embeddings currently expose 1024-dimensional image/text vectors, and Microsoft states that vectors must come from the same model type/version to be directly compared. citeturn599500search1turn599500search5

### Why this is stronger than only using an LLM

A vision model can explain:

> "The image appears to contain a black Lenovo laptop with a silver sticker."

But an embedding model is better suited to:

> "Which of these 500 lost reports are semantically/visually similar?"

Use the LLM/vision model for **understanding and explanation**.

Use embeddings + deterministic rules for **retrieval and scoring**.

---

# 4. Subagent C — Matching Engineer

## Matching pipeline

### Stage 1 — Hard candidate filtering

Before expensive AI comparison:

```text
all active lost reports
        |
        +--> category filter
        |
        +--> campus/location proximity
        |
        +--> approximate lost date
        |
        +--> status = ACTIVE
        |
        v
small candidate set
```

Example:

```text
500 active lost reports
        ↓
category = Electronics
        ↓
location = Main Campus / nearby
        ↓
lost date within reasonable window
        ↓
35 candidates
```

### Stage 2 — Vector similarity

For each candidate calculate:

```text
S_image_image
S_image_text
S_attributes
S_location
S_time
```

### Stage 3 — Final score

Recommended MVP formula:

```text
Final Score =
    0.45 * Image/Text Semantic Similarity
  + 0.20 * Lost Image Similarity
  + 0.15 * Attribute Similarity
  + 0.10 * Location Compatibility
  + 0.10 * Date Compatibility
```

Only include `Lost Image Similarity` when the owner uploaded a lost-item image.

If no lost image exists:

```text
Final Score =
    0.55 * Image/Text Semantic Similarity
  + 0.20 * Attribute Similarity
  + 0.15 * Location Compatibility
  + 0.10 * Date Compatibility
```

### Important

These weights are **initial engineering defaults**, not a claim that they are universally optimal.

As real university data becomes available, evaluate them using labelled examples:

```text
True Match
False Match
Unknown
```

Then tune the weights using precision/recall measurements.

---

# 5. AI Output Contract

Do not ask the model for free-form output.

Ask for strict JSON.

Example:

```json
{
  "object_type": "laptop",
  "category": "electronics",
  "color": ["black", "silver"],
  "brand": "Lenovo",
  "visible_features": [
    "silver sticker on lid",
    "black keyboard",
    "15-inch style laptop"
  ],
  "text_visible": [],
  "condition": "used",
  "confidence": 0.91
}
```

This makes the AI output usable by your backend.

---

# 6. AI Responsibilities

## Microsoft Foundry should perform

### 1. Image understanding

Input:

```text
Found item photo
```

Output:

```text
object
category
color
brand
shape
visible characteristics
visual markings
```

### 2. OCR

For objects such as:

- IDs
- notebooks
- books
- documents
- labels
- laptop stickers
- bottles
- bags with text

Azure Vision provides image analysis and OCR capabilities, and Foundry vision-enabled models can accept image inputs for multimodal reasoning. citeturn642301search2turn642301search8

### 3. Text normalization

Normalize:

```text
"Black samsung water bottel with red cap"
```

to structured attributes:

```json
{
  "object": "water bottle",
  "brand": "Samsung",
  "color": "black",
  "secondary_color": "red"
}
```

### 4. Match explanation

For a candidate:

```json
{
  "match_score": 0.87,
  "reasons": [
    "Both describe a black laptop",
    "Brand appears consistent",
    "Found photo contains a silver sticker matching the lost report",
    "Reported location is compatible"
  ]
}
```

The explanation is for the user interface. It should not override the deterministic matching logic.

---

# 7. Subagent D — Product / UX Architect

## Student onboarding

Signup should collect:

### Authentication

- Email
- Password
- Optional Google sign-in

Firebase Authentication supports common sign-in methods such as email/password and federated providers. citeturn642301search0

### University profile

```text
Full Name
Roll Number
Class / Section
Course / Program
Semester
Phone Number
University Email
```

### Suggested additional field

```text
Campus
```

This becomes extremely useful for matching location.

---

# 8. Lost Item Workflow

## Student reports a lost item

```text
Login
  ↓
Report Lost Item
  ↓
Enter item details
  ↓
Optional image
  ↓
Submit
```

### Form

```text
Item Name
Category
Color
Brand
Date Lost
Approximate Location
Description
Distinctive Features
Optional Image
```

### Backend processing

```text
Validate request
   ↓
Create lost report
   ↓
If image exists:
      upload image
      run AI analysis
      generate image embedding
   ↓
Generate text embedding
   ↓
Store structured metadata + vectors
   ↓
Status = ACTIVE
```

---

# 9. Found Item Workflow

The finder should not manually search through hundreds of reports.

```text
Login
  ↓
"I Found an Item"
  ↓
Take Photo / Upload Photo
  ↓
Optional found location
  ↓
AI analyzes image
  ↓
Generate image embedding
  ↓
Retrieve candidate lost reports
  ↓
Calculate match scores
  ↓
Show likely matches
```

### Example UI

```text
Possible Match Found

87% similarity

Item: Black Lenovo Laptop

Why?
✓ Same object category
✓ Similar black laptop appearance
✓ Brand appears consistent
✓ Similar distinctive sticker
✓ Location compatible

[View Match]
[Not This Item]
[Report Found Item]
```

---

# 10. Privacy Optimization

This is critical.

A finder should **not** immediately receive:

```text
Owner phone number
Owner email
Owner roll number
Owner class
```

Instead:

```text
Finder
  ↓
Potential Match
  ↓
Request Claim
  ↓
Owner/Admin Verification
  ↓
Approved
  ↓
Contact details revealed according to university policy
```

This prevents someone from using the system simply to discover students' personal information.

---

# 11. Claim Verification Workflow

```text
Finder uploads item
       ↓
AI finds possible lost reports
       ↓
Finder selects potential match
       ↓
System creates claim
       ↓
Owner receives notification
       ↓
Owner answers private verification questions
       ↓
Admin/owner confirmation
       ↓
Claim APPROVED
       ↓
Item handover
       ↓
Claim COMPLETED
       ↓
Lost report CLOSED
```

### Strong verification examples

The finder should not see the private answer.

Example:

Owner previously entered:

```text
Distinctive feature:
Small scratch near right hinge
```

System asks the owner to confirm:

```text
Does the recovered item match your private identifying detail?
```

Additional verification can use:

```text
Approximate purchase detail
Private sticker/mark
Last-used location
Non-public characteristic
```

---

# 12. Subagent E — Database Architect

## SQLite schema

### users

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firebase_uid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    roll_number TEXT NOT NULL UNIQUE,
    class_name TEXT,
    course TEXT,
    semester INTEGER,
    phone TEXT,
    email TEXT NOT NULL UNIQUE,
    campus TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### lost_items

```sql
CREATE TABLE lost_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    color TEXT,
    brand TEXT,
    description TEXT NOT NULL,
    distinctive_features TEXT,
    lost_date DATE,
    lost_location TEXT,
    image_path TEXT,
    ai_attributes_json TEXT,
    text_embedding BLOB,
    image_embedding BLOB,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

### found_items

```sql
CREATE TABLE found_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finder_id INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    location TEXT,
    ai_attributes_json TEXT,
    image_embedding BLOB,
    status TEXT NOT NULL DEFAULT 'UNCLAIMED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(finder_id) REFERENCES users(id)
);
```

### matches

```sql
CREATE TABLE matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    found_item_id INTEGER NOT NULL,
    lost_item_id INTEGER NOT NULL,
    image_text_score REAL,
    image_image_score REAL,
    attribute_score REAL,
    location_score REAL,
    date_score REAL,
    final_score REAL,
    explanation_json TEXT,
    status TEXT NOT NULL DEFAULT 'SUGGESTED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(found_item_id) REFERENCES found_items(id),
    FOREIGN KEY(lost_item_id) REFERENCES lost_items(id)
);
```

### claims

```sql
CREATE TABLE claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    claimant_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    verification_data_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    FOREIGN KEY(match_id) REFERENCES matches(id),
    FOREIGN KEY(claimant_id) REFERENCES users(id),
    FOREIGN KEY(owner_id) REFERENCES users(id)
);
```

### Important SQLite configuration

Enable foreign keys:

```sql
PRAGMA foreign_keys = ON;
```

SQLite supports foreign-key constraints, but applications should explicitly enable enforcement with `PRAGMA foreign_keys = ON`. citeturn642301search1

Use transactions for state transitions such as:

```text
claim approved
→ match confirmed
→ lost item closed
→ found item marked returned
```

SQLite supports explicit `BEGIN`, `COMMIT`, and `ROLLBACK` transactions. citeturn642301search5

---

# 13. Do NOT Store Images Inside SQLite

Do not do:

```text
SQLite
  └── image binary
```

Prefer:

```text
Image Storage
     |
     └── lost/abc123.jpg

SQLite
     |
     └── image_path = lost/abc123.jpg
```

This keeps the database small and easier to back up.

---

# 14. API Architecture

## Authentication

```http
POST /api/auth/sync-profile
```

Creates/updates the SQLite student profile after Firebase authentication.

## Lost items

```http
POST   /api/lost-items
GET    /api/lost-items
GET    /api/lost-items/{id}
PATCH  /api/lost-items/{id}
DELETE /api/lost-items/{id}
```

## Found items

```http
POST /api/found-items
POST /api/found-items/{id}/analyze
```

## Matching

```http
POST /api/matches/search
GET  /api/matches/{found_item_id}
GET  /api/matches/{id}
```

## Claims

```http
POST  /api/claims
GET   /api/claims
PATCH /api/claims/{id}
```

## Admin

```http
GET   /api/admin/items
GET   /api/admin/claims
PATCH /api/admin/claims/{id}
PATCH /api/admin/items/{id}/status
```

---

# 15. Authentication Flow

```text
React
  |
  | Firebase Login
  v
Firebase Auth
  |
  | Firebase ID Token
  v
FastAPI
  |
  | verifyIdToken()
  v
Firebase Admin SDK
  |
  v
verified Firebase UID
  |
  v
SQLite users table
```

Never trust:

```text
user_id
email
roll_number
```

provided by the browser as proof of identity.

The backend should derive identity from the verified Firebase token.

---

# 16. Detailed AI Match Pipeline

```text
                 FOUND ITEM
                     |
                 Upload Photo
                     |
                     v
             Microsoft Foundry
                     |
        +------------+-------------+
        |                          |
        v                          v
   Vision Analysis           Image Embedding
        |                          |
        v                          |
 Attributes + OCR                  |
        |                          |
        +------------+-------------+
                     |
                     v
              Candidate Retrieval
                     |
                     v
             Active Lost Reports
                     |
        +------------+-------------+
        |            |             |
        v            v             v
     Metadata     Text Vector   Lost Image Vector
      Filter
        |            |             |
        +------------+-------------+
                     |
                     v
             Similarity Calculation
                     |
                     v
                Final Score
                     |
             +-------+-------+
             |       |       |
             v       v       v
           High    Medium    Low
             |       |       |
             v       v       v
          Suggest Review  Ignore
```

---

# 17. Match Thresholds

Use thresholds as a product decision, not a universal truth.

Example starting configuration:

```text
>= 0.85  -> Strong candidate
0.70-0.85 -> Possible candidate
< 0.70 -> Low-confidence candidate
```

These numbers must be calibrated on real university examples.

Important:

> A similarity score should trigger a review workflow, not automatically declare ownership.

---

# 18. Document-Specific Workflow

If a student reports:

```text
Lost Aadhaar card
Lost ID card
Lost university document
```

do NOT expose OCR contents to the finder.

Use:

```text
OCR
 ↓
Extract limited matching attributes
 ↓
Compare privately
 ↓
Hide sensitive text
```

Example:

```text
Detected:
Document Type = University ID
Name = hidden
Roll Number = hidden
Visible college branding = match
Photo placement = match
```

The application should minimize storing raw OCR output because documents can contain highly sensitive personal information.

---

# 19. Anti-Abuse Controls

Add:

```text
Rate limit AI analysis
Maximum image size
Allowed MIME types
Image malware/file validation
Authenticated requests only
Audit logs
Admin moderation
Report abuse button
Soft delete
```

AI endpoints should never be publicly callable without backend authorization.

---

# 20. AI Prompt Strategy

Instead of:

```text
Is this the same laptop?
```

use structured instructions:

```text
Analyze the supplied recovered-item photo.

Return JSON containing:
- object_type
- category
- brand
- primary_color
- secondary_colors
- visible_features
- visible_text
- approximate_object_description
- confidence

Do not invent details that are not visually supported.
Return null when a field cannot be determined.
```

Then compare the structured output against the lost report.

---

# 21. Better Use of Microsoft Foundry

Use Microsoft Foundry for:

### Model-driven understanding

```text
image -> attributes
image -> OCR
text -> normalized description
```

### Embeddings

```text
text -> vector
image -> vector
```

### Optional explanation agent

A final explanation layer can summarize:

```text
Why this item is being suggested
```

Do not let the explanation agent control the database state.

Microsoft Foundry exposes project APIs/SDKs for application integration, and vision-enabled chat models support image inputs. citeturn599500search2turn599500search3turn599500search13

---

# 22. Backend Project Structure

```text
lost-found-platform/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   │   ├── firebase.ts
│   │   │   └── api.ts
│   │   └── hooks/
│   │
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── auth/
│   │   │   └── firebase.py
│   │   │
│   │   ├── database/
│   │   │   ├── db.py
│   │   │   ├── models.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── lost_items.py
│   │   │   ├── found_items.py
│   │   │   ├── matches.py
│   │   │   └── claims.py
│   │   │
│   │   ├── ai/
│   │   │   ├── foundry_client.py
│   │   │   ├── vision.py
│   │   │   ├── embeddings.py
│   │   │   └── matcher.py
│   │   │
│   │   └── services/
│   │       ├── matching_service.py
│   │       ├── storage_service.py
│   │       └── notification_service.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── firebase/
│   └── ...
│
├── storage/
│
└── README.md
```

---

# 23. Recommended Development Phases

## Phase 1 — Authentication

Build:

```text
Firebase signup
Firebase login
Student profile
Logout
Protected routes
```

Deliverable:

```text
Authenticated student dashboard
```

---

## Phase 2 — Lost Item CRUD

Build:

```text
Create lost item
View own lost items
Edit
Delete
Close as found
```

Deliverable:

```text
Complete lost-item reporting system
```

---

## Phase 3 — Image Storage

Build:

```text
Image upload
Image validation
Secure storage
SQLite image path
```

Deliverable:

```text
Lost + found image handling
```

---

## Phase 4 — Microsoft Foundry Vision

Build:

```text
Image -> AI attributes
Image -> OCR when relevant
Text -> normalized attributes
```

Deliverable:

```text
AI item understanding
```

---

## Phase 5 — Multimodal Embeddings

Build:

```text
Lost description -> text embedding
Lost image -> image embedding
Found image -> image embedding
```

Deliverable:

```text
Semantic visual retrieval
```

---

## Phase 6 — Matching Engine

Build:

```text
candidate filter
+
vector similarity
+
attribute scoring
+
location/date compatibility
```

Deliverable:

```text
Possible Matches
```

---

## Phase 7 — Claims

Build:

```text
claim request
owner verification
admin moderation
return confirmation
```

Deliverable:

```text
End-to-end lost -> found -> return workflow
```

---

# 24. MVP User Journey

## Owner

```text
Signup
  ↓
Login
  ↓
Report Lost Item
  ↓
Description + optional image
  ↓
AI processes report
  ↓
Lost item becomes ACTIVE
```

## Finder

```text
Signup/Login
  ↓
Found Something
  ↓
Take photo
  ↓
Upload
  ↓
AI vision analysis
  ↓
Embedding generated
  ↓
Candidate lost reports retrieved
  ↓
Possible matches displayed
  ↓
Claim initiated
```

## System

```text
Claim
  ↓
Owner verification
  ↓
Admin review when needed
  ↓
Return
  ↓
Both records closed
```

---

# 25. Architecture Decisions

## Decision 1

### Firebase Auth + SQLite

Yes.

Reason:

```text
Firebase = identity
SQLite = application data
```

This keeps responsibilities clear.

---

## Decision 2

### Store embeddings in SQLite

For the MVP:

```text
embedding -> float32 array -> BLOB
```

The backend loads candidate vectors and performs cosine similarity.

For a larger deployment, a dedicated vector database/search service would be more scalable. However, introducing one would violate the simplicity of your current SQLite-centered requirement, so it should remain a later optimization.

---

## Decision 3

### Use AI for candidate generation and explanation, not automatic ownership

Correct flow:

```text
AI suggests
      ↓
System verifies signals
      ↓
Human confirmation
```

Not:

```text
AI says match
      ↓
Automatically transfer ownership
```

---

# 26. Key Failure Cases

## Case A — Poor quality photo

Return:

```text
"Image quality is too low for reliable analysis. Please upload a clearer image."
```

## Case B — Multiple matches

Show:

```text
Top possible matches
```

rather than choosing one automatically.

## Case C — No lost-image exists

Use:

```text
Found image ↔ lost text embedding
```

plus structured attributes.

## Case D — No useful visual evidence

Fallback to:

```text
description
category
brand
location
date
```

## Case E — AI unavailable

The platform should still allow:

```text
Lost item posting
Found item posting
Manual search
Claims
```

AI should be an enhancement, not a single point of failure for the whole portal.

---

# 27. Admin Dashboard

Admin should see:

```text
Total students
Active lost items
Found items
Potential matches
Pending claims
Completed returns
Flagged reports
AI failures
```

### Admin actions

```text
Suspend user
Remove fraudulent report
Review claim
Approve/reject disputed claim
Close stale report
Review AI match
```

---

# 28. Notifications

Recommended events:

```text
Possible match found
Claim received
Claim approved
Claim rejected
Item returned
Report closed
```

For MVP, these can be in-app notifications.

Later:

```text
Email
Push notification
University portal notification
```

---

# 29. Important Security Model

```text
Browser
   |
   | HTTPS
   v
FastAPI
   |
   +--> Verify Firebase token
   |
   +--> Authorize resource
   |
   +--> Query SQLite
   |
   +--> Call Foundry
   |
   +--> Return sanitized result
```

Never expose:

```text
Foundry API key
Firebase service-account private key
SQLite file
Storage private credentials
```

to the frontend.

---

# 30. Final Optimized Architecture

```text
                    ┌───────────────────────┐
                    │   UNIVERSITY STUDENT  │
                    └───────────┬───────────┘
                                │
                                v
                    ┌───────────────────────┐
                    │ React + TypeScript UI │
                    └───────────┬───────────┘
                                │
                Firebase Auth ID Token
                                │
                                v
                    ┌───────────────────────┐
                    │    FastAPI Backend    │
                    └───────┬───────┬───────┘
                            │       │
             ┌──────────────┘       └───────────────┐
             v                                      v
   ┌──────────────────┐                  ┌──────────────────────┐
   │ Firebase Auth    │                  │ SQLite               │
   │ Identity         │                  │ Users                │
   └──────────────────┘                  │ Lost Items           │
                                         │ Found Items          │
                                         │ Matches              │
                                         │ Claims               │
                                         └──────────────────────┘
             │
             │
             v
   ┌──────────────────────┐
   │ Image Storage        │
   │ Firebase Storage /   │
   │ Object Storage       │
   └──────────┬───────────┘
              │
              v
   ┌──────────────────────────────┐
   │      Microsoft Foundry      │
   │                              │
   │ Vision / Multimodal Models  │
   │ OCR                         │
   │ Attribute Extraction        │
   │ Text Analysis               │
   │ Multimodal Embeddings       │
   └──────────────┬───────────────┘
                  │
                  v
        ┌──────────────────────┐
        │ Matching Engine      │
        │                      │
        │ Metadata Filter      │
        │ Vector Similarity    │
        │ Attribute Similarity │
        │ Time/Location        │
        └──────────┬───────────┘
                   │
                   v
          ┌───────────────────┐
          │ Possible Matches  │
          └─────────┬─────────┘
                    │
                    v
          ┌───────────────────┐
          │ Human Verification│
          └─────────┬─────────┘
                    │
                    v
              ┌───────────┐
              │ Returned  │
              └───────────┘
```

---

# 31. Recommended MVP Scope

Build these first:

```text
1. Firebase signup/login
2. Student profile
3. Report Lost Item
4. Report Found Item
5. Image upload
6. Microsoft Foundry image analysis
7. Text/image embeddings
8. Candidate retrieval
9. Match score + explanation
10. Claim workflow
11. Admin dashboard
12. Return confirmation
```

Do not start with:

```text
real-time notifications
complex agents
vector database
microservices
mobile apps
advanced recommendation systems
```

Keep the first release as a **single FastAPI backend + SQLite + React frontend + Firebase Auth + Foundry AI**.

---

# 32. The One-Sentence Project Pitch

> **An AI-powered university Lost & Found platform that combines Firebase-authenticated student identities, SQLite-based item records, and Microsoft Foundry multimodal AI to match recovered-item photos with lost-item descriptions and images while keeping ownership verification under human control.**

---

## Sources

- Microsoft Foundry overview and project architecture: https://learn.microsoft.com/en-us/azure/foundry/ citeturn642301search3turn642301search7
- Microsoft Foundry SDK/project endpoint: citeturn599500search2turn599500search3
- Vision/image analysis: citeturn642301search2turn642301search4
- Vision-enabled multimodal models: citeturn642301search8
- Multimodal embeddings: citeturn599500search1turn599500search5
- Firebase Authentication and ID-token verification: citeturn642301search0turn599500search0
- SQLite foreign keys and transactions: citeturn642301search1turn642301search5


---

# PART III — PHASE-BY-PHASE PROJECT PLAN

# University AI Lost & Found — Phase-by-Phase Project Plan

> **Source of truth:** `University_AI_Lost_And_Found_Architecture.md`
>
> **Rule:** Implement one phase at a time. Do not begin the next phase until the current phase passes its acceptance criteria.

---

# 0. Project Definition

## Objective

Build a university-only Lost & Found portal where students can:

1. Register/login with Firebase Authentication.
2. Maintain their university profile.
3. Report a lost item using structured details and an optional image.
4. Report a found item using a photo.
5. Use Microsoft Foundry for image analysis, OCR, text understanding, and multimodal embeddings.
6. Retrieve likely lost-item matches for a found-item photo.
7. Submit and process claims.
8. Verify ownership before personal contact information is exposed.
9. Allow admins to moderate reports, claims, and suspicious activity.

## Fixed Technology Decisions

| Area | Technology |
|---|---|
| Frontend | React + Vite + TypeScript |
| Authentication | Firebase Authentication |
| Backend | Python FastAPI |
| Database | SQLite |
| Image/File Storage | Firebase Storage or compatible object storage |
| AI Platform | Microsoft Foundry |
| AI | Vision analysis, OCR, attribute extraction, multimodal embeddings |
| Matching | Metadata filtering + vector similarity + deterministic scoring |
| Initial Deployment | Single backend instance with persistent SQLite storage |

---

# 1. Implementation Principles

- [ ] Keep authentication, application data, storage, and AI responsibilities separate.
- [ ] Firebase Authentication owns identity.
- [ ] SQLite owns application records.
- [ ] Image binaries are not stored inside SQLite.
- [ ] Microsoft Foundry secrets stay on the backend.
- [ ] Backend verifies Firebase ID tokens.
- [ ] AI generates evidence and candidate matches; it does not automatically establish ownership.
- [ ] Sensitive student information is hidden from other students unless the workflow explicitly permits disclosure.
- [ ] Prefer deterministic business rules over free-form LLM decisions.
- [ ] AI endpoints must be authenticated and rate-limited.
- [ ] Keep every phase small enough to test independently.
- [ ] Do not introduce a vector database in the MVP unless SQLite retrieval becomes a measured bottleneck.
- [ ] Use the same multimodal embedding model/version for comparable vectors.

---

# 2. Phase 0 — Repository & Development Setup

## Goal

Create a clean, reproducible project foundation.

## Tasks

### Repository

- [ ] Create GitHub repository.
- [ ] Create `frontend/`.
- [ ] Create `backend/`.
- [ ] Create `docs/`.
- [ ] Add `README.md`.
- [ ] Add `ARCHITECTURE.md`.
- [ ] Add `PROJECT_PLAN.md`.
- [ ] Add `.gitignore`.
- [ ] Add `.env.example`.
- [ ] Add license if required by the project.
- [ ] Create initial Git commit.

### Development environment

- [ ] Configure Python virtual environment.
- [ ] Configure Node.js project.
- [ ] Install FastAPI backend dependencies.
- [ ] Install React frontend dependencies.
- [ ] Add formatting/linting configuration.
- [ ] Add basic backend health endpoint.
- [ ] Add basic frontend route.
- [ ] Document local setup instructions.

## Deliverable

A repository that can run:

```text
Frontend: React development server
Backend: FastAPI development server
```

## Acceptance Criteria

- [ ] `git clone` + documented commands can reproduce the project locally.
- [ ] Frontend opens successfully.
- [ ] Backend starts successfully.
- [ ] `GET /health` returns success.
- [ ] No secrets are committed.

---

# 3. Phase 1 — Firebase Project & Authentication

## Goal

Implement secure student authentication using Firebase Authentication.

## Firebase setup

- [ ] Create Firebase project.
- [ ] Enable required authentication providers.
- [ ] Enable Email/Password authentication.
- [ ] Configure authorized domains.
- [ ] Create frontend Firebase configuration.
- [ ] Create backend Firebase Admin credentials/service configuration.
- [ ] Store secrets only in environment variables.

## Frontend

- [ ] Build signup page.
- [ ] Build login page.
- [ ] Build logout.
- [ ] Add auth state listener.
- [ ] Add protected routes.
- [ ] Handle auth loading/error states.

## Backend

- [ ] Add Firebase Admin SDK.
- [ ] Create token-verification middleware/dependency.
- [ ] Extract verified `firebase_uid`.
- [ ] Reject invalid/expired tokens.
- [ ] Add authenticated test endpoint.

## Deliverable

```text
Student
  -> Sign Up
  -> Login
  -> Receive Firebase session
  -> Call protected backend API
```

## Acceptance Criteria

- [ ] New student can register.
- [ ] Existing student can log in.
- [ ] Logout works.
- [ ] Protected frontend pages require authentication.
- [ ] Backend rejects requests with no valid Firebase ID token.
- [ ] Backend derives identity from verified token rather than trusting browser-supplied user IDs.

---

# 4. Phase 2 — Student Profile & University Identity

## Goal

Capture the university details needed by the platform.

## Profile fields

- [ ] Full Name
- [ ] Roll Number
- [ ] Class / Section
- [ ] Course / Program
- [ ] Semester
- [ ] Phone Number
- [ ] University Email
- [ ] Campus

## Backend

- [ ] Create `users` table.
- [ ] Link profile to Firebase UID.
- [ ] Implement profile creation.
- [ ] Implement profile retrieval.
- [ ] Implement profile update.
- [ ] Validate unique roll number.
- [ ] Validate unique email where required.
- [ ] Add ownership checks.

## Frontend

- [ ] Profile form.
- [ ] Profile page.
- [ ] Edit profile.
- [ ] Profile completion state.

## Deliverable

A verified Firebase account is linked to one application profile in SQLite.

## Acceptance Criteria

- [ ] Every authenticated student can create/retrieve their profile.
- [ ] Duplicate roll numbers are rejected.
- [ ] Student cannot edit another student's profile.
- [ ] Firebase UID is stored as the identity link.

---

# 5. Phase 3 — SQLite Database Foundation

## Goal

Create the initial database schema and repository/data-access layer.

## Required tables

### `users`

```text
id
firebase_uid
name
roll_number
class_name
course
semester
phone
email
campus
created_at
```

### `lost_items`

```text
id
user_id
item_name
category
color
brand
description
distinctive_features
lost_date
lost_location
image_path
ai_attributes_json
text_embedding
image_embedding
status
created_at
```

### `found_items`

```text
id
finder_id
image_path
location
ai_attributes_json
image_embedding
status
created_at
```

### `matches`

```text
id
found_item_id
lost_item_id
image_text_score
image_image_score
attribute_score
location_score
date_score
final_score
explanation_json
status
created_at
```

### `claims`

```text
id
match_id
claimant_id
owner_id
status
verification_data_json
created_at
resolved_at
```

## Database rules

- [ ] Enable foreign keys.
- [ ] Use transactions for state changes.
- [ ] Add indexes on common lookup fields.
- [ ] Add status constraints/validation.
- [ ] Add timestamps.
- [ ] Create migrations or a repeatable schema initialization process.
- [ ] Add seed/test data.

## Deliverable

A working SQLite persistence layer.

## Acceptance Criteria

- [ ] Tables create successfully from a clean database.
- [ ] Foreign keys are enforced.
- [ ] CRUD works for the initial entities.
- [ ] Transactions roll back correctly.
- [ ] Tests cover basic persistence.

---

# 6. Phase 4 — Lost Item Reporting

## Goal

Allow students to submit a complete lost-item report.

## Frontend form

### Required

- [ ] Item Name
- [ ] Category
- [ ] Description
- [ ] Lost Date
- [ ] Lost Location

### Optional

- [ ] Color
- [ ] Brand
- [ ] Distinctive Features
- [ ] Image

## Backend

- [ ] `POST /api/lost-items`
- [ ] `GET /api/lost-items`
- [ ] `GET /api/lost-items/{id}`
- [ ] `PATCH /api/lost-items/{id}`
- [ ] `DELETE /api/lost-items/{id}`

## Rules

- [ ] Only authenticated students can create reports.
- [ ] Student can edit/delete their own active reports.
- [ ] Validate fields server-side.
- [ ] Default status = `ACTIVE`.
- [ ] Prevent unauthorized access to another student's private data.

## Deliverable

A complete non-AI lost-item workflow.

## Acceptance Criteria

- [ ] Student can submit a lost item.
- [ ] Item appears in their dashboard.
- [ ] Item can be edited.
- [ ] Item can be removed/closed according to status rules.
- [ ] Data survives backend restart.

---

# 7. Phase 5 — Image Upload & Storage

## Goal

Add secure image handling without storing binary image data in SQLite.

## Tasks

- [ ] Select storage provider.
- [ ] Configure storage bucket.
- [ ] Implement authenticated upload.
- [ ] Validate MIME type.
- [ ] Validate file size.
- [ ] Validate image dimensions where useful.
- [ ] Generate safe server-side filenames/paths.
- [ ] Store only image path/reference in SQLite.
- [ ] Add download/view permissions.
- [ ] Handle failed uploads cleanly.

## Deliverable

Lost and found images are securely stored externally.

## Acceptance Criteria

- [ ] Valid image upload succeeds.
- [ ] Invalid file types are rejected.
- [ ] Oversized files are rejected.
- [ ] SQLite stores only the reference/path.
- [ ] Users cannot arbitrarily access private files.

---

# 8. Phase 6 — Found Item Workflow

## Goal

Create the "I Found Something" workflow.

## Frontend

- [ ] Add `I Found an Item` action.
- [ ] Camera/photo upload UI.
- [ ] Image preview.
- [ ] Optional location field.
- [ ] Submit button.
- [ ] Analysis/loading state.
- [ ] Results screen.

## Backend

- [ ] `POST /api/found-items`
- [ ] Store found item.
- [ ] Store image.
- [ ] Set status = `UNCLAIMED`.
- [ ] Trigger analysis pipeline.

## Deliverable

A finder can upload a recovered item's photo.

## Acceptance Criteria

- [ ] Finder can upload a photo.
- [ ] Found item record is created.
- [ ] Image reference is stored.
- [ ] Finder is linked to the found item.
- [ ] No owner personal information is exposed yet.

---

# 9. Phase 7 — Microsoft Foundry Integration

## Goal

Integrate Microsoft Foundry behind the FastAPI backend.

## Setup

- [ ] Create/configure Microsoft Foundry project.
- [ ] Select appropriate vision-capable model/tool.
- [ ] Configure project endpoint/credentials.
- [ ] Store secrets in backend environment variables.
- [ ] Create `foundry_client.py`.

## AI service modules

```text
backend/app/ai/
├── foundry_client.py
├── vision.py
├── ocr.py
├── embeddings.py
└── matcher.py
```

## Image analysis

Extract only attributes supported by the image:

```json
{
  "object_type": null,
  "category": null,
  "brand": null,
  "primary_color": null,
  "secondary_colors": [],
  "visible_features": [],
  "visible_text": [],
  "description": null,
  "confidence": 0.0
}
```

## Rules

- [ ] Return structured JSON.
- [ ] Do not invent unsupported attributes.
- [ ] Use `null` when a property cannot be determined.
- [ ] Log AI failures without logging sensitive image contents.
- [ ] Add request timeouts/retries carefully.
- [ ] Rate-limit AI requests.

## Deliverable

Foundry can analyze a submitted item photo and return structured attributes.

## Acceptance Criteria

- [ ] Test image returns valid structured output.
- [ ] Invalid images fail gracefully.
- [ ] Backend secrets are not exposed to frontend.
- [ ] AI outage does not crash the entire application.

---

# 10. Phase 8 — OCR & Text Understanding

## Goal

Use AI/OCR where visible text can improve matching.

## Use cases

- University ID card
- Notebook
- Book
- Bottle label
- Laptop sticker
- Bag branding
- Other item markings

## Tasks

- [ ] Detect whether OCR is useful.
- [ ] Extract visible text.
- [ ] Normalize text.
- [ ] Distinguish sensitive text from useful matching signals.
- [ ] Avoid exposing raw OCR to finders.
- [ ] Minimize persistent storage of highly sensitive OCR data.

## Deliverable

OCR/text signals can contribute to matching without unnecessarily exposing private information.

## Acceptance Criteria

- [ ] OCR is stored/processed according to privacy rules.
- [ ] Raw sensitive text is not shown in public match results.
- [ ] OCR failures fall back to visual/metadata matching.

---

# 11. Phase 9 — Text & Image Multimodal Embeddings

## Goal

Create comparable embeddings for lost and found items.

## Embedding inputs

### Lost report

- [ ] Lost description → text embedding
- [ ] Lost image → image embedding if image exists

### Found report

- [ ] Found image → image embedding

## Required rule

Use the same compatible model/version for vectors that will be directly compared.

## Storage

For the MVP:

```text
embedding
    ↓
float32 array
    ↓
BLOB in SQLite
```

## Backend modules

```text
embeddings.py
    ├── embed_text()
    ├── embed_image()
    ├── serialize_vector()
    └── deserialize_vector()
```

## Deliverable

The system can produce and persist embeddings for searchable reports.

## Acceptance Criteria

- [ ] Text embedding is generated.
- [ ] Image embedding is generated.
- [ ] Embeddings can be retrieved from SQLite.
- [ ] Cosine similarity calculation is tested.
- [ ] Missing image cases are supported.

---

# 12. Phase 10 — Candidate Retrieval

## Goal

Avoid comparing a new found image against every lost report.

## Stage 1 — Hard filtering

Filter active lost reports using available metadata:

- [ ] Status = `ACTIVE`
- [ ] Category
- [ ] Campus
- [ ] Approximate location
- [ ] Reasonable date window
- [ ] Optional brand

## Stage 2 — Similarity candidates

- [ ] Compare found image embedding to lost image embeddings.
- [ ] Compare found image embedding to lost description embeddings.
- [ ] Compare AI-extracted attributes.
- [ ] Return top candidate set.

## Deliverable

Example:

```text
500 active lost reports
        ↓
Metadata filtering
        ↓
40 candidates
        ↓
Embedding comparison
        ↓
Top 10 candidates
```

## Acceptance Criteria

- [ ] Candidate retrieval is reproducible.
- [ ] Closed reports are excluded.
- [ ] Results include score components.
- [ ] No sensitive owner details are returned to the finder.

---

# 13. Phase 11 — Match Scoring Engine

## Goal

Convert multiple signals into one explainable candidate score.

## Signals

```text
S_image_text
S_image_image
S_attributes
S_location
S_date
```

## Initial MVP scoring

When lost image exists:

```text
Final Score =
    0.45 * Image/Text Semantic Similarity
  + 0.20 * Lost Image Similarity
  + 0.15 * Attribute Similarity
  + 0.10 * Location Compatibility
  + 0.10 * Date Compatibility
```

When lost image does not exist:

```text
Final Score =
    0.55 * Image/Text Semantic Similarity
  + 0.20 * Attribute Similarity
  + 0.15 * Location Compatibility
  + 0.10 * Date Compatibility
```

> These are starting engineering weights only. They must be calibrated using real labelled examples.

## Score bands

Initial product configuration:

```text
>= 0.85  → Strong candidate
0.70–0.85 → Possible candidate
< 0.70  → Low-confidence
```

## Tasks

- [ ] Implement individual score functions.
- [ ] Normalize score ranges.
- [ ] Implement weighted final score.
- [ ] Save component scores to SQLite.
- [ ] Generate human-readable explanations.
- [ ] Add unit tests.

## Deliverable

An explainable match engine.

## Acceptance Criteria

- [ ] Same/near-identical examples score highly.
- [ ] Clearly unrelated items score low.
- [ ] Each result exposes why it was suggested.
- [ ] AI explanation cannot modify the underlying score.

---

# 14. Phase 12 — Match Results UI

## Goal

Show useful possible matches without exposing private student information.

## Example result

```text
Possible Match Found

87% similarity

Black Lenovo Laptop

Why this is being suggested:
✓ Same category
✓ Similar black appearance
✓ Brand appears consistent
✓ Similar distinctive feature
✓ Compatible location
```

## Frontend tasks

- [ ] Match result cards.
- [ ] Confidence/similarity display.
- [ ] Explanation section.
- [ ] Item details allowed by privacy policy.
- [ ] `View Match`.
- [ ] `This is not my item`.
- [ ] `Request Claim`.

## Deliverable

Finder can understand why the system suggested a candidate.

## Acceptance Criteria

- [ ] Results are understandable without seeing internal AI JSON.
- [ ] Owner phone/email/roll number remain hidden.
- [ ] Low-confidence matches are not presented as confirmed ownership.

---

# 15. Phase 13 — Claims & Ownership Verification

## Goal

Create a controlled return workflow.

## Claim lifecycle

```text
SUGGESTED
   ↓
CLAIM_REQUESTED
   ↓
OWNER_VERIFICATION
   ↓
ADMIN_REVIEW (when required)
   ↓
APPROVED / REJECTED
   ↓
RETURNED
```

## Tasks

- [ ] Create claim API.
- [ ] Create claim page.
- [ ] Link finder, owner, match.
- [ ] Add private verification information.
- [ ] Hide verification answers from claimant.
- [ ] Allow owner to confirm/reject.
- [ ] Add admin review path.
- [ ] Prevent duplicate active claims.
- [ ] Add claim history.

## Deliverable

An end-to-end claim workflow that does not rely solely on AI.

## Acceptance Criteria

- [ ] Finder can submit a claim.
- [ ] Owner can review it.
- [ ] Owner can approve/reject.
- [ ] Admin can intervene.
- [ ] Claim state changes are transactional.
- [ ] Sensitive information is protected.

---

# 16. Phase 14 — Return & Closure Workflow

## Goal

Complete the physical return process.

## Tasks

- [ ] Confirm item handover.
- [ ] Mark claim as `COMPLETED`.
- [ ] Mark lost item as `RETURNED`.
- [ ] Mark found item as `RETURNED`.
- [ ] Close related match.
- [ ] Prevent new claims after closure.
- [ ] Record timestamps.
- [ ] Preserve audit history.

## Deliverable

Completed items disappear from active matching.

## Acceptance Criteria

- [ ] Returned items cannot remain active.
- [ ] Related workflows are updated consistently.
- [ ] Transaction rollback protects against partial updates.

---

# 17. Phase 15 — Admin Dashboard

## Goal

Give administrators control over moderation, claims, and platform health.

## Dashboard metrics

- [ ] Total students
- [ ] Active lost items
- [ ] Found items
- [ ] Potential matches
- [ ] Pending claims
- [ ] Completed returns
- [ ] Flagged reports
- [ ] AI failures

## Admin capabilities

- [ ] Review users.
- [ ] Review lost reports.
- [ ] Review found reports.
- [ ] Review claims.
- [ ] Approve/reject disputes.
- [ ] Remove fraudulent reports.
- [ ] Suspend abusive users.
- [ ] Close stale reports.
- [ ] Review AI match suggestions.

## Acceptance Criteria

- [ ] Admin routes require admin authorization.
- [ ] Normal students cannot access admin APIs.
- [ ] Admin actions are logged.

---

# 18. Phase 16 — Search, Filters & Manual Fallback

## Goal

Ensure the portal remains usable even when AI is unavailable.

## Features

- [ ] Search by item name.
- [ ] Filter by category.
- [ ] Filter by campus/location.
- [ ] Filter by date.
- [ ] Filter by status.
- [ ] Optional brand/color filtering.

## AI fallback

If Microsoft Foundry is unavailable:

```text
AI unavailable
   ↓
Manual structured search
   ↓
User can still report/retrieve items
```

## Acceptance Criteria

- [ ] Core application remains usable during AI outage.
- [ ] Manual search returns active items.
- [ ] AI failures are clearly surfaced but do not break core CRUD.

---

# 19. Phase 17 — Notifications

## Goal

Notify students about important workflow events.

## MVP

- [ ] In-app notifications.
- [ ] Possible match found.
- [ ] Claim received.
- [ ] Claim approved.
- [ ] Claim rejected.
- [ ] Item returned.
- [ ] Report closed.

## Later

- [ ] Email notifications.
- [ ] Push notifications.

## Acceptance Criteria

- [ ] Important status changes create notification records.
- [ ] Notifications are tied to the authenticated user.

---

# 20. Phase 18 — Security & Abuse Prevention

## Goal

Harden the platform before deployment.

## Authentication & authorization

- [ ] Verify Firebase ID tokens on protected APIs.
- [ ] Enforce resource ownership.
- [ ] Add admin authorization.
- [ ] Never trust client-provided identity.
- [ ] Protect private routes.

## File security

- [ ] MIME validation.
- [ ] File size limits.
- [ ] Safe filenames.
- [ ] Reject unsupported file types.
- [ ] Restrict access to private storage.

## AI security

- [ ] Rate limit AI endpoints.
- [ ] Backend-only Foundry credentials.
- [ ] Add request timeouts.
- [ ] Protect against prompt injection in user-supplied text where relevant.
- [ ] Avoid sending unnecessary personal information to AI services.

## Data security

- [ ] Avoid exposing phone/email/roll number in match results.
- [ ] Minimize OCR storage.
- [ ] Audit sensitive actions.
- [ ] Add soft-delete/state-based deletion where appropriate.

## Acceptance Criteria

- [ ] Unauthorized requests are rejected.
- [ ] Secrets are not present in frontend bundles.
- [ ] Basic abuse/rate-limit tests pass.

---

# 21. Phase 19 — Testing

## Unit tests

- [ ] Authentication middleware.
- [ ] Profile validation.
- [ ] Lost-item CRUD.
- [ ] Found-item CRUD.
- [ ] Embedding serialization.
- [ ] Cosine similarity.
- [ ] Match scoring.
- [ ] Status transitions.
- [ ] Claim rules.

## Integration tests

- [ ] Firebase token + backend authentication.
- [ ] API + SQLite.
- [ ] Upload + database reference.
- [ ] AI analysis + database update.
- [ ] Matching pipeline.
- [ ] Claim workflow.

## End-to-end scenarios

### Scenario A — Lost item

```text
Signup
→ Login
→ Report Lost Item
→ View Report
```

### Scenario B — Found item

```text
Login
→ Found Item
→ Upload Photo
→ AI Analysis
→ Candidate Matches
```

### Scenario C — Successful return

```text
Found Item
→ Match
→ Claim
→ Owner Verification
→ Admin Review
→ Approved
→ Returned
→ Closed
```

### Scenario D — AI unavailable

```text
Found Item
→ AI Failure
→ Manual Search Still Works
```

---

# 22. Phase 20 — AI Evaluation & Calibration

## Goal

Measure whether the AI matching system is actually useful.

## Create a labelled evaluation dataset

Each example should have:

```text
Found Item
Lost Item
True Match? YES/NO
```

Add difficult cases:

- [ ] Same category, different item.
- [ ] Same brand, different model.
- [ ] Similar colors.
- [ ] Similar-looking objects.
- [ ] Poor image quality.
- [ ] Multiple plausible candidates.
- [ ] No lost image.
- [ ] OCR text mismatch.

## Metrics

Track:

```text
Precision
Recall
Top-1 accuracy
Top-5 retrieval accuracy
False positive rate
False negative rate
```

## Tasks

- [ ] Evaluate initial thresholds.
- [ ] Tune score weights.
- [ ] Compare image-only vs hybrid matching.
- [ ] Measure value of location/date filtering.
- [ ] Document failure cases.

## Acceptance Criteria

- [ ] Match system has measurable performance.
- [ ] Thresholds are based on observed results rather than arbitrary numbers.
- [ ] Known failure modes are documented.

---

# 23. Phase 21 — Performance Optimization

## Goal

Keep the MVP responsive as the number of reports grows.

## Optimize

- [ ] Add SQLite indexes.
- [ ] Limit candidate retrieval before vector comparisons.
- [ ] Cache repeated AI results where safe.
- [ ] Avoid duplicate embedding generation.
- [ ] Resize/compress images where appropriate.
- [ ] Paginate dashboard lists.
- [ ] Avoid sending full match data to frontend.
- [ ] Measure API latency.

## Future scale trigger

Consider a dedicated vector search service only when measured data size/performance requires it.

Do not introduce a vector database simply because embeddings exist.

---

# 24. Phase 22 — UI/UX Polish

## Student experience

- [ ] Responsive layout.
- [ ] Mobile-friendly camera workflow.
- [ ] Clear empty states.
- [ ] Loading indicators.
- [ ] AI analysis progress indicator.
- [ ] Error messages.
- [ ] Accessible forms.
- [ ] Consistent status badges.
- [ ] Confirmation dialogs for destructive actions.

## Important screens

```text
Landing / Login
Signup
Dashboard
Profile
Report Lost Item
I Found an Item
Potential Matches
Match Details
Claims
Notifications
Admin Dashboard
```

---

# 25. Phase 23 — Deployment

## Frontend

- [ ] Create production build.
- [ ] Configure Firebase client environment variables.
- [ ] Deploy frontend.
- [ ] Configure production domain.

## Backend

- [ ] Configure production environment variables.
- [ ] Configure Firebase Admin credentials securely.
- [ ] Configure Microsoft Foundry credentials securely.
- [ ] Configure persistent SQLite storage.
- [ ] Configure image storage.
- [ ] Deploy FastAPI backend.
- [ ] Enable HTTPS.

## Database

- [ ] Run production schema/migrations.
- [ ] Verify foreign-key enforcement.
- [ ] Configure backup strategy.
- [ ] Test restore procedure.

## Acceptance Criteria

- [ ] Production login works.
- [ ] Production APIs work over HTTPS.
- [ ] AI integration works.
- [ ] SQLite data persists across restarts/deployments.
- [ ] Images persist independently of application container lifecycle.

---

# 26. Phase 24 — Production Monitoring

## Track

- [ ] API errors.
- [ ] Authentication failures.
- [ ] AI failures.
- [ ] AI latency.
- [ ] Image upload failures.
- [ ] Match-generation failures.
- [ ] Claim failures.
- [ ] Database errors.

## Admin health dashboard

```text
API Health
Database Health
AI Health
Storage Health
```

---

# 27. Phase 25 — Documentation & Viva Preparation

## Technical documentation

- [ ] Final architecture diagram.
- [ ] Database ER diagram.
- [ ] API documentation.
- [ ] Authentication flow.
- [ ] AI pipeline.
- [ ] Matching algorithm.
- [ ] Security model.
- [ ] Deployment guide.

## Viva questions to prepare

### Why Firebase Authentication?

Explain separation of identity from application data.

### Why SQLite?

Explain simplicity and suitability for the MVP.

### Why Microsoft Foundry?

Explain vision, OCR, text understanding, and multimodal embedding capabilities.

### Why embeddings?

Explain semantic/visual similarity instead of only keyword matching.

### Why not compare every item with AI?

Explain candidate filtering and cost/latency optimization.

### Why not let AI decide ownership?

Explain false positives and need for human verification.

### What happens if the user has no lost-item image?

Explain found-image ↔ lost-description matching.

### What happens if AI fails?

Explain manual search and normal reporting still work.

### Where are images stored?

Explain object storage, while SQLite stores references.

---

# 28. Final MVP Definition

The MVP is considered complete when all of the following work end-to-end:

```text
Firebase Signup/Login
        ↓
Student Profile
        ↓
Report Lost Item
        ↓
Optional Image
        ↓
SQLite Record
        ↓
Report Found Item
        ↓
Found Photo
        ↓
Microsoft Foundry Analysis
        ↓
Multimodal Embeddings
        ↓
Candidate Filtering
        ↓
Hybrid Match Score
        ↓
Possible Matches
        ↓
Claim Request
        ↓
Owner Verification
        ↓
Admin Review (when needed)
        ↓
Return Confirmation
        ↓
Records Closed
```

---

# 29. Build Order Summary

```text
PHASE 0   Repository & Setup
   ↓
PHASE 1   Firebase Authentication
   ↓
PHASE 2   Student Profile
   ↓
PHASE 3   SQLite Database
   ↓
PHASE 4   Lost Item Reporting
   ↓
PHASE 5   Image Storage
   ↓
PHASE 6   Found Item Workflow
   ↓
PHASE 7   Microsoft Foundry
   ↓
PHASE 8   OCR & Text Understanding
   ↓
PHASE 9   Multimodal Embeddings
   ↓
PHASE 10  Candidate Retrieval
   ↓
PHASE 11  Match Scoring
   ↓
PHASE 12  Match UI
   ↓
PHASE 13  Claims & Verification
   ↓
PHASE 14  Return & Closure
   ↓
PHASE 15  Admin Dashboard
   ↓
PHASE 16  Manual Search/Fallback
   ↓
PHASE 17  Notifications
   ↓
PHASE 18  Security
   ↓
PHASE 19  Testing
   ↓
PHASE 20  AI Evaluation
   ↓
PHASE 21  Performance
   ↓
PHASE 22  UI/UX Polish
   ↓
PHASE 23  Deployment
   ↓
PHASE 24  Monitoring
   ↓
PHASE 25  Documentation/Viva
```

---

# 30. Recommended First Coding Prompt

After creating this project plan, give your coding agent:

```text
Read these two files first:

1. University_AI_Lost_And_Found_Architecture.md
2. University_AI_Lost_And_Found_Project_Plan.md

You are implementing Phase 0 only.

Do not implement Phase 1 or later.

Tasks:
- Create the repository/project structure.
- Create frontend React + Vite + TypeScript skeleton.
- Create backend FastAPI skeleton.
- Add configuration/environment handling.
- Add /health endpoint.
- Add .gitignore.
- Add .env.example.
- Add README with local setup instructions.
- Keep the architecture consistent with the two specification files.
- Do not add unnecessary services or technologies.

At the end:
1. Show the files created.
2. Explain how to run frontend and backend.
3. Show tests/checks performed.
4. Stop and wait for approval before implementing the next phase.
```

---

# 31. Phase Completion Rule

At the end of every phase, produce:

```text
PHASE: <number>
STATUS: COMPLETE / BLOCKED

Implemented:
- ...

Files changed:
- ...

Tests:
- ...

Known issues:
- ...

Next phase:
- ...

Do not automatically start the next phase.
```

---

# 32. Project Success Criteria

The project succeeds when it demonstrates:

1. **Reliable student authentication**
2. **Complete lost/found workflows**
3. **Secure SQLite-backed application data**
4. **Microsoft Foundry AI integration**
5. **Image + text semantic matching**
6. **Explainable candidate recommendations**
7. **Human ownership verification**
8. **Privacy-aware student information handling**
9. **Manual fallback when AI is unavailable**
10. **Tested and deployable architecture**

---

## Final Project Pitch

> **An AI-powered university Lost & Found platform that uses Firebase Authentication for student identity, SQLite for application data, and Microsoft Foundry multimodal AI to analyze recovered-item photos and match them against lost-item descriptions and images, while using a controlled human verification process before an item is returned.**

