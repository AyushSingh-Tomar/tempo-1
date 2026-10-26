# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for the Bordereaux Intelligence Platform.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](ADR-001-modular-monolith.md) | Modular Monolith Architecture | Accepted | 2026-10-09 |
| [ADR-002](ADR-002-deterministic-first.md) | Deterministic First, AI Second | Accepted | 2026-10-09 |
| [ADR-003](ADR-003-immutable-artifacts.md) | Immutable Artifacts with Versioning | Accepted | 2026-10-09 |
| [ADR-004](ADR-004-confidence-scoring.md) | Confidence Scoring Algorithm | Accepted | 2026-10-09 |
| [ADR-005](ADR-005-llm-provider-abstraction.md) | LLM Provider Abstraction | Accepted | 2026-10-09 |
| [ADR-006](ADR-006-async-job-processing.md) | Async Job Processing | Accepted | 2026-10-09 |

## ADR Template

New ADRs should follow this structure:

```markdown
# ADR-NNN: Title

## Status
Proposed | Accepted | Deprecated | Superseded

## Date
YYYY-MM-DD

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
### Positive
### Negative
### Mitigation

## Alternatives Considered

## References
```

## Process

1. Copy the template
2. Fill in the sections
3. Submit for review
4. Update status to Accepted after approval
5. Link from relevant specification documents
