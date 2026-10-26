# Open Questions — Resolution Status
## Bordereaux Intelligence Platform

> **Version:** 2.0
> **Date:** 2026-10-09
> **Status:** Architectural decisions approved, proceeding to specification

---

## Approved Architectural Decisions

### OQ-01: Canonical Schema Definition ✅ RESOLVED

**Decision:** Use a versioned custom minimal canonical schema for the MVP. Design it to accommodate relevant Lloyd's V5.2 and ACORD mappings, but do not claim full compliance without field-level validation. Keep external standard mappings configurable and versioned.

**Rationale:** Allows rapid MVP development while maintaining path to standards compliance. Versioning enables schema evolution without breaking existing data.

**Consequences:**
- Must define minimal field set sufficient for reconciliation use case
- Schema version tracked with every Claims Mapping artifact
- Migration strategy required for schema upgrades
- External standard mapping is configuration, not hardcoded

**Remaining Work:** Define concrete field list in DATA_MODEL.md

---

### OQ-02: Authentication Strategy ✅ RESOLVED

**Decision:** Design an authentication abstraction compatible with enterprise OIDC/SSO. Use a safe local development authentication setup. Enforce server-side RBAC and authorization independently of the frontend. Do not implement homemade production authentication.

**Rationale:** Separates authentication mechanism from authorization logic. Enables enterprise integration without MVP complexity.

**Consequences:**
- Authentication abstraction layer in architecture
- Local dev uses simple token-based auth (not for production)
- RBAC enforced at API layer, not just UI
- Permission checks independent of auth provider

**Remaining Work:** Define RBAC roles and permissions in SECURITY_AND_AUDIT.md

---

### OQ-03: Deployment Target ✅ RESOLVED

**Decision:** Use Docker Compose for local development and maintain a cloud-agnostic architecture. Use PostgreSQL for metadata and an object-storage abstraction for original files and derived artifacts. Defer the production cloud-provider decision until deployment requirements are known.

**Rationale:** Avoids premature vendor lock-in. Docker Compose enables consistent local development.

**Consequences:**
- Storage abstraction with local filesystem and S3-compatible implementations
- No cloud-specific services in core business logic
- Infrastructure as code for local dev environment
- Production deployment guide deferred

**Remaining Work:** Define storage abstraction interface in MODULE_CONTRACTS.md

---

### OQ-04: LLM Provider Selection ✅ RESOLVED

**Decision:** Implement a provider abstraction and use Anthropic Claude as the initial adapter. Keep provider/model selection configurable. Do not couple business logic to a particular vendor. Enforce structured-output validation, bounded context, timeouts, retry limits, and cost controls.

**Rationale:** Claude supports structured outputs. Abstraction enables future provider changes without business logic rewrites.

**Consequences:**
- LLM service interface defined independent of provider
- Claude adapter as reference implementation
- Structured output schemas defined in code (Pydantic)
- Token budgets, timeouts, and retry policies configurable
- Cost tracking per operation

**Remaining Work:** Define LLM service interface in MODULE_CONTRACTS.md

---

### OQ-05: Financial Tolerance Thresholds ✅ RESOLVED

**Decision:** Support configurable absolute and percentage tolerances, rounding rules, and AND/OR evaluation. Existing example values are development fixtures only, not approved business defaults. Define explicit behavior for zero denominators, missing values, currency differences, and rounding. Do not silently accept financial differences.

**Rationale:** Financial tolerance is business policy, not technical default. Explicit handling prevents silent data quality issues.

**Consequences:**
- Tolerance configuration per reconciliation, not global
- Development fixtures use safe conservative values
- Edge cases (zero denominator, null values) explicitly handled
- Currency mismatch blocks reconciliation or requires explicit rule
- Audit trail for tolerance decisions

**Development Fixtures (NOT production defaults):**
- Absolute: $100
- Percentage: 0.1%
- Evaluation: OR
- Precision: 2 decimal places

**Remaining Work:** Document tolerance behavior in reconciliation feature spec

---

### OQ-06: Treaty Types for MVP ✅ RESOLVED

**Decision:** Start with a generic, versioned treaty model supporting clauses, typed parameters, effective dates, rule mappings, immutable states, and what-if scenarios. Validate the model against representative quota-share and excess-of-loss examples. Defer comprehensive treaty-specific calculation engines.

**Rationale:** Generic model proves the versioning and what-if architecture. Type-specific engines are optimization, not MVP.

**Consequences:**
- Treaty model does not enforce type-specific validation initially
- Clause parameters are typed but interpretation is configuration-driven
- What-if comparison works regardless of treaty type
- Quota-share and excess-of-loss serve as validation examples

**Remaining Work:** Define treaty model validation criteria

---

### OQ-07: Regulatory Requirements ✅ RESOLVED

**Decision:** Implement foundational security, access control, audit logging, retention configuration, and secure file handling. Do not claim formal SOC 2, GDPR, or other regulatory compliance without a defined compliance scope and verification.

**Rationale:** Foundation enables future compliance. Premature compliance claims create legal risk.

**Consequences:**
- Audit events for all state changes
- Configurable retention policies
- No PII in logs without explicit configuration
- Compliance certification is future work, not MVP claim

**Remaining Work:** Define audit event catalog in SECURITY_AND_AUDIT.md

---

### OQ-08: Historical Mapping Reuse ✅ RESOLVED — SUPERSEDED (feature removed in iteration 1.1)

**Decision:** Start with project-scoped historical mapping reuse. Require review and approval for uncertain or changed mappings. Defer organization-wide and global template reuse.

**Rationale:** Project scope limits blast radius of mapping errors. Cross-project reuse adds complexity without MVP value.

