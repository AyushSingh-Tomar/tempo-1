# Implementation Task: Build the First End-to-End Bordereaux Processing Accelerator

You are the lead engineer implementing the first working iteration of the **Bordereaux Processing Accelerator** within our existing ReInsurance Project.

Your task is to implement the workflow represented by the provided **Bordereaux Processing Accelerator flowchart** in the current codebase. This must be a functioning, end-to-end feature integrated with the existing application—not merely a UI mockup, static flowchart, or isolated prototype.

## 1. Start by understanding the existing project

Before writing or modifying code, inspect the repository and understand its current architecture.

Read and follow the project documentation, particularly:

- `README.md`
- `SOLUTION_DESIGN.md`
- `databricks_ui_ux_architecture_reference.md`
- `Module_1_ingestion_and_naming.md`
- `Checks_to_perform(1).md`
- `Module_2_Reconciliation_Implement.md`
- `Treaty Management Section_Implement.md`

Inspect the existing frontend, backend, database models, API routes, service layer, file-storage implementation, authentication/authorization, agent configuration, and test suite.

Use the existing repository files as the source of truth for the implementation. Some specifications describe future capabilities, so distinguish between existing functionality and planned functionality.

### Implementation rules

1. Reuse the existing architecture, libraries, components, design system, and conventions wherever possible.
2. Do not replace working modules or rewrite the application architecture to implement this feature.
3. Do not create duplicate services, APIs, database models, or state-management mechanisms if suitable equivalents already exist.
4. Integrate with Module 1 for ingestion, standardization, and mapping wherever its current capabilities support the required workflow.
5. Keep the implementation modular, testable, and maintainable.
6. If a required capability does not exist, implement the smallest appropriate extension in the existing architecture.
7. Do not assume a technology stack or invent APIs before inspecting the codebase.
8. If a specification conflicts with working project behavior, identify the conflict and follow the established architecture unless a change is essential.

Once you understand the repository, begin implementing the feature. Do not stop after producing an analysis or implementation plan.

## 2. Objective of the first iteration

Build a usable workflow that takes a user's Excel or CSV file through the following lifecycle:

**Upload → Validate → Clean and Standardize → Review Changes → Confirm → Map Columns → Review Mappings → Enter Treaty Figures → Validate Figures → Apply Financial Rules → Review Discrepancies → Override or Resolve → Generate Reports → Download.**

The workflow must preserve user decisions and provide a clear audit trail.

For this iteration, prioritize the core, deterministic processing path. Optional learning hints and preference capture must never be prerequisites for successful processing.

## 3. Implement the workflow in this exact sequence

### Step 1 — Start and upload

Provide a clear entry point for starting a new processing run.

The user must be able to upload an Excel (`.xlsx`) or CSV (`.csv`) file.

Requirements:

- Validate the file extension and actual file content.
- Enforce configured upload-size limits.
- Reject unsupported or malformed files with understandable error messages.
- For Excel workbooks, support selecting a worksheet when multiple worksheets exist.
- Display the filename, file size, and relevant ingestion status.
- Assign a unique processing-run identifier.
- Preserve the original uploaded file without modifying or overwriting it.
- Record source metadata and file checksum where consistent with the existing architecture.

The workflow must not continue when the uploaded file is invalid.

**Invalid file behavior:** Show a clear error explaining that an Excel or CSV file is required, and allow the user to upload another file.

### Step 2 — Clean and standardize the file

After successful validation, invoke the appropriate existing ingestion and standardization services.

The system should inspect the file and apply safe, deterministic cleaning operations according to the project's existing BRD and standardization rules.

Depending on the input structure and configured rules, these may include:

- Detecting headers and handling supported multi-row header structures.
- Normalizing column names and whitespace.
- Handling empty rows and columns according to explicit rules.
- Normalizing null values and common formatting inconsistencies.
- Parsing dates and numeric values safely.
- Detecting duplicate records without silently deleting potentially legitimate transactions.
- Detecting malformed values and structural anomalies.
- Applying configured business validation rules.

