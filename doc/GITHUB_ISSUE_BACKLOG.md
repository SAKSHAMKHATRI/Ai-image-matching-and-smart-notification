# GitHub Issue Backlog for University AI Lost & Found

This document translates the audit findings and the master project plan into a GitHub-ready issue backlog. The issues are arranged to follow the required phase order and to avoid starting future phases before the required foundations are complete.

## Issue 1: Phase 0 — Repository and project bootstrap

Title: `Phase 0: Initialize repository structure and project tooling`

Body:

```md
## Summary
Set up the repository foundation required by the master architecture before implementing application features.

## Goal
Create the project skeleton for the required stack:
- React + Vite + TypeScript frontend
- Python FastAPI backend
- SQLite database foundation
- Firebase/Auth configuration placeholders
- Foundry AI configuration placeholders
- secret management and environment template

## Acceptance Criteria
- Repository contains frontend and backend folders with initial structure
- README explains setup and architecture
- `.gitignore` excludes `.env`, secrets, and generated artifacts
- `.env.example` exists and documents required keys
- Dependency manifests exist for frontend and backend
- Basic health-check app runs locally for both stacks
- Project structure matches the approved architecture

## Scope
- Create frontend scaffold
- Create backend scaffold
- Add dependency manifests
- Add environment template
- Add secret-handling guidance
- Add basic startup scripts

## Out of Scope
- Real business features
- Firebase login flow
- AI matching logic
- Claims processing

## Notes
This is the required Phase 0 foundation before Phase 1.
```

---

## Issue 2: Phase 1 — Firebase authentication foundation

Title: `Phase 1: Implement Firebase Authentication and protected backend access`

Body:

```md
## Summary
Add Firebase Authentication as the identity provider and enforce verified identity on backend routes.

## Goal
- Configure Firebase Auth integration
- Verify Firebase ID tokens in FastAPI
- Protect API routes with auth middleware
- Ensure identity comes from verified token rather than client-supplied fields

## Acceptance Criteria
- Backend can verify Firebase ID tokens
- Authenticated routes reject invalid or missing tokens
- User identity is derived from verified Firebase token
- Profile creation is linked to verified Firebase UID rather than trust-based client data
- Unauthorized access is blocked by backend authorization checks

## Scope
- Firebase config setup
- Auth middleware
- Token verification helper
- Protected route guards
- Basic auth error handling

## Out of Scope
- Full student profile editing
- Match logic
- Admin actions

## Notes
Authentication must be treated as a non-negotiable security boundary.
```

---

## Issue 3: Phase 2 — Student profile and identity data model

Title: `Phase 2: Add student profile model and profile management`

Body:

```md
## Summary
Capture required student profile information and keep application profile data separate from Firebase auth data.

## Goal
Implement the profile model required by the project specification:
- Full Name
- Roll Number
- Class / Section
- Course / Program
- Semester
- Phone Number
- University Email
- Campus

## Acceptance Criteria
- Student profile is stored in SQLite
- Firebase auth and app profile are conceptually separate
- Users can create and update their profile
- Student cannot edit another student profile
- Validation rules are enforced for university data

## Scope
- SQLite schema
- profile APIs
- frontend profile form
- authorization checks

## Out of Scope
- AI matching
- Claims workflow
- Admin moderation
```

---

## Issue 4: Phase 3 — SQLite foundation and schema

Title: `Phase 3: Build SQLite foundation for users, reports, matches, and claims`

Body:

```md
## Summary
Create the persistent data model foundation for the platform.

## Goal
Add the core database entities and relationships required by the master context:
- users
- lost_items
- found_items
- matches
- claims

## Acceptance Criteria
- `PRAGMA foreign_keys = ON;` is enabled
- Foreign key relationships are enforced
- Transactions are used for state-changing operations
- Schema supports status tracking and audit-friendly state transitions
- Database initialization is repeatable and safe

## Scope
- SQLite connection setup
- schema and migrations
- ORM or SQL model definitions
- basic repository/service access

## Out of Scope
- Matching logic
- AI integration
- UI work beyond validation
```