**Consequences:**
- Mappings stored per project
- Historical match boosts confidence score, doesn't auto-approve
- Changed source structure triggers re-review
- Organization-wide templates are future feature

**Remaining Work:** None for MVP

---

### OQ-09: PDF Support ✅ RESOLVED

**Decision:** Prioritize CSV, XLSX, XLS, JSON, JSONL, and other structured formats justified by the source requirements. Defer complex PDF understanding until the core ingestion and mapping pipeline is reliable. Document any PDF functionality that is explicitly required for the MVP.

**Rationale:** PDF parsing is high-effort, low-reliability. Structured formats prove the pipeline.

**Consequences:**
- PDF adapter not in MVP scope
- FR-ING-07 deferred to post-MVP
- Users provide structured exports for MVP
- PDF requirement documented if discovered

**MVP File Formats:** CSV, TSV, XLSX, XLS, JSON, JSONL, Parquet

---

### OQ-10: Real-time vs Batch Processing ✅ RESOLVED

**Decision:** Use asynchronous batch processing for ingestion, standardization, and reconciliation. Persist job states, errors, progress, and run identifiers. Use deterministic execution and idempotency protections where appropriate.

**Rationale:** Batch processing is sufficient for MVP use cases. Async enables large file handling without blocking.

**Consequences:**
- Job queue for long-running operations
- Job status API for progress tracking
- Idempotency via fingerprinting
- No streaming/incremental reconciliation in MVP

**Remaining Work:** Define job lifecycle in ARCHITECTURE.md

---

### OQ-11: Multi-tenancy Model ✅ RESOLVED

**Decision:** Use a single-tenant MVP. Avoid unnecessary tenant infrastructure, but document the isolation changes needed before supporting multiple organizations.

**Rationale:** Multi-tenancy adds complexity without MVP value. Documentation enables future migration.

**Consequences:**
- No tenant_id in core models
- Single database, single storage namespace
- Multi-tenant migration path documented
- Isolation requirements captured for future

**Remaining Work:** Document multi-tenant migration considerations

---

### OQ-12: Internationalization ✅ RESOLVED

**Decision:** Use English for the initial UI. Support explicit currencies, ISO-compatible date handling, timezone-aware timestamps, and locale-independent financial calculations.

**Rationale:** English-first reduces MVP scope. Data handling must be locale-independent for financial accuracy.

**Consequences:**
- UI strings in English only
- Dates stored as UTC, displayed in user timezone
- Currency stored with explicit code, not locale-derived
- Number formatting explicit, not locale-dependent

**Remaining Work:** None for MVP

---

### OQ-13: Mobile/Tablet Support ✅ RESOLVED

**Decision:** Use a desktop-first responsive UI. Prioritize complex mapping review, financial tables, reconciliation exceptions, treaty configuration, and audit workflows.

**Rationale:** Primary use case is desktop analyst workflow. Responsive design enables tablet viewing without mobile optimization.

**Consequences:**
- Desktop viewport is primary design target
- Responsive breakpoints for tablet viewing
- No mobile-specific features
- Complex tables may require horizontal scroll on small screens

**Remaining Work:** None for MVP

---

## Contradictions Resolved

### C-01: LLM Model Naming ✅ RESOLVED

**Issue:** A04 §46 references "GPT-6 Luna/Sol/Astra" (fictional model names).

**Resolution:** Treat as placeholder names. Use Claude as initial implementation per OQ-04 decision. Model routing logic applies to actual available models.

---

### C-02: Confidence Scoring Weights ✅ RESOLVED

**Issue:** Two weight distributions mentioned (A02 vs A03).

**Resolution:** Use A02 weights as defaults. Weights are configurable per OQ-05 principle of configurable business rules.

**Default Weights:**
- Semantic: 20%
- Value: 20%
- Context: 15%
- Layout: 5%
- Relationship: 20%
- Historical: 10%
- AI: 10%

---

### C-03: File Size Limits ✅ RESOLVED

**Issue:** No explicit file size limits.

**Resolution:** Define development limits, document as configurable:
- Maximum single file: 500MB
- Maximum rows per dataset: 5M
- Maximum columns: 500

Production limits are deployment configuration.

---

## Information Gaps — Status

### G-01: Sample Data ⚠️ DEFERRED

**Status:** No sample data provided. Will generate synthetic test data during implementation.

**Mitigation:** Define golden dataset schema in TEST_STRATEGY.md. Generate synthetic data as part of Phase 1.

---

### G-02: Golden Dataset ⚠️ DEFERRED

**Status:** No golden dataset provided.

**Mitigation:** Define expected structure and generate synthetic golden dataset. Document in MVP_ACCEPTANCE_CRITERIA.md.

---

### G-03: UI Mockups ⚠️ DEFERRED

**Status:** No mockups provided.

**Mitigation:** Use A07 (Databricks UI reference) patterns. Create wireframes during Phase 8 if needed.

---

### G-04: Error Message Catalog ⚠️ DEFERRED

**Status:** No error catalog defined.

**Mitigation:** Define error code structure in ARCHITECTURE.md. Catalog evolves during implementation.

---

## Remaining Genuine Blockers

**None.** All critical architectural questions are resolved. Remaining gaps (sample data, mockups) can be addressed during implementation.

---

## Decision Authority

| Decision Type | Authority |
|---------------|-----------|
| Architectural decisions (OQ-01 through OQ-13) | Approved per ANSWERING_OPEN_QUESTION.md |
| Business rule defaults | Development fixtures only, require business confirmation |
| MVP scope | Defined in MVP_SCOPE.md |
| Feature prioritization | Per IMPLEMENTATION_PLAN.md phases |
