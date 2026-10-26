# ADR-001: Modular Monolith Architecture

## Status
**Accepted**

## Date
2026-10-09

## Context

We need to choose an architectural pattern for the Bordereaux Intelligence Platform. The options considered:

1. **Microservices** — Each module as a separate service
2. **Traditional Monolith** — Single codebase without clear boundaries
3. **Modular Monolith** — Single deployment with strict module boundaries

### Constraints

- Small initial team (1-3 developers for MVP)
- Need to iterate quickly on domain model
- Future need to scale specific components
- Deterministic processing requirements
- Complex data lineage across components

## Decision

We will implement a **Modular Monolith** architecture.

### Key Characteristics

1. **Single deployable unit** — One FastAPI application
2. **Strict module boundaries** — Defined interfaces between modules
3. **Shared database** — Single PostgreSQL instance with module-owned tables
4. **In-process communication** — Direct function calls via interfaces
5. **Async workers** — Background jobs in same codebase

### Module Structure

```
src/
├── core/           # Shared kernel
├── ingestion/      # File handling
├── profiling/      # Data analysis
├── mapping/        # Schema mapping
├── standardization/# Transformation
├── reconciliation/ # Comparison
├── reporting/      # Output generation
└── api/           # HTTP interface
```

## Consequences

### Positive

- **Faster development** — No distributed system overhead
- **Simpler debugging** — Single process, shared memory
- **Easier refactoring** — Module boundaries can shift
- **Lower operational cost** — One deployment, one database
- **Strong consistency** — Database transactions span modules

### Negative

- **Scaling constraints** — Must scale entire application
- **Deployment coupling** — All modules deploy together
- **Potential boundary erosion** — Requires discipline

### Mitigation

- Enforce module boundaries via code review and linting
- Design for future extraction (interface-based communication)
- Use async workers for CPU-intensive operations
- Profile and optimize hotspots before considering split

## Alternatives Considered

### Microservices

**Rejected because:**
- Operational complexity too high for small team
- Network latency impacts deterministic processing
- Distributed transactions complicate lineage

### Traditional Monolith

**Rejected because:**
- No clear boundaries leads to coupling
- Harder to reason about module ownership
- Difficult to extract later

## References

- [Modular Monolith by Simon Brown](https://www.codingthearchitecture.com/presentations/modular-monolith)
- ANSWERING_OPEN_QUESTION.md (OQ-01 decision)
