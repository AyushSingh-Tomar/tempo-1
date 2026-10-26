We have completed Phase A (Discovery) and Phase B (Synthesis). I want to resolve the open architectural questions and proceed with Phase C (Specification), followed by Phase D (Agent Architecture).

Use the following decisions as the approved MVP direction unless a genuine contradiction with the source requirements is identified.

1. Approved decisions

OQ-01 — Canonical schema
Use a versioned custom minimal canonical schema for the MVP. Design it to accommodate relevant Lloyd's V5.2 and ACORD mappings, but do not claim full compliance without field-level validation. Keep external standard mappings configurable and versioned.

OQ-02 — Authentication
Design an authentication abstraction compatible with enterprise OIDC/SSO. Use a safe local development authentication setup. Enforce server-side RBAC and authorization independently of the frontend. Do not implement homemade production authentication.

OQ-03 — Deployment
Use Docker Compose for local development and maintain a cloud-agnostic architecture. Use PostgreSQL for metadata and an object-storage abstraction for original files and derived artifacts. Defer the production cloud-provider decision until deployment requirements are known.

OQ-04 — LLM provider
Implement a provider abstraction and use Anthropic Claude as the initial adapter. Keep provider/model selection configurable. Do not couple business logic to a particular vendor. Enforce structured-output validation, bounded context, timeouts, retry limits, and cost controls.

OQ-05 — Financial tolerances
Support configurable absolute and percentage tolerances, rounding rules, and AND/OR evaluation. Existing example values are development fixtures only, not approved business defaults. Define explicit behavior for zero denominators, missing values, currency differences, and rounding. Do not silently accept financial differences.

OQ-06 — Treaty types
Start with a generic, versioned treaty model supporting clauses, typed parameters, effective dates, rule mappings, immutable states, and what-if scenarios. Validate the model against representative quota-share and excess-of-loss examples. Defer comprehensive treaty-specific calculation engines.

OQ-07 — Compliance
Implement foundational security, access control, audit logging, retention configuration, and secure file handling. Do not claim formal SOC 2, GDPR, or other regulatory compliance without a defined compliance scope and verification.

OQ-08 — Historical mapping reuse
Start with project-scoped historical mapping reuse. Require review and approval for uncertain or changed mappings. Defer organization-wide and global template reuse.

OQ-09 — PDF
Prioritize CSV, XLSX, XLS, JSON, JSONL, and other structured formats justified by the source requirements. Defer complex PDF understanding until the core ingestion and mapping pipeline is reliable. Document any PDF functionality that is explicitly required for the MVP.

OQ-10 — Processing
Use asynchronous batch processing for ingestion, standardization, and reconciliation. Persist job states, errors, progress, and run identifiers. Use deterministic execution and idempotency protections where appropriate.

OQ-11 — Multi-tenancy
Use a single-tenant MVP. Avoid unnecessary tenant infrastructure, but document the isolation changes needed before supporting multiple organizations.

OQ-12 — Internationalization
Use English for the initial UI. Support explicit currencies, ISO-compatible date handling, timezone-aware timestamps, and locale-independent financial calculations.

OQ-13 — Mobile
Use a desktop-first responsive UI. Prioritize complex mapping review, financial tables, reconciliation exceptions, treaty configuration, and audit workflows.

2. Technical architecture direction

Use a modular monolith initially, not premature microservices.

Preferred starting stack:

Python, FastAPI, Pydantic, SQLAlchemy, Alembic.

PostgreSQL for application metadata.

pandas or Polars and PyArrow where appropriate for tabular processing.

React and TypeScript for the frontend.

An object-storage abstraction, with local development storage and an S3-compatible implementation where needed.

Redis and a background task queue such as Celery if justified by job execution requirements.

Docker Compose, automated tests, and CI checks.

Do not add infrastructure solely because it is fashionable. Explain any proposed alternative against the project requirements.

3. Non-negotiable architectural principles

Deterministic processing first; AI reasoning only where it adds value.

Raw uploaded files are immutable.

Every derived artifact and reconciliation run is versioned and traceable.

Financial calculations, joins, aggregation, variance calculations, schema validation, and threshold evaluation are deterministic.

LLM output is an untrusted proposal until schema and business-rule validation succeeds.

AI cannot directly approve mappings, financial adjustments, treaty changes, or reconciliation outcomes.

Human review is mandatory where business policy or evidence requires it.

Preserve source lineage from findings back to original files and rows.

Use explicit contracts between ingestion, mapping, reconciliation, and treaty modules.

Make business rules configurable and auditable rather than embedding them in prompts.

4. Required next actions

First, read and cross-check:

docs/project-context/OPEN_QUESTIONS.md

docs/project-context/PROJECT_BRIEF.md

docs/project-context/REQUIREMENTS.md

docs/project-context/DOMAIN_MODEL.md

docs/project-context/IMPLEMENTATION_PLAN.md

docs/project-context/ARTIFACT_INDEX.md

All relevant original source specifications.

Then:

A. Update OPEN_QUESTIONS.md with the decisions above, their rationale, consequences, and any remaining questions. Distinguish approved architectural decisions from provisional business assumptions.

B. Resolve contradictions between source artifacts, synthesized documents, and these decisions. Do not silently discard a source requirement.

C. Produce an Architecture Decision Record (ADR) for each major architectural choice. Include context, decision, alternatives, consequences, and status.

D. Define the module boundaries, dependency rules, data flow, persistence boundaries, API boundaries, background job lifecycle, versioning, error handling, security boundaries, and audit model.

E. Identify the smallest end-to-end MVP that proves the core product: upload a file, inspect and profile it, propose mappings, review uncertain mappings, produce standardized output, reconcile against a subledger, and generate an evidence-backed report.

F. Define acceptance criteria and a synthetic golden dataset with expected outputs before implementation.

G. Identify which proposed features are essential for the MVP and which must be deferred.

5. Phase C deliverables

Create or update:

ARCHITECTURE.md

ADR/ decision records

MODULE_CONTRACTS.md

API_SPECIFICATION.md

DATA_MODEL.md, including schema and migration strategy

SECURITY_AND_AUDIT.md

TEST_STRATEGY.md

MVP_ACCEPTANCE_CRITERIA.md

MVP_SCOPE.md

An updated IMPLEMENTATION_PLAN.md

Avoid duplicating large sections of existing documents. Prefer references to authoritative sources and maintain traceability to original requirements.

6. Constraints on your work

Do not implement application code yet.

Do not generate additional agents until the module boundaries, contracts, responsibilities, and acceptance criteria are clear.

Do not assume that all 120+ functional requirements belong in the MVP.

If a decision depends on unknown business rules, label it explicitly and propose a safe default for development rather than inventing a production rule.

Before completing Phase C, perform a consistency review across all specifications. Report contradictions, unresolved blockers, architecture risks, and decisions that still require human input.

Start by summarizing the approved decisions and the remaining genuine blockers, then execute the Phase C specification work.