Do not invent transformations that could change financial meaning. In particular, preserve signs, precision, identifiers, currency distinctions, and meaningful source values.

Produce a structured cleaning result containing:

- Original row and column counts.
- Resulting row and column counts.
- Changes performed.
- Warnings and validation findings.
- Records or values requiring attention.
- Source-to-output lineage.

Retain the raw input as an immutable source artifact. Cleaning should create a derived artifact rather than replace the original.

### Step 3 — Present the before/after cleaning summary

Display a review screen showing what the system changed.

Include:

- Before/after row and column counts.
- A preview of the original data.
- A preview of the cleaned data.
- A list of transformations performed.
- Warnings, rejected values, and other relevant findings.
- A clear explanation of any nontrivial change.

Provide two actions:

**A. Acknowledge and continue**

Persist the user's acknowledgement and proceed to column mapping.

**B. Reject and rerun**

Return to the cleaning review stage and allow the user to request another processing attempt.

A rerun must not create an uncontrolled loop or overwrite an earlier artifact. Preserve the previous attempt, and allow only explicitly supported cleaning options or corrections to change the next run.

Do not represent a user acknowledgement as proof that all data is correct. It records that the user reviewed the displayed result.

### Step 4 — Map columns to the data dictionary

After acknowledgement, map source columns to the project's existing canonical data dictionary and mapping model.

Reuse Module 1's mapping engine, schema definitions, candidate generation, and confidence-scoring functionality where available.

Requirements:

- Generate proposed source-to-target mappings.
- Use header names, actual values, data types, contextual relationships, and approved historical mappings where supported.
- Assign confidence scores and retain the supporting evidence.
- Identify unmapped fields, ambiguous candidates, and incompatible data types.
- Allow the user to inspect, correct, accept, or reject mappings.
- Preserve the mapping version and reviewer decisions.
- Support the existing canonical claims-mapping conventions rather than creating a separate competing schema.

AI may assist with semantic ambiguity, but Python must validate types, required fields, and mapping integrity.

Never silently accept an ambiguous financial mapping merely because its column name looks similar to a target field.

#### Optional capability: inline hints from past learning

Provide a clearly optional integration point for approved historical mappings or reusable processing profiles.

If this functionality already exists, reuse it. Otherwise, implement it only as a lightweight, isolated extension if it fits the current architecture.

Historical hints may recommend a mapping, but must not silently overwrite current user decisions or authoritative mapping rules.

### Step 5 — Display the mapping review panel

Show a mapping-review interface that allows the user to inspect the proposed mappings before continuing.

The interface should display:

- Source column.
- Proposed canonical field.
- Confidence.
- Sample values and relevant profile statistics.
- Mapping evidence and warnings.
- Alternative candidates.
- User-approved or manually corrected mapping.

Provide a pass-through notice that clearly summarizes the mapping configuration that will be used downstream.

The user must explicitly confirm the mappings before the workflow advances.

**If the user declines:** Return to the mapping review panel, retain the current edits, and allow adjustments.

**If the user confirms:** Persist the confirmed mapping version and proceed to treaty figures.

The application must not fabricate a mapping or mark a mapping as confirmed simply to allow the workflow to continue.

### Step 6 — Request and collect treaty figures

After mapping confirmation, present a form for the treaty figures required by the current processing rules.

Inspect the existing specifications and implementation to determine which fields are already defined. Reuse those definitions rather than hardcoding an unrelated set of fields.

The form should support the required financial parameters, such as applicable treaty limits, retention, attachment points, rates, shares, or other configured figures.

Requirements:

- Use explicit field labels and descriptions.
- Validate numeric types and permitted ranges.
- Support currency and percentage fields where appropriate.
- Make required versus optional fields explicit.
- Preserve decimal precision.
- Display field-level validation errors.
- Prevent submission when required figures are missing or invalid.
- Persist the submitted figures against the processing run, including the configuration version where applicable.

Do not assume that every treaty uses the same parameters. Use existing configuration or a schema-driven form where feasible.

### Step 7 — Validate treaty figures

