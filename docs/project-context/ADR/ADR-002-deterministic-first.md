# ADR-002: Deterministic First, AI Second

## Status
**Accepted**

## Date
2026-10-09

## Context

The platform uses LLM capabilities for mapping suggestions and exception classification. We need to establish clear boundaries for where AI can and cannot make changes, particularly around financial data.

### Requirements

- Financial calculations must be auditable
- Results must be reproducible
- Regulatory compliance requires deterministic audit trails
- AI suggestions need human oversight

## Decision

We adopt the principle: **"Python does math, LLM interprets."**

### Rules

1. **LLM cannot modify state directly** — All changes go through human approval
2. **All calculations are Python-deterministic** — Same inputs = same outputs
3. **LLM outputs are suggestions** — Never auto-applied without review
4. **No LLM in critical path** — System works fully without LLM

### LLM Scope

| Task | LLM Role | Boundary |
|------|----------|----------|
| Mapping candidates | Suggest confidence adjustments | Cannot approve mappings |
| Exception classification | Categorize variances | Cannot resolve variances |
| Pattern explanation | Describe clusters | Cannot modify data |
| Treaty discovery | Extract terms | Cannot create treaty state |

### Implementation

```python
class LLMService:
    """LLM can only return suggestions, never mutate state."""
    
    async def suggest_mapping_confidence(
        self, 
        candidate: MappingCandidate
    ) -> Suggestion[ConfidenceAdjustment]:
        """Returns suggestion, caller decides whether to apply."""
        ...
    
    async def classify_variance(
        self, 
        variance: VarianceRecord
    ) -> Suggestion[VarianceClassification]:
        """Returns classification, does not update record."""
        ...
```

## Consequences

### Positive

- **Auditability** — Every calculation traceable
- **Reproducibility** — Same data = same results
- **Regulatory compliance** — Clear decision trail
- **Degradation path** — System works without LLM
- **Trust** — Users verify before AI changes apply

### Negative

- **More user friction** — Must review suggestions
- **Slower for obvious cases** — High-confidence suggestions still need approval
- **Development complexity** — Dual paths (with/without LLM)

### Mitigation

- Auto-approval thresholds for high-confidence, low-risk suggestions
- Batch approval UX for reviewing multiple similar suggestions
- Clear confidence indicators so users can quickly assess

## Examples

### Allowed

```python
# LLM suggests confidence adjustment
suggestion = await llm.suggest_confidence(candidate)
# Python calculates new score
new_confidence = calculate_confidence(
    base_scores,
    ai_adjustment=suggestion.value if user_approved else None
)
```

### Not Allowed

```python
# WRONG: LLM directly sets confidence
candidate.confidence = await llm.calculate_confidence(candidate)

# WRONG: LLM auto-approves mapping
if llm.should_approve(candidate):
    candidate.status = "APPROVED"  # No human in loop
```

## References

- Artifact: Module_2_Reconciliation_Implement.md, Section 5.11 (LLM Boundary)
- Artifact: Treaty_Management_Section_Implement.md (LLM discovery rules)
- ANSWERING_OPEN_QUESTION.md (OQ-05, OQ-12)
