# ADR-004: Confidence Scoring Algorithm

> **Revision (iteration 1.1):** the *Relationship* (20%) and *Historical* (10%) buckets are removed. Weights are now
> semantic 30%, value 25%, context 20%, layout 10%, AI 15%. Relationship checks moved to financial checks (after treaty
> figures are entered); historical/manual-mapping learning is dropped. A header that is a data-dictionary term for the
> field it maps to scores 100% outright. Sections below describing the removed buckets are superseded.

## Status
**Accepted**

## Date
2026-10-09

## Context

When generating mapping candidates between source columns and canonical schema fields, we need a transparent, explainable scoring system. Users must understand why mappings are suggested.

### Requirements

- Scores must be explainable (not black-box)
- Weights must be configurable
- Multiple evidence types contribute
- Auto-approval threshold must be defensible

## Decision

Implement a **weighted evidence-based confidence scoring system**.

### Weight Distribution (MVP)

| Evidence Type | Weight | Description |
|---------------|--------|-------------|
| Semantic similarity | 20% | Name/alias matching |
| Value compatibility | 20% | Type and range checks |
| Context signals | 15% | Position, adjacent columns |
| Layout patterns | 5% | Column groupings |
| Relationship | 20% | Computed field detection |
| Historical | 10% | Prior project mappings |
| AI adjustment | 10% | LLM confidence boost |

**Total: 100%**

### Scoring Formula

```python
confidence = (
    semantic_score * 0.20 +
    value_score * 0.20 +
    context_score * 0.15 +
    layout_score * 0.05 +
    relationship_score * 0.20 +
    historical_score * 0.10 +
    ai_score * 0.10
)
```

### Evidence Types

#### Semantic Similarity (20%)

```python
def calculate_semantic_score(source_name: str, target_field: Field) -> float:
    # Exact alias match
    if normalize(source_name) in target_field.aliases:
        return 1.0
    
    # Fuzzy name match
    similarity = jellyfish.jaro_winkler(
        normalize(source_name), 
        normalize(target_field.name)
    )
    
    return similarity
```

#### Value Compatibility (20%)

```python
def calculate_value_score(
    source_profile: ColumnProfile, 
    target_field: Field
) -> float:
    score = 0.0
    
    # Type compatibility
    if is_type_compatible(source_profile.data_type, target_field.type):
        score += 0.5
    
    # Range compatibility (for numerics)
    if target_field.type == "DECIMAL":
        if is_range_compatible(source_profile.numeric_stats, target_field):
            score += 0.3
    
    # Pattern compatibility (for strings)
    if target_field.pattern:
        if matches_pattern(source_profile.patterns, target_field.pattern):
            score += 0.2
    
    return score
```

#### Context Signals (15%)

- Position in file (first column often ID)
- Adjacent column relationships
- Header patterns

#### Historical (10%)

```python
def calculate_historical_score(
    source_name: str,
    target_field: str,
    project_history: List[ApprovedMapping]
) -> float:
    # Check if this mapping was approved before in same project
    prior = find_prior_mapping(source_name, target_field, project_history)
    if prior:
        return 1.0 if prior.status == "APPROVED" else 0.0
    return 0.0  # No history
```

#### AI Adjustment (10%)

```python
def calculate_ai_score(
    candidate: MappingCandidate,
    llm_response: Optional[LLMSuggestion]
) -> float:
    if llm_response is None:
        return 0.5  # Neutral when no LLM
    
    # LLM returns confidence 0-1
    return llm_response.confidence
```

### Auto-Approval Threshold

**Threshold: 0.95**

Candidates with confidence ≥ 0.95 are marked `auto_approve_eligible=True`.

**Conditions for auto-approval:**
1. Confidence ≥ 0.95
2. No conflicting candidates above 0.7
3. Target field not already mapped
4. User has enabled auto-approval

### Confidence Breakdown Response

```json
{
  "total": 0.92,
  "breakdown": {
    "semantic": 0.95,
    "value": 0.90,
    "context": 0.85,
    "layout": 0.70,
    "relationship": 0.90,
    "historical": 1.0,
    "ai": 0.88
  },
  "evidence": [
    {
      "type": "ALIAS_MATCH",
      "description": "Source 'CLAIM_NO' matches alias 'claim_no'",
      "contribution": 0.19
    },
    {
      "type": "TYPE_MATCH",
      "description": "Both STRING type",
      "contribution": 0.10
    }
  ]
}
```

## Consequences

### Positive

- **Transparent** — Users see why mappings scored high/low
- **Tunable** — Weights can be adjusted per project
- **Explainable** — Evidence list justifies each score
- **Auditable** — Breakdown stored with each candidate

### Negative

- **Complexity** — Multiple scoring functions to maintain
- **Calibration** — Weights may need tuning per domain
- **Edge cases** — Some columns may confuse the algorithm

### Mitigation

- Log all scoring decisions for analysis
- Allow per-project weight overrides
- Provide manual mapping as fallback
- Regular review of low-confidence false negatives

## References

- Artifact: Checks_to_perform.md (scoring rationale)
- ANSWERING_OPEN_QUESTION.md (OQ-04 approved weights)
- MODULE_CONTRACTS.md (MappingCandidateGenerator interface)