Validate the submitted figures using deterministic Python/business-rule validation.

Check applicable conditions such as:

- Required values are present.
- Numeric values are valid and finite.
- Dates and effective periods are valid where relevant.
- Currency and percentage values use the expected representation.
- Cross-field constraints are satisfied when defined by the business rules.
- Dependent treaty or financial rules can be evaluated safely.

If validation fails, display the specific errors and return the user to the treaty-figure form.

Do not continue to financial-rule execution with invalid inputs.

### Step 8 — Apply money-column rules and detect discrepancies

Once the treaty figures are valid, apply the existing project's financial-column rules and deterministic validation checks.

Use the existing rules in `Checks_to_perform(1).md` and the applicable Module 1 specifications.

The implementation should support applicable checks for:

- Financial-field type and value validity.
- Expected relationships between gross, net, commission, premium, or other relevant fields.
- Sign conventions and permitted calculations.
- Missing or invalid monetary values.
- Duplicate or inconsistent records.
- Relevant cross-field business constraints.
- Discrepancies against configured treaty figures or expected calculations.
- Other explicitly configured financial checks.

Do not assume a universal financial formula. Resolve the intended rule from the existing project specifications and configuration.

**Important:** All calculations, aggregations, tolerance checks, and numerical validations must be deterministic. Use AI only where semantic interpretation is genuinely necessary, not to perform financial arithmetic.

Every detected discrepancy must include, as applicable:

- A unique discrepancy identifier.
- The affected row or business entity.
- The field or rule involved.
- Expected and observed values.
- The variance or difference.
- The rule that detected it.
- Severity and status.
- Evidence and source lineage.

Distinguish between a confirmed data error, a potentially valid business difference, a warning, and an unresolved issue wherever the existing rule model supports these classifications.

### Step 9 — Display the results dashboard

Build a results dashboard containing the processed data, discrepancy summary, and review actions.

Include:

- Processing-run status.
- Total records processed.
- Counts of valid records, warnings, and discrepancies.
- Summary of the financial checks performed.
- A detailed discrepancies table.
- Relevant amounts, differences, and rule explanations.
- Search, sorting, and filtering appropriate to the existing UI.
- A way to inspect the affected source record and its lineage.

Use the existing design system and data-grid components where available.

The dashboard must be usable for both successful runs and runs containing discrepancies. A run with exceptions should not be falsely marked as fully reconciled.

### Step 10 — Allow reasoned discrepancy overrides

If discrepancies require review, let the user inspect each applicable discrepancy and record an override where permitted.

An override must require:

- The selected discrepancy.
- A reason for the override.
- An optional supporting comment or evidence reference where supported.
- The identity of the acting user, obtained through the existing authentication context.
- A timestamp and link to the relevant processing run.

Requirements:

- Validate the override on the backend.
- Respect existing permissions and authorization conventions.
- Persist the override as an audit event.
- Preserve the original discrepancy and its detected values.
- Show both the original finding and the user's decision.
- Update the dashboard after a successful override.
- Keep overridden findings distinguishable from automatically resolved findings.

An override is a human disposition, not a deletion of evidence. It must not modify the source file or silently change the underlying financial rules.

If further changes are needed, allow the user to rerun the relevant processing stage through the supported workflow while preserving prior run history.

If discrepancies remain unresolved, the user must be able to inspect them rather than being forced to approve them.

### Step 11 — Generate the processed file and audit report

When the user reaches the report-generation stage, generate downloadable artifacts using the actual results of the processing run.

At minimum, provide:

**Processed file**

- The standardized dataset in the appropriate supported downloadable format.
- Preserved identifiers and financial values.
- Clear column names.
- No unintended loss of records or source information.
- Appropriate lineage or a linked lineage artifact.

**Audit report**

- Processing-run identifier and timestamps.
- Source filename and version/checksum where supported.
- Cleaning operations and validation findings.
- Mapping configuration/version and relevant review decisions.
- Treaty figures or configuration version used.
- Financial checks performed and their results.
- Discrepancy summary and details.
- Human overrides, reasons, and comments.
- Final processing status.