---

## Issue 5: Phase 4 — Lost item reporting workflow

Title: `Phase 4: Implement lost item reporting and management`

Body:

```md
## Summary
Allow students to report lost items with structured information and optional image upload.

## Goal
Support the required lost item flow:
- item name
- category
- color
- brand
- lost date
- approximate location
- description
- distinctive features
- optional image

## Acceptance Criteria
- Authenticated student can create a lost item report
- Lost item data validates correctly
- Reports are stored with proper status
- User can view their own reports
- Owner can update or delete only their own reports
- Image metadata can be stored without embedding binary data in SQLite

## Scope
- API routes for lost items
- database model
- frontend form
- optional image handling

## Out of Scope
- Found item matching
- AI analysis
- claim lifecycle
```

---

## Issue 6: Phase 5 — Image storage and safe upload pipeline

Title: `Phase 5: Add secure image storage for lost and found items`

Body:

```md
## Summary
Implement safe file upload and storage for images without storing binary content directly in SQLite.

## Goal
- Validate MIME types
- Enforce file size limits
- Use safe filenames
- Store references in SQLite
- Restrict storage access to authorized owners and backend services

## Acceptance Criteria
- Unsupported file types are rejected
- Oversized uploads are rejected
- Stored image references point to safe storage paths
- SQLite stores path metadata only, not raw binary data
- File security rules align with the master context

## Scope
- Storage service
- upload API
- validation rules
- frontend upload flow

## Out of Scope
- AI analysis
- match scoring
- claim verification
```

---

## Issue 7: Phase 6 — Found item workflow and analysis trigger

Title: `Phase 6: Implement found item reporting and AI analysis trigger`

Body:

```md
## Summary
Add the found-item workflow so a student can report an item they found and trigger analysis.

## Goal
Support the finder workflow:
- upload a found-item photo
- optional found location
- AI image analysis
- attribute extraction
- image embedding
- candidate retrieval
- match review

## Acceptance Criteria
- Finder can create a found item record
- Uploaded image is accepted and stored securely
- Found item analysis endpoint is available
- AI failure fallback does not block reporting
- Found items can be reviewed before matching

## Scope
- found item model and API
- image upload + metadata
- analysis trigger endpoint
- basic UI flow

## Out of Scope
- final match scoring model
- claims and ownership decisions
```

---

## Issue 8: Phase 7 — Microsoft Foundry integration

Title: `Phase 7: Integrate Microsoft Foundry for AI analysis`

Body:

```md
## Summary
Connect the backend to Microsoft Foundry and implement graceful AI failure handling.

## Goal
Add the AI service client and ensure the rest of the product remains usable when the AI system is unavailable.

## Acceptance Criteria
- Backend can call Microsoft Foundry APIs through a dedicated client
- Config lives in environment variables only
- Requests have timeout and retry fallback behavior
- AI outage does not block manual reporting or browsing
- Error conditions are handled transparently

## Scope
- Foundry client
- timeout/rate-limits
- fallback behavior
- monitoring/logging

## Out of Scope
- Matching scoring
- final ownership logic
```

---

## Issue 9: Phase 8 — OCR and text understanding

Title: `Phase 8: Implement OCR and privacy-aware text extraction`

Body:

```md
## Summary
Use OCR and text understanding for object attributes while minimizing exposure of sensitive data.

## Goal
- Extract relevant visible text from object images
- Minimize persistence of sensitive OCR data
- Keep raw OCR private and avoid exposure to other students
- Validate AI output schema

## Acceptance Criteria
- OCR is only used for relevant matching fields
- Sensitive OCR content is not exposed in results
- Derived signals are stored instead of raw sensitive data when possible
- Structured schema validation rejects invalid model output

## Scope
- OCR service
- schema validation
- privacy filtering
- integration with found item analysis

## Out of Scope
- final ownership approval
- admin workflows
```

---

## Issue 10: Phase 9 — Embeddings and multimodal matching preparation

Title: `Phase 9: Add multimodal embeddings for image and text comparison`

Body:

```md
## Summary
Prepare the data representation needed for candidate retrieval and similarity scoring.

## Goal
Generate and store compatible embeddings for:
- lost item description text
- lost item image if present
- found item image

## Acceptance Criteria
- Same embedding model/version is used consistently
- Vectors are normalized and serialized safely
- SQLite stores vector payloads in safe format
- Embedding pipeline is testable independently from the full app

## Scope
- embedding service
- vector serialization
- data model changes
- local testing

## Out of Scope
- direct ownership decisions
- UI presentation of match explanation
```

---

## Issue 11: Phase 10 — Candidate retrieval

Title: `Phase 10: Implement candidate retrieval and metadata filtering`

Body:

```md
## Summary
Build the retrieval step that narrows the search space before similarity scoring.

## Goal
Filter active lost reports using structured fields such as:
- status
- category
- campus
- location
- date window
- brand

## Acceptance Criteria
- System retrieves only active lost-item candidates
- Metadata filtering reduces the pool before vector similarity
- Candidate retrieval returns a manageable set for scoring
- Retrieval behavior is testable with fixtures

## Scope
- filtering logic
- candidate retrieval service
- API endpoint

## Out of Scope
- final ownership or claim approval
```

---

## Issue 12: Phase 11 — Match scoring and thresholds

Title: `Phase 11: Implement deterministic match scoring and thresholds`

Body:

```md
## Summary
Compute match confidence from image similarity, attribute similarity, location, and date compatibility.

## Goal
Implement the approved scoring model and threshold categories:
- Strong candidate >= 0.85
- Possible candidate 0.70–0.85
- Low confidence < 0.70

## Acceptance Criteria
- Final score is deterministic and explained by explicit components
- Score is never treated as proof of ownership
- Score thresholds are configurable
- Unit tests cover scoring logic and edge cases

## Scope
- scoring service
- threshold constants
- matching tests

## Out of Scope
- admin review automation
- human approval workflow
```

---

## Issue 13: Phase 12 — Match UI and match detail presentation

Title: `Phase 12: Build match results UI and detail screens`

Body:

```md
## Summary
Present candidate matches to the finder in a clear, mobile-friendly user interface.

## Goal
Display matches with safe data, explanations, and review paths.

## Acceptance Criteria
- UI shows candidate matches without exposing private owner data
- Match detail includes score and explanation reasons
- Mobile-friendly behavior is included
- Fallback for empty or low-confidence results exists

## Scope
- match list screen
- match detail components
- safe data presentation

## Out of Scope
- claim approval decisions
- return processing
```

---

## Issue 14: Phase 13 — Claims and verification workflow

Title: `Phase 13: Implement claim lifecycle and verification flow`

Body:

```md
## Summary
Allow a possible match to become a claim and then move through verification and decision states.

## Goal
Implement the lifecycle:
SUGGESTED → CLAIM_REQUESTED → OWNER_VERIFICATION → ADMIN_REVIEW → APPROVED / REJECTED → RETURNED

## Acceptance Criteria
- Duplicate active claims are prevented
- Owner can approve or reject
- Admin can intervene when needed
- Verification details remain private
- State transitions are transactional

## Scope
- claims data model
- API routes
- verification logic
- admin interventions

## Out of Scope
- return closure automation
- notifications
```

---

## Issue 15: Phase 14 — Return and closure workflow

Title: `Phase 14: Implement return approval and closure process`

Body:

```md
## Summary
Support the final return process once ownership is verified.

## Goal
Move the item into a completed return workflow and close the claim state cleanly.

## Acceptance Criteria
- Successful claim results in approved return status
- Item state changes are transactional
- Audit records are preserved
- Closed claims are not reopened without a valid admin action

## Scope
- return processing logic
- state transitions
- audit trail

## Out of Scope
- broad admin dashboard features
```

---

## Issue 16: Phase 15 — Admin dashboard and moderation

Title: `Phase 15: Build admin dashboard for moderation and review`

Body:

```md
## Summary
Provide admin-only access to review users, reports, matches, claims, and suspicious records.

## Goal
Allow admins to:
- review users
- review lost and found reports
- review claims
- review disputes
- suspend abusive users
- close stale or suspicious records

## Acceptance Criteria
- Admin endpoints enforce role-based authorization
- Students cannot access admin-only resources
- Admin dashboard is separate from student views
- Suspicious or fraudulent records can be moderated

## Scope
- admin APIs
- admin UI
- role checks

## Out of Scope
- general user experience polish
```

---

## Issue 17: Phase 16 — Manual search and fallback workflow

Title: `Phase 16: Add manual search and fallback behavior for non-AI workflows`

Body:

```md
## Summary
Ensure the platform remains useful when AI is unavailable or underperforming.

## Goal
Support manual browsing and filtering even when the AI system is down.

## Acceptance Criteria
- Reporting and browsing continue without AI
- Manual search allows students to find relevant lost items without AI assistance
- Fallback UX is understandable and accessible
- AI failures are logged without breaking normal workflows

## Scope
- search/filter logic
- fallback UI
- error handling

## Out of Scope
- full AI system improvement
```

---

## Issue 18: Phase 17 — Notifications

Title: `Phase 17: Add notifications for claims, matches, and status updates`

Body:

```md
## Summary
Notify users about relevant status changes without exposing private information.

## Goal
Add a notification system for:
- possible matches
- claim updates
- return progress
- admin actions or moderation notices

## Acceptance Criteria
- Notifications are tied to relevant user concerns only
- Sensitive information is not exposed in notifications
- Notification delivery is auditable
- System supports status-based updates

## Scope
- notification model
- API/service
- UI integration

## Out of Scope
- production email/SMS providers
```

---

## Issue 19: Phase 18 — Security and privacy hardening

Title: `Phase 18: Harden security, privacy, and data minimization`

Body:

```md
## Summary
Apply the required security protections for identity, file handling, AI calls, and privacy-sensitive data.

## Goal
Enforce:
- Firebase token verification
- RBAC/authorization checks
- file validation and secure storage
- AI request safety
- data minimization and private OCR handling

## Acceptance Criteria
- Backend rejects unauthorized access
- File uploads are validated before storage
- Sensitive student fields are hidden appropriately
- AI requests minimize personal data exposure
- Audit-safe logs are used for security signals

## Scope
- auth hardening
- file security
- privacy filters
- logging and monitoring

## Out of Scope
- feature expansion beyond security
```

---

## Issue 20: Phase 19 — Testing and validation

Title: `Phase 19: Add automated testing for business logic and integration flows`

Body:

```md
## Summary
Establish the minimum test suite required by the project standards.

## Goal
Add unit, integration, and end-to-end tests for key workflows:
- lost item report
- found item report
- claim and verification flow
- AI failure flow

## Acceptance Criteria
- Unit tests cover validation, scoring, and authorization helpers
- Integration tests cover API + database flows
- End-to-end tests cover the required journeys
- Regression coverage exists for core logic

## Scope
- pytest setup
- frontend test setup
- validation tests
- workflow tests

## Out of Scope
- production deployment
```

---

## Issue 21: Phase 20 — AI evaluation and benchmarking

Title: `Phase 20: Add AI evaluation framework and labelled test dataset`

Body:

```md
## Summary
Evaluate the matching quality with labelled examples rather than visual demo assumptions.

## Goal
Create labelled data for:
- true match vs non-match
- difficult cases
- multiple candidates
- poor photo conditions
- missing lost image
- misleading OCR

## Acceptance Criteria
- Benchmark metrics are collected for precision, recall, Top-1 accuracy, Top-5 accuracy, false positive rate, and false negative rate
- Review process is defined for model improvements
- Results feed future calibration decisions

## Scope
- evaluation dataset
- scoring metrics
- calibration planning

## Out of Scope
- permanent production deployment
```

---

## Issue 22: Phase 21 — Performance tuning

Title: `Phase 21: Optimize performance for matching, storage, and UI responsiveness`

Body:

```md
## Summary
Improve performance once the system is functional and validated.

## Goal
Ensure the platform remains responsive under realistic student usage and candidate retrieval loads.

## Acceptance Criteria
- Candidate retrieval is efficient enough for the chosen MVP scale
- Storage and API requests remain stable
- UI remains responsive on mobile devices
- Performance regressions are measured

## Scope
- API optimization
- database indexing
- UI responsiveness

## Out of Scope
- deployment or monitoring operations
```

---

## Issue 23: Phase 22 — UI/UX polish and mobile-first improvements

Title: `Phase 22: Polish the mobile-first experience and user flows`

Body:

```md
## Summary
Improve the usability and accessibility of the platform across mobile and desktop screens.

## Goal
Ensure the finder can use the production flow on a phone camera, upload, and review matches with minimal friction.

## Acceptance Criteria
- Screens are mobile-first and accessible
- Forms are optimized for camera upload workflows
- Loading, error, and empty states exist
- Core journeys are easy to understand

## Scope
- UI polish
- mobile UX improvements
- accessibility pass

## Out of Scope
- deployment and observability
```

---

## Issue 24: Phase 23 — Deployment readiness

Title: `Phase 23: Prepare deployment configuration for staging and production`

Body:

```md
## Summary
Prepare the application for deployment after all core requirements are implemented and validated.

## Goal
Add configuration and deployment workflow to support a production-ready environment.

## Acceptance Criteria
- Deployment configuration is documented
- Environment variables are defined for production use
- App can run in a controlled staging setup
- Deployment plan covers critical security and data handling concerns

## Scope
- deployment docs
- environment configuration
- hosting guidance

## Out of Scope
- actual production rollout without approval
```

---

## Issue 25: Phase 24 — Monitoring and operations

Title: `Phase 24: Add monitoring, logging, and operational observability`

Body:

```md
## Summary
Set up monitoring for system health, AI integration failures, and operational issues.

## Goal
Add the operational layer needed for a production system.

## Acceptance Criteria
- Logs capture critical workflow events
- AI failures are observable
- Database and API health are tracked
- Monitoring includes security-relevant events

## Scope
- observability configs
- service health checks
- alerting guidance

## Out of Scope
- broad analytics features
```

---

## Issue 26: Phase 25 — Documentation and viva readiness

Title: `Phase 25: Prepare final documentation, demo, and viva assets`

Body:

```md
## Summary
Prepare the project for final documentation review and viva presentation.

## Goal
Package the project with architecture, implementation notes, and demo-ready outputs.

## Acceptance Criteria
- Final architecture and plan are documented
- Implementation summary and validation report are available
- Demo flow is clear for viva presentation
- Risks and limitations are documented

## Scope
- final docs
- viva/demo prep
- known issue summary

## Out of Scope
- new feature development
```

---

## Recommended GitHub issue ordering

The issues should be created in this order:

1. Phase 0 — Repository and project bootstrap
2. Phase 1 — Firebase Authentication
3. Phase 2 — Student profile
4. Phase 3 — SQLite foundation
5. Phase 4 — Lost item reporting
6. Phase 5 — Image storage
7. Phase 6 — Found item workflow
8. Phase 7 — Microsoft Foundry integration
9. Phase 8 — OCR and text understanding
10. Phase 9 — Embeddings
11. Phase 10 — Candidate retrieval
12. Phase 11 — Match scoring
13. Phase 12 — Match UI
14. Phase 13 — Claims and verification
15. Phase 14 — Return and closure
16. Phase 15 — Admin dashboard
17. Phase 16 — Manual fallback
18. Phase 17 — Notifications
19. Phase 18 — Security and privacy hardening
20. Phase 19 — Testing
21. Phase 20 — AI evaluation
22. Phase 21 — Performance
23. Phase 22 — UI/UX polish
24. Phase 23 — Deployment
25. Phase 24 — Monitoring
26. Phase 25 — Documentation and viva

## GitHub creation status

The repository is currently not authenticated from this environment, so these issues could not be created directly on GitHub from the terminal. The issue content is ready for upload once GitHub authentication is available.