Generate the audit report in a format supported by the existing application. If PDF or Excel report generation already exists, reuse it; otherwise, implement a practical format such as CSV or JSON for the audit details and the appropriate standardized data export.

Do not generate a success report containing fabricated results or mark failed report-generation jobs as successful.

### Step 12 — Download and finish

Provide an explicit download action for the processed file and the audit report.

Requirements:

- Generate downloads from persisted artifacts associated with the correct run.
- Ensure a user cannot download another user's or unauthorized project's files.
- Handle missing, expired, or failed artifacts with meaningful errors.
- Keep the run summary and audit history accessible after completion.
- Display a clear completion state once the required artifacts have actually been generated.

#### Optional capability: capture user choices for future hints

Where appropriate, capture approved user preferences or mapping choices as feedback for future processing runs.

This must be separate from the core workflow and must not automatically alter business rules.

Only persist the feedback through an explicit, auditable mechanism. Do not treat an override as permission to update global rules or train a model automatically.

## 4. State management and workflow integrity

Implement this as a real, stateful workflow, not a collection of unrelated pages.

Use the existing workflow orchestration and persistence mechanisms if available. Otherwise, introduce a small explicit state model appropriate to the current architecture.

The workflow should represent states corresponding to:

1. `STARTED`
2. `FILE_UPLOADED`
3. `FILE_VALIDATED`
4. `CLEANING_COMPLETED`
5. `CLEANING_REVIEW_PENDING`
6. `MAPPING_REVIEW_PENDING`
7. `MAPPING_CONFIRMED`
8. `TREATY_FIGURES_PENDING`
9. `TREATY_FIGURES_VALIDATED`
10. `FINANCIAL_CHECKS_COMPLETED`
11. `DISCREPANCY_REVIEW_PENDING`
12. `REPORT_GENERATION_PENDING`
13. `COMPLETED`
14. `FAILED`

Adapt the exact names to existing project conventions.

Not every run must pass through every review state if the current business design explicitly supports an equivalent shortcut, but no mandatory human confirmation may be bypassed.

Enforce legal state transitions on the backend. Do not rely solely on disabled frontend buttons to prevent invalid transitions.

Persist enough state to allow the user to resume a processing run without losing confirmed mappings, treaty figures, or review decisions.

Prevent accidental duplicate execution, stale updates, and cross-run data leakage.

## 5. Architecture, data integrity, and security

Follow these rules throughout the implementation:

- Preserve raw uploaded files as immutable artifacts.
- Keep derived data separate from original data.
- Use backend validation for every important transition.
- Preserve source-row identifiers and lineage wherever transformations occur.
- Keep user decisions, mapping versions, rule versions, and run identifiers connected.
- Keep business logic out of UI components.
- Use typed request/response models and the project's existing validation conventions.
- Use the existing database and migration approach.
- Use transactions where multiple persisted changes must remain consistent.
- Apply safe file handling and appropriate access controls.
- Do not execute user-provided code or arbitrary expressions.
- Do not hardcode secrets, user identities, or environment-specific paths.
- Do not silently suppress exceptions.
- Do not use fake data in production execution paths.
- Do not allow an LLM or agent to directly mutate financial state outside validated backend operations.

Keep the implementation modular across the existing UI, API, service, persistence, and processing layers.

## 6. UI and UX expectations

Use the supplied flowchart as the workflow reference, but implement it as a practical application experience.

Follow `databricks_ui_ux_architecture_reference.md` and the existing solution design.

The UI should provide:

- A clear step-by-step workflow.
- A visible indication of the current stage.
- Clear primary and secondary actions.
- Persistent project and processing-run context.
- Meaningful loading, empty, error, and completion states.
- Review screens that retain user edits.
- Tables for financial data and discrepancies.
- Contextual explanations of mappings and business rules.
- Accessible labels, keyboard navigation, and visible focus states.
- Responsive layouts consistent with the existing application.

Do not build the entire application as one enormous page or replace the existing application shell. Reuse established navigation and layout components.

The optional steps in the flowchart should remain secondary and must not obstruct the primary processing path.

## 7. Testing requirements

Add automated tests using the repository's existing test framework.

At minimum, cover:

### File handling
- Valid CSV upload.
- Valid XLSX upload.
- Unsupported file rejection.
- Malformed file rejection.
- Multi-sheet workbook handling where supported.
- Empty or structurally invalid file handling.

### Cleaning and review
- Deterministic cleaning behavior.
- Before/after summary accuracy.
- Raw file immutability.
- Acknowledgement and rerun transitions.
- Preservation of earlier processing attempts.

### Mapping
- Candidate mapping generation.
- Mapping validation.
- Missing required mappings.
- User corrections and confirmation.
- Persistence of mapping versions and review decisions.

### Treaty figures and financial checks
- Valid figure submission.
- Missing and invalid values.
- Boundary conditions and cross-field validation.
- Financial-rule execution.
- Precision and sign handling.
- Detection of expected discrepancies.

### Human review
- Valid override with a reason.
- Invalid override rejection.
- Preservation of the original discrepancy.
- Correct audit events and permissions.

### Reports and downloads
- Correct processed dataset.
- Correct audit report.
- Download access control.
- Failed report-generation behavior.
- Correct final workflow status.

### Integration
Test the complete happy path:

`Upload → Validate → Clean → Review → Confirm → Map → Confirm Mapping → Enter Treaty Figures → Validate Figures → Run Financial Checks → Review Results → Generate Reports → Download`

Also test failure paths, including invalid uploads, rejected mappings, invalid treaty figures, unresolved discrepancies, and report-generation failures.

Use small, realistic test fixtures with representative financial fields. Do not use production data or hardcode expected results from invented business assumptions.

## 8. Definition of done

The implementation is complete only when:

- [ ] The workflow is accessible through the existing application.
- [ ] Upload, validation, and cleaning work end to end.
- [ ] The before/after review displays actual processing results.
- [ ] User acknowledgement and rerun actions work.
- [ ] Column mapping integrates with the existing mapping/data-dictionary model.
- [ ] Mapping review and confirmation are persisted.
- [ ] Treaty figures are collected and validated.
- [ ] Financial rules execute deterministically.
- [ ] Discrepancies are displayed with evidence.
- [ ] Permitted overrides require a reason and produce audit events.
- [ ] The processed file and audit report are generated from actual run results.
- [ ] Downloads work and enforce access controls.
- [ ] Processing state, versions, and lineage are preserved.
- [ ] Errors are handled without corrupting the source or losing prior decisions.
- [ ] Backend, frontend, and integration tests cover the critical workflow.
- [ ] Existing tests and unrelated modules remain functional.
- [ ] The optional learning-hint functionality does not block the core workflow.
- [ ] No core step is represented by a mock action or hardcoded success response.

## 9. Execution instructions

Work directly in the current repository.

**First**, inspect the codebase and identify the existing components and services that should be reused.

**Second**, implement the workflow in small, coherent changes, keeping the application runnable throughout development.

**Third**, run the relevant tests and available lint/type checks. Fix regressions caused by your changes.

**Fourth**, verify the complete workflow using a realistic sample Excel or CSV fixture. Confirm that the displayed results and downloadable artifacts are derived from the actual processing output.

**Finally**, report:

1. What was implemented.
2. Which existing modules and components were reused.
3. The files created or modified.
4. Any database migrations or environment changes required.
5. The tests and checks executed, including their actual results.
6. How to run the feature locally.
7. Any remaining limitations or specifications that require clarification.

Do not claim a test passed unless you actually ran it successfully.

If a business rule is genuinely ambiguous, identify the exact ambiguity, choose the safest non-destructive behavior, and document the decision. Do not invent financial logic.

**Priority:** Deliver a reliable, functional first iteration of the complete core workflow before spending time on advanced AI diagnostics, elaborate visual effects, or optional learning capabilities.

Begin by inspecting the repository, then implement the feature. Do not stop at a proposal or a list of files to change.