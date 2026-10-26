# AI-Aided Mapping & Relationship Inference Module

> **Implementation README / Claude-Oriented Technical Specification**
>
> This module is the core intelligence layer of the Bordereaux Intelligence Platform. Its responsibility is to transform arbitrary raw source files into a **machine-understandable representation**, infer the semantic meaning of source fields, establish relationships between fields and datasets, produce a versioned `claims_mapping` artifact, and determine when deterministic automation is sufficient versus when AI reasoning or human review is required.
>
> **Primary implementation principle:** deterministic Python automation first, targeted LLM reasoning second, human review only where evidence is insufficient or ambiguity remains.

---

# 1. Module Overview

## 1.1 Purpose

The AI-Aided Mapping module accepts raw source files in arbitrary formats and determines:

1. What the file contains.
2. Where the actual tabular/business data begins.
3. What each source column represents.
4. Which canonical business field each source field corresponds to.
5. Which columns are mathematically, semantically, or structurally related.
6. Whether mappings can be accepted automatically.
7. Which mappings require human review.
8. How the source data should be standardized after mapping.
9. How the Claims Mapping dataset relates to the Technical Subledger.
10. Which user-defined relationship rules pass or fail.
11. What evidence supports every decision.

The module must **not** treat AI as the primary parser or transformation engine.

The intended architecture is:

```text
Raw Files
   │
   ▼
File Detection
   │
   ▼
Structure Detection
   │
   ▼
Data Extraction
   │
   ▼
Profiling
   │
   ▼
Normalization
   │
   ▼
Deterministic Candidate Generation
   │
   ▼
Deterministic Scoring
   │
   ├───────────────┐
   │               │
   ▼               ▼
Strong Evidence   Ambiguity
   │               │
   │               ▼
   │          Targeted LLM
   │               │
   └───────┬───────┘
           ▼
    Evidence Fusion
           │
           ▼
    Confidence Gate
      │     │     │
      │     │     └── BLOCKED / UNRESOLVED
      │     └──────── HUMAN REVIEW
      └────────────── AUTO ACCEPT
           │
           ▼
    Final Claims Mapping
           │
           ▼
    Standardization
           │
           ├───────────────┐
           ▼               ▼
   Relationship Checks   Subledger
           │               │
           └───────┬───────┘
                   ▼
          Validation / Exceptions
                   │
                   ▼
              Final Artifacts
```

---

## 1.2 Scope

This module owns:

* arbitrary file ingestion
* file-type detection
* structure detection
* schema inference
* data profiling
* normalization required for analysis
* semantic candidate generation
* mapping scoring
* confidence calculation
* ambiguity detection
* financial relationship inference
* cross-column relationship inference
* cross-file relationship inference
* custom relationship checks
* manual mapping overrides
* targeted LLM reasoning
* mapping caching
* claims mapping generation
* mapping versioning
* evidence generation
* validation
* exception generation
* audit metadata

It does **not** directly own:

* final reconciliation reporting
* treaty clause processing
* final report rendering
* user authentication
* enterprise notification delivery

Those modules consume artifacts generated here.

---

# 2. Why This Module Is Foundational

Almost every downstream operation depends on knowing what the source data actually means.

For example:

```text
Raw Column
"Amount"
```

cannot safely become:

```text
Commission
```

merely because another file happens to contain a column named `Commission`.

The system must establish the meaning from evidence.

Possible interpretations may include:

```text
Amount
 ├── Gross Premium
 ├── Net Premium
 ├── Commission
 ├── Tax
 ├── Claim Amount
 └── Sum Insured
```

The mapping engine therefore needs to reason over:

* names
* headers
* hierarchy
* position
* types
* values
* distributions
* ranges
* relationships
* arithmetic identities
* source context
* previous mappings
* canonical definitions

The existing platform requirements explicitly require context-aware mapping, confidence, human validation, reusable claims mapping, and financial relationship reasoning.

The established pipeline remains:

```text
Upload
  ↓
Detect Structure
  ↓
Profile
  ↓
Generate Mapping
  ↓
Confidence Gate
  ├── High → Standardize
  └── Review → Human Approval
                    ↓
                Standardize
                    ↓
             Claims Mapping
                    ↓
                 Pivot
                    ↓
             Reconciliation
                    ↓
                 Report
```

This module extends that process with additional deterministic checks and configurable relationship validation; it does **not replace or reorder the established stages**.

---

# 3. Design Principles

## 3.1 Deterministic First, AI Second

The system should attempt to solve every problem using deterministic computation before invoking an LLM.

```text
Python Rules
    ↓
Profile
    ↓
Candidate Retrieval
    ↓
Deterministic Scoring
    ↓
Business Validation
    ↓
LLM only if necessary
```

Do not call an LLM merely because one is available.

---

## 3.2 Raw Data Is Immutable

Never modify the uploaded source.

Maintain separate assets:

```text
RAW SOURCE
   ↓
PARSED REPRESENTATION
   ↓
NORMALIZED WORKING DATA
   ↓
STANDARDIZED DATASET
```

The raw artifact must remain available for lineage and audit.

---

## 3.3 AI Cannot Directly Mutate Business State

The LLM can recommend:

```text
source_column → canonical_field
```

but cannot directly:

* rename database columns
* modify mappings
* approve mappings
* overwrite source data
* alter canonical schemas
* execute arbitrary transformations

Instead:

```text
LLM
 ↓
Structured Proposal
 ↓
Pydantic Validation
 ↓
Deterministic Validation
 ↓
Confidence Engine
 ↓
Auto-accept / Human Review
 ↓
Persistence
```

---

## 3.4 Evidence Is Mandatory

Every mapping decision must have evidence.

Example:

```json
{
  "source_column": "Amount",
  "target_field": "Commission",
  "confidence": 0.82,
  "evidence": {
    "header_similarity": 0.62,
    "value_type_match": 1.0,
    "relationship_score": 0.94,
    "historical_mapping_score": 0.80
  }
}
```

Never generate explanations that are not backed by stored evidence.

---

## 3.5 Human Review Is a First-Class Workflow

Human review is not an error state.

It is an intentional decision point:

```text
Automation
    ↓
Confidence Gate
    ↓
 ┌───────────────┐
 │               │
Safe           Ambiguous
 │               │
 ▼               ▼
Accept        Human Review
```

---

# 4. Supported Input Types & Ingestion Strategy

## 4.1 Requirement

The module must accept a source file **regardless of filename extension whenever the underlying content can be identified and parsed by a registered adapter**.

Do not implement:

```python
if filename.endswith(".csv"):
    ...
elif filename.endswith(".xlsx"):
    ...
```

as the primary architecture.

Instead:

```text
File
 ↓
Magic-byte/content inspection
 ↓
Format detector
 ↓
Parser registry
 ↓
Format adapter
 ↓
Logical Dataset
```

---

## 4.2 Supported Formats

Initial adapters should include:

| Format        | Adapter                              |
| ------------- | ------------------------------------ |
| CSV           | CSV parser                           |
| TSV           | Delimited-text parser                |
| XLSX          | Excel parser                         |
| XLS           | Legacy Excel adapter where supported |
| JSON          | JSON parser                          |
| JSONL         | Streaming JSON parser                |
| XML           | XML parser                           |
| PDF           | PDF/table extraction adapter         |
| TXT           | Text/structured-text adapter         |
| Parquet       | PyArrow/Polars adapter               |
| HTML          | HTML table adapter                   |
| EDI           | EDI parser                           |
| SAS           | SAS adapter                          |
| Database dump | Registered database/dump adapter     |
| Proprietary   | Plugin adapter                       |

The system should be extensible through a parser registry.

---

## 4.3 Parser Interface

Use a common interface:

```python
class FileAdapter(Protocol):

    def can_parse(self, source: SourceArtifact) -> bool:
        ...

    def inspect(self, source: SourceArtifact) -> FileInspection:
        ...

    def extract(self, source: SourceArtifact) -> ExtractedSource:
        ...

    def preview(
        self,
        source: SourceArtifact,
        limit: int = 100
    ) -> Preview:
        ...
```

---

## 4.4 Format Detection

Detection should use:

1. extension as a weak hint
2. MIME type
3. magic bytes
4. file signature
5. parser probes
6. content structure

Example:

```python
def detect_format(path: Path) -> str:
    signature = inspect_magic_bytes(path)

    candidates = parser_registry.find_by_signature(signature)

    if not candidates:
        candidates = parser_registry.find_by_extension(path.suffix)

    for adapter in candidates:
        if adapter.can_parse(path):
            return adapter.format_name

    raise UnsupportedFormatError(...)
```

The extension must never be trusted blindly.

---

# 5. Logical Input Model

The module requires two logical business inputs.

## 5.1 Claims Mapping File

The **Claims Mapping file** is the primary business mapping reference.

It may contain:

* source-to-canonical mappings
* claim/policy identifiers
* canonical business fields
* mapping rules
* field relationships
* approved mapping information

The physical file may have any name or extension.

The system identifies it by:

* user designation
* metadata
* profile
* configured source role
* schema recognition

---

## 5.2 Subledger File

The **Subledger file** is the secondary validation source.

It is used for:

* cross-file validation
* key matching
* aggregate comparison
* relationship inference
* reconciliation preparation
* exception detection

Again, the physical filename is not authoritative.

---

## 5.3 Source Role

Every source should receive a logical role:

```text
CLAIMS_MAPPING
SUBLEDGER
SUPPORTING_SOURCE
REFERENCE
```

Example:

```json
{
  "asset_id": "asset_001",
  "logical_role": "CLAIMS_MAPPING",
  "format": "xlsx"
}
```

---

# 6. Core Concepts & Definitions

## 6.1 Source Field

A physical field extracted from the source.

```text
Source Field
├── physical_name
├── position
├── header_path
├── source_asset
├── source_sheet/table
└── profile
```

---

## 6.2 Canonical Field

A standardized business field defined by the configurable canonical schema.

Example:

```text
canonical_field_id:
    gross_premium

name:
    Gross Premium

type:
    decimal

aliases:
    ["premium amount", "written premium", "gross prem"]
```

---

## 6.3 Claims Mapping

The versioned artifact connecting physical source fields to canonical business meaning.

```text
Source Field
     ↓
Claims Mapping
     ↓
Canonical Field
```

Example:

```text
"Prem Amt"
      ↓
Gross Premium
```

---

## 6.4 Inferred Relationship

A relationship discovered from:

* column values
* mathematical behavior
* shared keys
* data distributions
* structural proximity
* semantic meaning
* cross-file matching

Examples:

```text
Gross Premium - Commission ≈ Net Premium
```

or:

```text
Claims Mapping.Policy_ID = Subledger.Policy_ID
```

---

## 6.5 Mapping Confidence

A calibrated system score representing how strongly available evidence supports a mapping.

It is **not** the LLM's self-reported confidence.

---

## 6.6 Coverage

The proportion of records participating successfully in a relationship.

```text
coverage =
matching/valid records
----------------------
eligible records
```

---

## 6.7 Relationship Confidence

The strength of evidence supporting a discovered relationship.

It should consider:

* coverage
* consistency
* uniqueness
* collision rate
* mathematical error
* sample size
* stability across partitions
* business-rule compliance

---

## 6.8 Exception

A record or relationship that violates an expected rule.

Examples:

```text
Missing key
Duplicate key
Invalid date
Arithmetic mismatch
Referential integrity failure
Currency inconsistency
```

---

# 7. End-to-End Workflow

## 7.1 Complete Workflow

```text
1. Register Input
       ↓
2. Detect Format
       ↓
3. Inspect Structure
       ↓
4. Extract Logical Tables
       ↓
5. Confirm Structure
       ↓
6. Profile Data
       ↓
7. Normalize Analysis Representation
       ↓
8. Load Canonical Schema
       ↓
9. Apply Manual / Historical Mappings
       ↓
10. Generate Candidates
       ↓
11. Score Candidates
       ↓
12. Infer Relationships
       ↓
13. Validate Candidates
       ↓
14. Detect Ambiguity
       ↓
15. Invoke LLM Only Where Required
       ↓
16. Fuse Evidence
       ↓
17. Confidence Gate
       ├── HIGH → Auto Accept
       ├── MEDIUM → Human Review
       └── LOW → Unresolved / Block
       ↓
18. Persist Final Mapping
       ↓
19. Standardize
       ↓
20. Execute Relationship Checks
       ↓
21. Compare Against Subledger
       ↓
22. Generate Exceptions
       ↓
23. Produce Claims Mapping Artifact
       ↓
24. Persist Lineage / Audit
```

---

# 8. Step 1 — Source Registration

Create a source record before processing.

```json
{
  "asset_id": "asset_123",
  "filename": "source_file.bin",
  "size_bytes": 1839201,
  "checksum_sha256": "...",
  "uploaded_at": "2026-09-30T10:00:00Z",
  "logical_role": "CLAIMS_MAPPING",
  "status": "UPLOADED"
}
```

The checksum is important for caching.

---

# 9. Step 2 — Structure Detection

Structure detection occurs before semantic mapping.

The system must determine:

* sheets
* tables
* header rows
* data-start rows
* merged cells
* blank rows
* repeated headers
* footnotes
* totals
* candidate data regions
* row/column counts

Example:

```json
{
  "sheet": "Premium",
  "header_rows": [3, 4],
  "data_start_row": 5,
  "data_end_row": 4519,
  "header_paths": {
    "G": ["Premium Details", "Amount"],
    "H": ["Premium Details", "Commission %"],
    "I": ["Premium Details", "Net"]
  }
}
```

---

# 10. Step 3 — Header Reconstruction

Physical headers should be converted into normalized header paths.

Example:

```text
Row 1:       Premium Details
Row 2:       Amount
```

becomes:

```python
[
    "Premium Details",
    "Amount"
]
```

Canonical display name:

```text
Premium Details > Amount
```

This context is significantly more informative than:

```text
Amount
```

alone.

---

# 11. Step 4 — Data Profiling

Profiling must happen before semantic reasoning.

## 11.1 Dataset-Level Profile

Collect:

```text
row_count
column_count
duplicate_rows
empty_rows
candidate_keys
partition_columns
date_columns
numeric_columns
categorical_columns
currency_columns
```

---

## 11.2 Column-Level Profile

For every column:

```json
{
  "name": "Amount",
  "position": 12,
  "header_path": [
    "Premium Details",
    "Amount"
  ],
  "inferred_type": "decimal",
  "null_rate": 0.012,
  "unique_count": 4201,
  "unique_ratio": 0.93,
  "min": 50.0,
  "max": 250000.0,
  "mean": 14320.4,
  "median": 8200.0,
  "sample_values": [
    1200.50,
    5000.00,
    830.25
  ]
}
```

---

## 11.3 String Features

Calculate:

* average length
* minimum/maximum length
* regex patterns
* alphabetic ratio
* numeric ratio
* uppercase ratio
* identifier patterns
* date-like strings
* currency-like strings
* code-like strings

Example:

```text
"POL-2026-000123"
```

can be recognized as an identifier pattern without using an LLM.

---

## 11.4 Numeric Features

Calculate:

```text
min
max
mean
median
stddev
quantiles
zero_rate
negative_rate
null_rate
distinct_count
```

Also test:

```text
integer-like
percentage-like
currency-like
ratio-like
identifier-like
```

---

## 11.5 Date Features

Test common representations:

```text
YYYY-MM-DD
DD/MM/YYYY
MM/DD/YYYY
DD-MMM-YYYY
YYYYMMDD
Excel serial dates
Unix timestamps
```

Do not ask an LLM to identify ordinary date formats.

---

# 12. Step 5 — Analysis Normalization

Normalization for analysis is distinct from final business standardization.

The system may normalize:

```text
" Premium Amount "
"premium_amount"
"PREMIUM-AMT"
```

into a comparison representation such as:

```text
premium amount
```

but must preserve the original source field.

Example:

```python
def normalize_identifier(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value
```

Never destroy the original value.

---

# 13. Step 6 — Canonical Schema Loading

Canonical schemas must be configuration-driven.

Example:

```yaml
field_id: gross_premium
name: Gross Premium
type: decimal
aliases:
  - premium amount
  - premium amt
  - gross prem
  - written premium
category: premium
required: false
relationships:
  - gross_premium_minus_commission_equals_net
```

The schema must be versioned.

```text
canonical_schema:v1
canonical_schema:v2
canonical_schema:v3
```

---

# 14. Step 7 — Manual and Historical Mapping First

Before generating AI candidates, check:

1. explicit manual mappings
2. published mapping profile
3. previously approved exact source mappings
4. deterministic aliases
5. source-template mappings

Example:

```python
mapping = mapping_memory.lookup(
    source_signature=source_signature,
    normalized_column=normalized_name
)
```

If an exact deterministic mapping is valid:

```text
DO NOT CALL LLM
```

This is one of the most important cost-optimization mechanisms.

---

# 15. Candidate Mapping Generation

## 15.1 Candidate Sources

Candidates should come from multiple deterministic mechanisms.

### A. Exact Alias Match

```text
"Premium Amt"
        ↓
Gross Premium
```

### B. Normalized Name Match

```text
"gross_prem"
        ↓
Gross Premium
```

### C. Token Similarity

Use:

* token overlap
* Jaccard similarity
* edit distance
* TF-IDF similarity

### D. Semantic Retrieval

Use embeddings only when deterministic lexical matching is insufficient.

```text
source description
       ↓
embedding
       ↓
canonical field index
       ↓
top-k candidates
```

### E. Data-Type Compatibility

Reject candidates that are structurally incompatible.

Example:

```text
source = date
candidate = Gross Premium(decimal)
```

should receive a severe penalty or be rejected.

---

# 16. Candidate Filtering

Before scoring, eliminate impossible candidates.

Example:

```python
if source_type == "date" and target_type == "decimal":
    reject(candidate)

if source_is_percentage and target.is_identifier:
    reject(candidate)
```

Candidate generation should normally produce a small set:

```text
Top 3–10 candidates
```

rather than sending the entire canonical schema to the LLM.

---

# 17. Detailed Candidate Scoring

A recommended initial scoring model:

```text
Final Score =
    semantic_score
  + value_score
  + hierarchy_score
  + layout_score
  + relationship_score
  + historical_score
  + AI_score
```

Initial configurable weights:

| Evidence                   | Default |
| -------------------------- | ------: |
| Semantic/header similarity |     20% |
| Data/value evidence        |     20% |
| Header hierarchy/context   |     15% |
| Position/layout            |      5% |
| Inter-column relationships |     20% |
| Historical mappings        |     10% |
| AI reasoning               |     10% |

These are configuration defaults, not permanent constants.

---

# 18. Semantic/Header Score

Example:

```python
semantic_score = weighted_similarity(
    source_name,
    target.name,
    target.aliases
)
```

Possible signals:

```text
exact alias             +1.00
normalized exact        +0.95
high token overlap      +0.80
partial overlap         +0.60
weak semantic relation  +0.30
unrelated               +0.00
```

Do not allow semantic similarity to independently auto-accept a financially ambiguous field.

---

# 19. Value-Type Score

Examples:

```text
source decimal
target decimal
→ strong compatibility
```

```text
source date
target date
→ strong compatibility
```

```text
source categorical
target currency
→ weak compatibility
```

This is deterministic.

---

# 20. Value-Semantics Heuristics

The system should infer semantic characteristics from values.

Examples:

### Percentage

```text
0.15
0.20
0.075
```

or:

```text
15
20
7.5
```

may indicate a percentage field depending on surrounding context.

### Currency

```text
1200.50
5000.00
830.25
```

combined with:

* currency column
* monetary header
* premium context

increases monetary-field likelihood.

### Identifier

```text
POL-000123
CLM-009321
TR-2026-001
```

should score highly as identifier-like.

---

# 21. Header Hierarchy Score

Consider:

```text
Premium Details > Amount
```

differently from:

```text
Claims > Amount
```

The word `Amount` alone is ambiguous.

The hierarchy can disambiguate:

```text
Premium > Amount
```

toward:

```text
Premium-related fields
```

while:

```text
Claims > Amount
```

moves candidates toward:

```text
Claim Amount
```

---

# 22. Layout Score

Use:

* column position
* neighboring columns
* repeated structures
* grouped headers
* source template layout

Example:

```text
Gross Premium
Commission %
Commission
Net Premium
```

strongly suggests a financial relationship cluster.

---

# 23. Historical Mapping Score

If a source template has previously been reviewed:

```text
"Prem Amt"
→
Gross Premium
```

then the approved mapping should become a deterministic signal.

Historical mapping should be weighted by:

* source identity
* source-template similarity
* mapping version
* approval status
* recency
* reviewer policy

Do not blindly reuse an old mapping if source structure materially changed.

---

# 24. Relationship Inference

Relationship inference is performed after basic profiling and candidate generation.

It should use deterministic Python calculations whenever possible.

## 24.1 Relationship Categories

```text
1. Arithmetic
2. Ratio
3. Referential
4. Key-based
5. Composite-key
6. Distributional
7. Temporal
8. Hierarchical
9. Conditional
10. Business-rule
```

---

# 25. Arithmetic Relationship Inference

Search for relationships such as:

```text
Gross Premium - Commission ≈ Net Premium
```

```text
Gross Premium + Tax ≈ Total Premium
```

```text
Sum of child amounts ≈ parent amount
```

For each hypothesis calculate:

```text
absolute_error
relative_error
match_rate
outlier_rate
coverage
```

Example:

```python
relative_error = abs(expected - actual) / max(abs(expected), epsilon)
```

---

# 26. Ratio Relationship Inference

Examples:

```text
Commission / Gross Premium ≈ Commission %
```

```text
Net Premium / Gross Premium ≈ Share %
```

The engine should test:

```text
ratio
≈ candidate percentage column
```

and measure:

```text
mean_error
median_error
p95_error
coverage
```

---

# 27. Relationship Discovery Algorithm

```python
def discover_relationships(df, candidate_fields):
    relationships = []

    numeric_columns = get_numeric_columns(df)

    for a, b in combinations(numeric_columns, 2):
        relationships.extend(
            test_pairwise_relationships(df, a, b)
        )

    relationships.extend(
        discover_three_column_relationships(
            df,
            numeric_columns
        )
    )

    return rank_relationships(relationships)
```

Do not blindly test every possible expression on huge datasets.

Use:

* sampled data
* type filtering
* semantic candidate filtering
* configurable maximum combinations
* statistical prefilters

---

# 28. Ambiguous Financial Field Example

Suppose:

```text
Premium Amt
Commission %
Amount
Net
```

Possible mappings:

```text
Amount → Gross Premium
Amount → Commission
Amount → Net Premium
```

The engine should test:

```text
Amount / Premium Amt
```

```text
Amount / Premium Amt ≈ Commission %
```

and:

```text
Premium Amt - Amount ≈ Net
```

If both relationships hold strongly:

```text
Amount → Commission
```

becomes strongly supported.

The evidence should look like:

```json
{
  "relationship_type": "arithmetic_and_ratio",
  "formula": "gross_premium - amount = net_premium",
  "coverage": 0.942,
  "median_relative_error": 0.004,
  "commission_ratio_match": 0.931
}
```

---

# 29. Confidence Computation

Confidence must be computed outside the LLM.

Example:

```python
def calculate_confidence(evidence):
    score = (
        0.20 * evidence.semantic +
        0.20 * evidence.value +
        0.15 * evidence.context +
        0.05 * evidence.layout +
        0.20 * evidence.relationship +
        0.10 * evidence.historical +
        0.10 * evidence.ai
    )

    return clamp(score, 0.0, 1.0)
```

The weights must come from configuration.

---

# 30. Confidence Calibration

Raw scores should eventually be calibrated against a labeled dataset.

Maintain:

```text
source column
expected field
system score
accepted/rejected
reviewer decision
```

Measure:

* precision
* recall
* auto-accept accuracy
* review rate
* unresolved rate
* false auto-accept rate

The goal is not simply to maximize the numerical score.

The most important safety metric is:

```text
incorrect automatic acceptance
```

---

# 31. Confidence Gates

Configuration:

```yaml
confidence:
  auto_accept_threshold: 0.90
  human_review_threshold: 0.60
  block_threshold: 0.60
```

Example behavior:

```text
0.90–1.00
    → AUTO_ACCEPT

0.60–0.899
    → HUMAN_REVIEW

<0.60
    → UNRESOLVED / BLOCKED
```

Thresholds must be configurable.

---

# 32. Hard Safety Gates

A high numerical score must not automatically override a hard validation failure.

Examples:

```text
canonical type incompatible
required relationship broken
duplicate canonical assignment where forbidden
mandatory key missing
unsupported transformation
invalid schema version
```

Then:

```text
HARD FAILURE
    ↓
BLOCK
```

even if:

```text
confidence = 0.98
```

---

# 33. LLM Integration

## 33.1 LLM Philosophy

The LLM is a **semantic decision component**, not the mapping engine.

Use it when:

```text
deterministic evidence is insufficient
```

Do not use it for:

```text
CSV parsing
Excel parsing
date detection
numeric statistics
joins
arithmetic
duplicate detection
null calculations
sorting
aggregation
schema validation
```

Python should perform those tasks.

---

# 34. When the LLM Is Called

The LLM should be invoked only for these primary cases.

## Case 1 — Semantic Ambiguity

Example:

```text
Source:
"Earned Amt"

Candidates:
- Gross Premium
- Net Premium
- Earned Premium
```

The LLM receives compact semantic context.

---

## Case 2 — Multiple High-Scoring Candidates

Example:

```text
Gross Premium    0.87
Net Premium      0.85
Commission       0.83
```

The LLM is asked to distinguish candidates using evidence.

---

## Case 3 — Relationship Hypothesis

Use an LLM when deterministic relationship discovery cannot establish what an observed relationship means.

Python may discover:

```text
A / B ≈ C
```

The LLM may determine whether this plausibly represents:

```text
Commission / Gross Premium ≈ Commission %
```

The actual numerical validation remains Python's responsibility.

---

# 35. What Is Sent to the LLM

Never send the entire raw file by default.

Send a compact evidence package.

Example:

```json
{
  "source_column": {
    "name": "Amount",
    "header_path": [
      "Premium Details",
      "Amount"
    ],
    "position": 12
  },
  "profile": {
    "type": "decimal",
    "null_rate": 0.01,
    "min": 50,
    "max": 250000,
    "median": 8200,
    "sample_values": [
      1200.5,
      5000,
      830.25
    ]
  },
  "related_columns": [
    {
      "name": "Premium Amt",
      "type": "decimal"
    },
    {
      "name": "Commission %",
      "type": "decimal"
    },
    {
      "name": "Net",
      "type": "decimal"
    }
  ],
  "candidate_fields": [
    {
      "field": "Gross Premium",
      "score": 0.72
    },
    {
      "field": "Commission",
      "score": 0.81
    },
    {
      "field": "Net Premium",
      "score": 0.75
    }
  ],
  "relationships": [
    {
      "formula": "Premium_Amt - Amount ≈ Net",
      "coverage": 0.942,
      "median_relative_error": 0.004
    }
  ]
}
```

---

# 36. What Must Not Be Sent

Avoid sending:

```text
entire Excel workbook
entire CSV
entire PDF
millions of rows
duplicate records
unnecessary columns
raw sensitive identifiers
```

unless a specific model operation genuinely requires them and deployment policy permits it.

---

# 37. LLM Output Contract

The model must return strict JSON.

```json
{
  "selected_field": "Commission",
  "alternatives": [
    {
      "field": "Net Premium",
      "confidence": 0.31,
      "reason": "..."
    }
  ],
  "semantic_reasoning": [
    "The source is located under Premium Details.",
    "The numerical relationship supports a commission interpretation."
  ],
  "relationship_hypotheses": [
    {
      "relationship": "Gross Premium - Amount = Net Premium",
      "supported": true
    }
  ],
  "needs_human_review": false
}
```

The backend validates this using Pydantic.

---

# 38. LLM Must Not Provide Final Confidence

Do not treat:

```json
{
  "confidence": 0.97
}
```

as the system confidence.

Instead:

```text
LLM reasoning
     ↓
structured semantic evidence
     ↓
Python validation
     ↓
confidence engine
```

The LLM score may be retained as one evidence signal.

---

# 39. Recommended LLM

For the implementation, use a **small/efficient structured-output reasoning model for the normal ambiguity workload**, with a stronger reasoning model available as an escalation path for unusually difficult cases.

If the deployment is using OpenAI models, the recommended architecture is:

```text
Primary:
GPT-5.6 Luna
        │
        ├── normal semantic ambiguity
        ├── candidate selection
        └── compact relationship interpretation

Escalation:
GPT-5.6 Sol
        │
        ├── difficult multi-candidate ambiguity
        ├── complex business semantics
        └── unresolved relationship interpretation
```

The important optimization is **not simply choosing the smallest model**. The largest cost reduction comes from reducing the number of calls and the amount of context sent to each call.

Model choice should therefore remain provider-abstracted:

```python
class MappingReasoner(Protocol):

    async def classify_mapping(
        self,
        evidence: MappingEvidence
    ) -> MappingDecision:
        ...
```

This allows the deployment to substitute another approved model without changing the mapping engine.

---

# 40. Token Optimization Strategy

## 40.1 Do Not Send Raw Data

Instead of:

```text
100,000 rows
```

send:

```text
type
null rate
cardinality
quantiles
sample values
patterns
relationship statistics
```

---

## 40.2 Summarize Before Reasoning

Pipeline:

```text
Raw Data
   ↓
Python Profiling
   ↓
Compact Evidence Summary
   ↓
LLM
```

---

## 40.3 Candidate Restriction

Do not send:

```text
500 canonical fields
```

Send:

```text
top 3–10 candidates
```

---

## 40.4 Chunking Rules

For large datasets:

```text
dataset
 ↓
deterministic partitions
 ↓
profile each partition
 ↓
aggregate profile
 ↓
send aggregate summary
```

Do not ask the LLM to summarize millions of rows.

---

## 40.5 Relationship Sampling

Use deterministic sampling.

Example:

```python
sample = stratified_sample(
    df,
    n=1000,
    seed=42
)
```

For financial relationships, retain representative:

* small values
* median values
* large values
* nulls
* negative values
* outliers

---

## 40.6 Structured Outputs

Always prefer:

```text
JSON Schema
```

over free-form responses.

Benefits:

* lower parsing overhead
* predictable behavior
* validation
* easier retries
* easier caching
* easier testing

---

# 41. Deterministic Prompting

Prompts should be stable.

Avoid:

```text
You are an amazing expert...
```

Prefer:

```text
Determine which candidate canonical field best explains the supplied source-field evidence.

Use only supplied evidence.

Do not invent evidence.

If evidence is insufficient, set needs_human_review=true.

Return only the required JSON schema.
```

This improves reproducibility and caching.

---

# 42. LLM Call Policy

Use this decision tree:

```python
def should_call_llm(mapping_context):
    if mapping_context.manual_mapping:
        return False

    if mapping_context.exact_historical_mapping:
        return False

    if mapping_context.deterministic_score >= AUTO_ACCEPT:
        return False

    if mapping_context.candidate_gap >= SAFE_MARGIN:
        return False

    if mapping_context.has_hard_validation_failure:
        return False

    return mapping_context.requires_semantic_reasoning
```

---

# 43. LLM Call Budget

Every mapping run should have a configurable budget.

```yaml
llm:
  enabled: true
  max_calls_per_run: 100
  max_calls_per_file: 50
  max_retries: 2
```

If the budget is exhausted:

```text
Do not silently continue with unsupported AI decisions.

Route remaining mappings to:
HUMAN REVIEW
```

---

# 44. Caching Strategy

Caching is mandatory.

A mapping request cache key should include all material inputs.

Example:

```text
SHA256(
    canonical_schema_version
    + source_signature
    + normalized_source_column
    + header_path
    + profile_hash
    + candidate_hash
    + relationship_evidence_hash
    + prompt_version
    + model_id
)
```

Example:

```python
cache_key = sha256(
    canonical_schema_version,
    source_signature,
    column_profile_hash,
    candidate_hash,
    relationship_hash,
    prompt_version,
    model_id,
)
```

---

# 45. Cache Rules

Cache:

* file inspection
* structure detection
* column profiles
* embeddings
* candidate retrieval
* LLM responses
* deterministic relationship analysis

Invalidate when:

```text
source changes
schema changes
mapping rules change
prompt version changes
model changes
profile changes
relationship configuration changes
```

---

# 46. Manual Mapping

The system must provide an explicit manual mapping API.

Example:

```python
manual_map(
    source_column="Amount",
    canonical_field="Commission",
    reason="Approved by analyst"
)
```

Manual mapping should bypass unnecessary AI calls.

Flow:

```text
Manual Mapping
      ↓
Validate Target
      ↓
Run Business Checks
      ↓
Persist Override
      ↓
Mark APPROVED / OVERRIDDEN
      ↓
Save to Mapping Memory
```

---

# 47. Manual Mapping API

```http
POST /api/mapping-runs/{run_id}/manual-mapping
```

Request:

```json
{
  "source_column": "Amount",
  "canonical_field": "commission",
  "reason": "Confirmed from carrier template",
  "save_as_reusable_rule": true
}
```

Response:

```json
{
  "mapping_id": "map_123",
  "status": "OVERRIDDEN",
  "canonical_field": "commission",
  "ai_call_required": false
}
```

---

# 48. Manual Mapping Validation

Manual mappings are not exempt from deterministic validation.

Example:

```text
User maps:
Amount → Date
```

The system should respond:

```text
Mapping rejected.

Reason:
Source values are 99.2% decimal-like while canonical Date requires a date-compatible representation.
```

The reviewer can override only where policy allows an explicit exception.

---

# 49. Inferred Relationships

Relationships are generated from the actual data rather than assumed solely from field names.

The existing financial reasoning approach should remain intact.

Core examples:

```text
Gross Premium - Commission ≈ Net Premium

Commission / Gross Premium ≈ Commission %

Net Premium / Gross Premium ≈ Share %

Parent total ≈ Sum(child records)
```

---

# 50. Relationship Evidence

Each relationship should contain:

```json
{
  "relationship_id": "rel_001",
  "type": "ARITHMETIC",
  "fields": [
    "gross_premium",
    "commission",
    "net_premium"
  ],
  "formula": "gross_premium - commission = net_premium",
  "coverage": 0.942,
  "mean_relative_error": 0.007,
  "median_relative_error": 0.004,
  "p95_relative_error": 0.021,
  "confidence": 0.94,
  "status": "SUPPORTED"
}
```

---

# 51. Custom Relationship Checks

## 51.1 Purpose

Users must be able to define relationship checks without changing Python source code.

Custom checks must support both:

```text
Claims Mapping ↔ Claims Mapping
```

and:

```text
Claims Mapping ↔ Subledger
```

This extends the existing relationship-inference capability without changing the established processing pipeline.

---

# 52. Intra-File Custom Relationships

Users can define checks entirely within the Claims Mapping dataset.

Examples:

### Key uniqueness

```text
Policy ID must be unique
```

### Composite uniqueness

```text
Policy ID + Reporting Period
must be unique
```

### Arithmetic constraint

```text
Gross Premium - Commission = Net Premium
```

### Conditional rule

```text
IF Currency = USD
THEN Premium > 0
```

### Range constraint

```text
Commission % >= 0
AND
Commission % <= 1
```

### Nullability constraint

```text
Policy ID must not be null
```

---

# 53. Cross-File Custom Relationships

Users can define relationships between Claims Mapping and Subledger.

Examples:

```text
ClaimsMapping.PolicyID
        =
Subledger.PolicyID
```

or:

```text
ClaimsMapping.PolicyID
+ ClaimsMapping.ReportingPeriod
        =
Subledger.PolicyID
+ Subledger.ReportingPeriod
```

---

# 54. Supported Custom Relationship Types

The rule engine should support:

| Relationship          | Example                          |
| --------------------- | -------------------------------- |
| Key-to-key            | `claim.id = ledger.claim_id`     |
| Composite key         | `policy + period`                |
| Conditional join      | join only when `status = ACTIVE` |
| Referential integrity | every claim exists in subledger  |
| One-to-one            | exactly one ledger record        |
| One-to-many           | one policy → many claims         |
| Many-to-one           | many transactions → one policy   |
| Aggregate             | sum claims = ledger amount       |
| Arithmetic            | `A - B = C`                      |
| Ratio                 | `A / B ≈ C`                      |
| Range                 | `0 <= commission_pct <= 1`       |
| Nullability           | required field cannot be null    |
| Uniqueness            | field/composite key unique       |
| Temporal              | date relationships               |
| Business condition    | configurable expression          |

---

# 55. Custom Relationship Definition

Recommended schema:

```json
{
  "relationship_id": "custom_001",
  "name": "Claims to Subledger Policy Match",
  "scope": "CROSS_FILE",
  "left_asset": "claims_mapping",
  "right_asset": "subledger",
  "type": "KEY_TO_KEY",
  "keys": [
    {
      "left": "policy_id",
      "right": "policy_id"
    }
  ],
  "condition": null,
  "expected_cardinality": "MANY_TO_ONE",
  "coverage_threshold": 0.98,
  "failure_policy": "REVIEW",
  "enabled": true
}
```

---

# 56. Composite-Key Rule

Example:

```json
{
  "type": "COMPOSITE_KEY",
  "keys": [
    {
      "left": "policy_id",
      "right": "policy_id"
    },
    {
      "left": "reporting_period",
      "right": "reporting_period"
    },
    {
      "left": "currency",
      "right": "currency"
    }
  ]
}
```

The engine should normalize each key before comparison according to configured normalization rules.

---

# 57. Conditional Join

Example:

```json
{
  "type": "CONDITIONAL_JOIN",
  "keys": [
    {
      "left": "policy_id",
      "right": "policy_id"
    }
  ],
  "condition": {
    "field": "status",
    "operator": "equals",
    "value": "ACTIVE"
  }
}
```

Conditions must be represented as structured expressions rather than arbitrary Python code.

Do not execute user-supplied Python expressions.

---

# 58. Referential Integrity Check

Example:

```text
Every ClaimsMapping.PolicyID
must exist in
Subledger.PolicyID
```

Result:

```json
{
  "passed": false,
  "coverage": 0.973,
  "exceptions": 143
}
```

---

# 59. Aggregate Relationship Check

Example:

```text
SUM(ClaimsMapping.NetPremium)
    =
Subledger.NetPremium
```

The engine should calculate:

```text
left_total
right_total
absolute_variance
relative_variance
tolerance
status
```

Example:

```json
{
  "left_total": 10452300.25,
  "right_total": 10451890.25,
  "absolute_variance": 410.00,
  "relative_variance": 0.000039,
  "tolerance": 0.001,
  "passed": true
}
```

---

# 60. Relationship Validation Result

Every custom check must generate a structured result.

```json
{
  "relationship_id": "custom_001",
  "status": "PASS",
  "evaluated_rows": 4521,
  "passed_rows": 4470,
  "failed_rows": 51,
  "coverage": 0.9887,
  "confidence": 0.981,
  "exceptions_artifact": "exceptions_001"
}
```

Possible statuses:

```text
PASS
PASS_WITH_WARNINGS
FAIL
NOT_EVALUATED
BLOCKED
```

---

# 61. Relationship Confidence

Confidence should be deterministic where possible.

Example:

```python
relationship_confidence = (
    0.40 * coverage_score +
    0.25 * consistency_score +
    0.20 * uniqueness_score +
    0.15 * sample_stability_score
)
```

The exact weights must be configurable.

---

# 62. Relationship Exception Report

Exceptions should include:

```json
{
  "relationship_id": "custom_001",
  "row_reference": "claims:1045",
  "left_key": "POL-1023",
  "right_key": null,
  "failure_type": "MISSING_REFERENCE",
  "severity": "HIGH",
  "evidence": {
    "left_value": "POL-1023"
  }
}
```

---

# 63. Relationship UI

Custom relationships should be configurable through a visual rule builder.

```text
Relationship Checks

[ + Create Check ]

Name:
Claims → Subledger Policy Match

Source:
Claims Mapping

Field:
Policy ID

Operator:
equals

Target:
Subledger

Field:
Policy ID

Expected:
Many-to-One

Coverage:
>= 98%

[Validate] [Save]
```

Advanced mode:

```text
Composite Keys
Conditions
Aggregations
Tolerance
Failure Policy
Schedule
```

---

# 64. Custom Checks Must Not Change the Main Pipeline

Custom relationship checks are extensions.

They should execute within the existing workflow:

```text
Upload
 ↓
Structure
 ↓
Profile
 ↓
Mapping
 ↓
Confidence Gate
 ↓
Review
 ↓
Standardize
 ↓
Claims Mapping
 ↓
Relationship Checks
 ↓
Subledger Validation
 ↓
Pivot / Reconciliation
```

They must not replace:

* profiling
* mapping
* confidence scoring
* human review
* standardization
* claims mapping
* reconciliation

---

# 65. Standardization

After mapping approval:

```text
Raw Source
  ↓
Structure Cleanup
  ↓
Column Mapping
  ↓
Type Coercion
  ↓
Date Normalization
  ↓
Currency Normalization
  ↓
Value Standardization
  ↓
Business Rule Validation
  ↓
Canonical Dataset
```

The mapping artifact is used as the source of truth.

---

# 66. Standardization Functions

```python
normalize_column_names()
normalize_dates()
normalize_currency()
normalize_numeric_fields()
normalize_nulls()
normalize_categories()
apply_field_transform()
apply_business_rule()
validate_canonical_schema()
write_standardized_dataset()
```

---

# 67. Claims Mapping Artifact

The final artifact should contain at minimum:

```json
{
  "mapping_run_id": "run_001",
  "source_asset_id": "asset_001",
  "source_field": "Premium Amt",
  "source_column_index": 8,
  "source_header_path": [
    "Premium Details",
    "Premium Amt"
  ],
  "canonical_field_id": "gross_premium",
  "mapping_type": "SEMANTIC",
  "confidence": 0.94,
  "evidence": {},
  "reasoning_summary": "...",
  "validation_status": "APPROVED",
  "reviewer": null,
  "review_timestamp": null,
  "mapping_version": 3
}
```

---

# 68. Mapping Status Lifecycle

```text
PROPOSED
   │
   ├── deterministic safe
   │       ↓
   │   AUTO_ACCEPTED
   │
   └── ambiguous
           ↓
    REVIEW_REQUIRED
           ↓
      ┌────┴────┐
      ▼         ▼
  APPROVED   OVERRIDDEN
      │         │
      └────┬────┘
           ▼
       SUPERSEDED
```

Rejected mappings must remain in history.

---

# 69. Human Review Interface

The Mapping Studio should expose:

```text
┌─────────────────────────────────────────────────────────────┐
│ Source Field       Proposed Mapping       Confidence        │
├─────────────────────────────────────────────────────────────┤
│ Policy Ref         Reference              98%               │
│ Effective Dt       Date                   96%               │
│ Premium Amt        Gross Premium          91%               │
│ Amount             Commission              58%  REVIEW       │
│ Net                Net Premium             93%               │
└─────────────────────────────────────────────────────────────┘
```

When `Amount` is selected:

```text
Inspector
───────────────
Evidence
Samples
Statistics
Relationships
Alternatives
Historical mappings
AI explanation

Actions
[Accept]
[Choose Alternative]
[Map Manually]
[Reject]
[Save Rule]
```

---

# 70. Human Review Decision Model

Reviewer actions:

```text
ACCEPT
REJECT
SELECT_ALTERNATIVE
MANUAL_MAP
MARK_UNUSED
ADD_COMMENT
SAVE_REUSABLE_RULE
```

Store:

```text
original proposal
reviewer action
previous value
final value
reviewer
timestamp
comment
mapping version
```

Review history must be immutable.

---

# 71. Python Architecture

Recommended repository structure:

```text
mapping_engine/
│
├── ingestion/
│   ├── registry.py
│   ├── detectors.py
│   ├── adapters/
│   │   ├── csv.py
│   │   ├── excel.py
│   │   ├── json.py
│   │   ├── xml.py
│   │   ├── pdf.py
│   │   ├── parquet.py
│   │   ├── html.py
│   │   ├── edi.py
│   │   └── sas.py
│
├── structure/
│   ├── detector.py
│   ├── headers.py
│   └── tables.py
│
├── profiling/
│   ├── dataset.py
│   ├── column.py
│   ├── numeric.py
│   ├── dates.py
│   └── patterns.py
│
├── normalization/
│   ├── identifiers.py
│   ├── values.py
│   └── types.py
│
├── mapping/
│   ├── candidates.py
│   ├── scoring.py
│   ├── confidence.py
│   ├── ambiguity.py
│   ├── memory.py
│   └── manual.py
│
├── relationships/
│   ├── arithmetic.py
│   ├── ratios.py
│   ├── keys.py
│   ├── inference.py
│   ├── custom_rules.py
│   └── validation.py
│
├── ai/
│   ├── provider.py
│   ├── prompts.py
│   ├── schemas.py
│   ├── cache.py
│   └── reasoner.py
│
├── standardization/
│   ├── mapper.py
│   ├── transforms.py
│   └── validator.py
│
├── artifacts/
│   ├── claims_mapping.py
│   ├── evidence.py
│   └── exceptions.py
│
└── tests/
```

---

# 72. Core Python Services

```python
class IngestionService:
    def ingest_file(...)
    def inspect_file(...)
    def detect_structure(...)
    def confirm_structure(...)


class ProfilingService:
    def profile_dataset(...)
    def profile_column(...)
    def analyze_relationships(...)


class MappingService:
    def generate_candidates(...)
    def score_candidates(...)
    def detect_ambiguity(...)
    def generate_explanation(...)
    def create_proposal(...)
    def approve_mapping(...)
    def persist_decision(...)


class RelationshipService:
    def infer_relationships(...)
    def validate_relationship(...)
    def execute_custom_check(...)
    def create_exception(...)


class StandardizationService:
    def apply_mapping(...)
    def normalize_types(...)
    def normalize_dates(...)
    def normalize_currency(...)
    def apply_rules(...)
    def validate_output(...)
```

---

# 73. Automation-First Processing Engine

The orchestration layer should look approximately like:

```python
async def process_mapping_run(run_id: str):

    source = await ingest_service.get_source(run_id)

    inspection = await ingestion.inspect_file(source)

    structure = await ingestion.detect_structure(
        inspection
    )

    profile = await profiling.profile_dataset(
        source,
        structure
    )

    canonical_schema = schema_service.load_active()

    deterministic_mappings = (
        mapping_memory.apply_known_mappings(
            source,
            structure,
            profile
        )
    )

    candidates = mapping.generate_candidates(
        source,
        profile,
        canonical_schema,
        deterministic_mappings
    )

    relationships = relationship.infer_relationships(
        profile,
        candidates
    )

    proposals = mapping.score_candidates(
        candidates,
        relationships
    )

    proposals = await ai_reasoner.enrich_only_if_needed(
        proposals,
        profile,
        relationships
    )

    decisions = confidence_engine.evaluate(
        proposals
    )

    await review_router.route(decisions)

    return decisions
```

---

# 74. Large Dataset Strategy

Never load unnecessarily large files into memory.

Use:

* Polars
* PyArrow
* pandas for manageable datasets
* streaming parsers
* chunked reads
* Parquet intermediates

Example:

```python
for batch in reader.iter_batches(batch_size=100_000):
    update_profile(batch)
```

The profile accumulator should maintain:

```text
count
null count
min
max
mean
variance
quantiles
cardinality estimate
pattern frequencies
```

without requiring the entire dataset in memory.

---

# 75. Performance Strategy

For large files:

```text
Upload
 ↓
Async Job
 ↓
Incremental Inspection
 ↓
Streaming Profile
 ↓
Candidate Generation
 ↓
Targeted Reasoning
```

The browser should never receive the entire raw dataset merely to perform mapping.

---

# 76. API Surface

## Ingestion

```http
POST /api/ingestions
GET  /api/ingestions/{id}
GET  /api/ingestions/{id}/preview
GET  /api/ingestions/{id}/structure
POST /api/ingestions/{id}/confirm-structure
```

## Mapping

```http
POST /api/mapping-runs
GET  /api/mapping-runs/{id}
GET  /api/mapping-runs/{id}/proposals
POST /api/mapping-runs/{id}/review
POST /api/mapping-runs/{id}/approve
POST /api/mapping-runs/{id}/manual-mapping
POST /api/mapping-runs/{id}/standardize
```

## Relationships

```http
GET  /api/mapping-runs/{id}/relationships
POST /api/mapping-runs/{id}/relationships/infer
POST /api/mapping-runs/{id}/relationships/custom
POST /api/mapping-runs/{id}/relationships/{relationship_id}/validate
GET  /api/mapping-runs/{id}/relationships/{relationship_id}/exceptions
```

## Mapping Profiles

```http
POST /api/mapping-profiles
GET  /api/mapping-profiles
POST /api/mapping-profiles/{id}/apply
POST /api/mapping-profiles/{id}/publish
POST /api/mapping-profiles/{id}/rollback
```

---

# 77. CLI Examples

## Process a file

```bash
python -m mapping_engine run \
  --input ./source_file.xlsx \
  --role claims_mapping
```

---

## Process both sources

```bash
python -m mapping_engine run \
  --claims ./claims_mapping.xlsx \
  --subledger ./subledger.xlsx
```

---

## Preview structure

```bash
python -m mapping_engine inspect \
  --input ./source.xlsx
```

---

## Generate mappings

```bash
python -m mapping_engine map \
  --run-id run_001
```

---

## Run relationship checks

```bash
python -m mapping_engine relationships validate \
  --run-id run_001
```

---

## Add a manual mapping

```bash
python -m mapping_engine mapping manual \
  --run-id run_001 \
  --source "Amount" \
  --target "commission"
```

---

# 78. Configuration

Example:

```yaml
mapping:
  candidate_count: 10
  deterministic_first: true
  use_embeddings: true
  require_evidence: true

confidence:
  auto_accept_threshold: 0.90
  review_threshold: 0.60
  block_below: 0.60

relationships:
  enabled: true
  max_columns_for_pairwise_analysis: 100
  sample_size: 5000
  default_tolerance: 0.001

llm:
  enabled: true
  provider: openai
  primary_model: gpt-5.6-luna
  escalation_model: gpt-5.6-sol
  max_calls_per_run: 100
  max_retries: 2
  cache_enabled: true

security:
  external_ai_allowed: false
  redact_sensitive_values: true
```

---

# 79. Sensitive Data Redaction

When possible, replace sensitive values before sending them to an external LLM.

Instead of:

```text
John Smith
```

send:

```text
<PERSON_001>
```

Instead of:

```text
123456789
```

send:

```text
<ID_PATTERN_001>
```

Retain the mapping locally.

---

# 80. AI Privacy Boundary

The system must have an explicit policy:

```text
Raw Source
    │
    ├── Deterministic Processing
    │       ↓
    │   Evidence Summary
    │
    └── Optional Redaction
            ↓
       Approved AI Provider
```

No confidential source data should be sent to an external AI provider unless explicitly permitted by deployment policy.

---

# 81. Database Models

Minimum entities:

```text
SourceAsset
IngestionRun
StructureDetection
DatasetProfile
ColumnProfile
CanonicalSchema
CanonicalField
MappingRun
MappingProposal
MappingDecision
MappingProfile
RelationshipDefinition
RelationshipResult
RelationshipException
LLMCall
LLMCache
StandardizedDataset
AuditEvent
```

---

# 82. Mapping Proposal Schema

```python
class MappingProposal(BaseModel):

    source_field: str
    source_header_path: list[str]

    canonical_field_id: str

    candidate_rank: int

    confidence: float

    evidence: dict

    reasoning_summary: str | None

    needs_human_review: bool

    status: Literal[
        "PROPOSED",
        "AUTO_ACCEPTED",
        "REVIEW_REQUIRED",
        "APPROVED",
        "REJECTED",
        "OVERRIDDEN"
    ]
```

---

# 83. Relationship Schema

```python
class RelationshipResult(BaseModel):

    relationship_id: str

    relationship_type: str

    status: str

    evaluated_rows: int

    passed_rows: int

    failed_rows: int

    coverage: float

    confidence: float

    exceptions_count: int

    evidence: dict
```

---

# 84. LLM Call Audit

Every LLM call must be recorded.

```json
{
  "call_id": "llm_001",
  "run_id": "run_001",
  "model": "gpt-5.6-luna",
  "prompt_version": "mapping-v3",
  "input_hash": "...",
  "cache_hit": false,
  "tokens_input": 820,
  "tokens_output": 240,
  "latency_ms": 1320,
  "result_status": "SUCCESS"
}
```

Do not persist sensitive prompt content unless deployment policy permits it.

---

# 85. Failure Modes & Recovery

## 85.1 Unsupported File

```text
STATUS:
UNSUPPORTED_FORMAT
```

Provide:

```text
detected format
available adapters
recommended action
```

---

## 85.2 Structure Detection Failure

Route to:

```text
STRUCTURE_REVIEW
```

User can specify:

```text
sheet
header rows
data start
data end
```

---

## 85.3 Ambiguous Mapping

```text
REVIEW_REQUIRED
```

Do not guess silently.

---

## 85.4 LLM Failure

If:

```text
timeout
rate limit
invalid JSON
provider unavailable
```

then:

```text
retry
 ↓
cache check
 ↓
fallback model if configured
 ↓
human review
```

Never silently replace failed AI reasoning with an unsupported assumption.

---

## 85.5 Relationship Failure

Relationship failure should create an exception rather than corrupting the dataset.

---

## 85.6 Invalid Manual Mapping

Reject the mapping when hard validation fails unless explicit override policy allows it.

---

# 86. Idempotency

Repeated execution against the same immutable source and configuration should produce the same deterministic artifacts.

Use:

```text
source checksum
schema version
mapping profile version
relationship configuration version
normalization version
prompt version
model version
```

to identify processing state.

---

# 87. Versioning

Important objects are immutable versions.

```text
Mapping Profile v1
Mapping Profile v2
Mapping Profile v3
```

Never modify historical versions in place.

A new decision creates a new version.

---

# 88. Lineage

The system must preserve:

```text
Raw File
   ↓
Ingestion
   ↓
Structure Detection
   ↓
Profile
   ↓
Mapping Proposal
   ↓
Mapping Decision
   ↓
Standardized Dataset
   ↓
Relationship Results
   ↓
Claims Mapping
   ↓
Pivot
   ↓
Reconciliation
```

A user should be able to trace any canonical field back to its raw source.

---

# 89. Audit Events

At minimum:

```text
FILE_UPLOADED
FORMAT_DETECTED
STRUCTURE_DETECTED
STRUCTURE_CONFIRMED
PROFILE_CREATED
MAPPING_GENERATED
LLM_CALLED
MAPPING_REVIEWED
MAPPING_APPROVED
MAPPING_OVERRIDDEN
RELATIONSHIP_INFERRED
RELATIONSHIP_CHECKED
RELATIONSHIP_FAILED
DATA_STANDARDIZED
CLAIMS_MAPPING_CREATED
```

Each event should include:

```text
event_id
actor
timestamp
project
resource
action
before_reference
after_reference
correlation_id
```

---

# 90. Testing Strategy

## 90.1 Unit Tests

Test:

* format detection
* parser adapters
* header reconstruction
* structure detection
* profiling
* type inference
* normalization
* candidate generation
* candidate scoring
* confidence calculation
* relationship inference
* custom relationship validation
* manual mapping
* cache keys
* schema validation

---

# 91. Golden Mapping Tests

Maintain:

```text
source field
expected canonical field
expected relationship
```

Example:

```text
"Prem Amt" → Gross Premium
"Comm %"   → Commission %
"Net"      → Net Premium
```

Track:

```text
precision
recall
auto-accept accuracy
false auto-accept rate
review rate
unresolved rate
```

---

# 92. Financial Relationship Tests

Create known datasets:

```text
Gross = 1000
Commission = 100
Net = 900
```

Expected:

```text
Gross - Commission = Net
Commission / Gross = 10%
```

Add deliberately corrupted records:

```text
Gross = 1000
Commission = 100
Net = 950
```

The relationship engine must identify the exception.

---

# 93. Custom Relationship Tests

Test:

```text
one-to-one
one-to-many
many-to-one
composite keys
missing keys
duplicate keys
conditional joins
aggregate relationships
tolerance rules
null handling
```

---

# 94. LLM Tests

Use mocked model responses.

Test:

```text
valid JSON
invalid JSON
missing fields
wrong candidate
hallucinated evidence
low-confidence response
timeout
rate-limit
cache hit
```

The system must reject malformed output.

---

# 95. LLM Evaluation

Maintain a fixed evaluation dataset.

Measure:

```text
candidate-selection accuracy
semantic disambiguation accuracy
unsupported-evidence rate
review routing accuracy
token usage
average latency
cache-hit rate
cost per mapping run
```

The LLM must not be judged only by whether it produces fluent explanations.

---

# 96. Integration Test

The primary integration test is:

```text
Raw File
   ↓
Format Detection
   ↓
Structure Detection
   ↓
Profile
   ↓
Candidate Generation
   ↓
Relationship Inference
   ↓
Mapping
   ↓
Confidence Gate
   ↓
Human Override
   ↓
Standardization
   ↓
Claims Mapping
   ↓
Custom Relationship Checks
   ↓
Subledger Validation
   ↓
Exceptions
```

---

# 97. Synthetic Demo Dataset

The demo data should intentionally contain:

* multi-row headers
* inconsistent column names
* blank rows
* date variations
* currency variations
* ambiguous `Amount`
* gross/commission/net relationships
* technical subledger
* missing keys
* duplicate keys
* at least one custom relationship failure

Example:

```text
Premium Details
    Premium Amt
    Commission %
    Amount
    Net
```

The demo should demonstrate the engine discovering:

```text
Amount → Commission
```

through relationships rather than name similarity alone.

---

# 98. Example Complete Mapping Run

```text
INPUT
─────
claims_mapping.xlsx
subledger.xlsx

        ↓

FORMAT DETECTION
────────────────
XLSX
XLSX

        ↓

STRUCTURE
─────────
Claims:
  Sheet = Premium
  Header = rows 3–4
  Data = row 5+

Subledger:
  Sheet = Transactions
  Header = row 1
  Data = row 2+

        ↓

PROFILE
───────
Policy ID → identifier
Premium Amt → decimal
Commission % → percentage
Amount → decimal
Net → decimal

        ↓

CANDIDATES
──────────
Amount:
  Gross Premium 0.72
  Commission     0.81
  Net Premium    0.75

        ↓

RELATIONSHIP ANALYSIS
─────────────────────
Premium Amt - Amount ≈ Net
Coverage = 94.2%

Amount / Premium Amt ≈ Commission %
Coverage = 93.1%

        ↓

EVIDENCE FUSION
───────────────
Commission = 0.94

        ↓

CONFIDENCE GATE
───────────────
AUTO_ACCEPT
```

If evidence is weaker:

```text
CONFIDENCE = 0.61

        ↓

REVIEW_REQUIRED
```

---

# 99. Example Human Review

```text
Source:
Amount

Proposed:
Commission

Confidence:
61%

Alternatives:
Gross Premium  58%
Net Premium    55%

Evidence:
- Numeric currency-like values
- Located under Premium Details
- Gross - Amount ≈ Net on 81% of rows
- Amount / Gross ≈ Commission % on 78% of rows

Decision:
[Accept]
[Select Alternative]
[Map Manually]
[Reject]
```

The reviewer can select:

```text
Accept
```

The system then creates:

```text
MappingDecision
status = APPROVED
```

and optionally:

```text
ReusableMappingRule
```

---

# 100. Example Custom Relationship

User creates:

```text
Name:
Claims/Subledger Policy Reference

Type:
Cross-file Referential Integrity

Claims:
Policy ID

Subledger:
Policy ID

Expected:
Every Claims Policy ID exists in Subledger
```

Execution:

```text
Claims records:       4,521
Matched:              4,470
Missing:                 51

Coverage:
98.87%

Status:
PASS_WITH_WARNINGS
```

The 51 missing records become exceptions.

---

# 101. Security Requirements

The module may process highly confidential insurance data.

Required:

* encryption at rest
* encryption in transit
* least-privilege access
* project isolation
* tenant isolation where applicable
* secure temporary files
* configurable retention
* secrets manager
* audit logging
* controlled AI-provider access
* sensitive-value redaction
* no uncontrolled external AI transmission

Development should use synthetic data.

---

# 102. Observability

Every mapping run should expose:

```text
run status
duration
files processed
rows processed
columns processed
mappings generated
auto-accepted mappings
review-required mappings
blocked mappings
relationship checks
exceptions
LLM calls
LLM cache hits
tokens used
estimated AI cost
errors
warnings
```

Example:

```json
{
  "run_id": "run_001",
  "status": "COMPLETED",
  "columns": 82,
  "auto_accepted": 69,
  "review_required": 11,
  "blocked": 2,
  "llm_calls": 7,
  "cache_hits": 18,
  "relationship_checks": 14,
  "exceptions": 23
}
```

---

# 103. Operational State Machine

Use the established processing state model:

```text
CREATED
   ↓
UPLOADED
   ↓
INSPECTING
   ↓
STRUCTURE_DETECTED
   ↓
AWAITING_STRUCTURE_CONFIRMATION
   ↓
PROFILING
   ↓
MAPPING
   ↓
AWAITING_MAPPING_REVIEW
   ↓
STANDARDIZING
   ↓
MAPPING_COMPLETE
   ↓
PIVOTING
   ↓
READY_FOR_RECONCILIATION
   ↓
RECONCILING
   ↓
REPORTING
   ↓
COMPLETED
```

Failures must be explicit and recoverable.

---

# 104. Implementation Priorities

## Phase 1 — Deterministic Foundation

Implement:

```text
file adapters
format detection
structure detection
header reconstruction
profiling
normalization
canonical schema
```

No LLM dependency should be required for this phase.

---

## Phase 2 — Mapping Engine

Implement:

```text
mapping memory
candidate generation
candidate scoring
confidence
claims mapping
manual mapping
```

---

## Phase 3 — Relationship Engine

Implement:

```text
numeric relationships
financial relationships
key detection
cross-file matching
custom relationship checks
exception generation
```

---

## Phase 4 — AI Reasoner

Implement:

```text
LLM interface
structured prompts
Pydantic outputs
cache
token tracking
semantic ambiguity
relationship hypothesis reasoning
```

---

## Phase 5 — Human Review

Implement:

```text
review queue
evidence inspector
alternative selection
manual override
comments
reusable rules
approval history
```

---

## Phase 6 — Optimization

Implement:

```text
confidence calibration
model escalation
sampling improvements
cache optimization
cost telemetry
false-auto-accept monitoring
```

---

# 105. Definition of Done

Claude should consider this module complete only when:

* arbitrary supported file formats can enter through one ingestion interface
* file format is detected independently of filename extension
* structure detection occurs before semantic mapping
* multi-row headers are reconstructed
* actual values are profiled
* canonical schema is configurable and versioned
* manual mappings are supported
* historical mappings are reused
* deterministic candidates are generated
* candidate scoring is implemented
* confidence is calculated outside the LLM
* relationships are inferred deterministically where possible
* ambiguous mappings can invoke an LLM
* LLM output is schema validated
* LLM calls are cached
* token usage is measured
* raw data is not unnecessarily sent to the LLM
* low-confidence mappings enter human review
* human decisions are immutable
* final claims mapping is generated
* standardization uses approved mappings
* custom intra-file relationship checks work
* custom cross-file relationship checks work
* relationship exceptions are generated
* subledger relationships can be validated
* lineage is recorded
* audit events are emitted
* failures are recoverable
* tests cover deterministic and AI paths
* demo data proves the complete workflow
* no unsupported AI decision is silently accepted

---

# 106. Final Architecture

```text
                         ┌──────────────────────┐
                         │      RAW FILES       │
                         │ CSV/XLSX/JSON/XML/...│
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ FORMAT DETECTION     │
                         │ Parser Registry      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ STRUCTURE DETECTION  │
                         │ Headers / Tables     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ DATA PROFILING       │
                         │ Types / Values       │
                         │ Patterns / Stats     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ NORMALIZATION        │
                         │ Analysis Representation│
                         └──────────┬───────────┘
                                    │
                                    ▼
              ┌──────────────────────────────────────────┐
              │       DETERMINISTIC MAPPING ENGINE       │
              │                                          │
              │ Alias / Semantic Retrieval               │
              │ Type Compatibility                       │
              │ Context / Header Hierarchy               │
              │ Historical Mapping Memory                │
              │ Relationship Evidence                    │
              └──────────────────────┬───────────────────┘
                                     │
                                     ▼
                         ┌──────────────────────┐
                         │ RELATIONSHIP ENGINE  │
                         │                      │
                         │ Arithmetic           │
                         │ Ratios               │
                         │ Keys                 │
                         │ Composite Keys       │
                         │ Cross-file           │
                         │ Custom Rules         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ CANDIDATE SCORER     │
                         │ + EVIDENCE FUSION    │
                         └──────────┬───────────┘
                                    │
                           ┌────────┴────────┐
                           │                 │
                           ▼                 ▼
                  ┌────────────────┐  ┌────────────────┐
                  │ DETERMINISTIC  │  │ TARGETED LLM   │
                  │ VALIDATION     │  │ REASONING      │
                  └────────┬───────┘  └───────┬────────┘
                           │                  │
                           └────────┬─────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ CONFIDENCE CALIBRATOR│
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┼─────────────────┐
                   │                │                 │
                   ▼                ▼                 ▼
             AUTO ACCEPT      HUMAN REVIEW       BLOCKED
                   │                │
                   │                ▼
                   │         MANUAL DECISION
                   │                │
                   └────────┬───────┘
                            ▼
                  ┌──────────────────────┐
                  │ FINAL CLAIMS MAPPING │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ STANDARDIZATION      │
                  │ Types / Dates /      │
                  │ Currency / Rules     │
                  └──────────┬───────────┘
                             │
                 ┌───────────┴────────────┐
                 ▼                        ▼
        ┌──────────────────┐     ┌──────────────────┐
        │ CUSTOM RELATION- │     │ TECHNICAL        │
        │ SHIP VALIDATION  │     │ SUBLEDGER        │
        └────────┬─────────┘     └────────┬─────────┘
                 │                        │
                 └───────────┬────────────┘
                             ▼
                    ┌──────────────────┐
                    │ EXCEPTIONS /     │
                    │ VALIDATION       │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ DOWNSTREAM        │
                    │ PIVOT / RECON /   │
                    │ REPORT / LINEAGE  │
                    └──────────────────┘
```

---

# 107. Core Implementation Rule

The implementation should follow this principle throughout the codebase:

```text
                    ┌─────────────────────┐
                    │       RAW DATA      │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │     PYTHON FIRST    │
                    │                     │
                    │ Parse               │
                    │ Profile             │
                    │ Normalize           │
                    │ Generate Candidates │
                    │ Calculate Relations │
                    │ Validate            │
                    │ Score               │
                    └──────────┬──────────┘
                               ↓
                    Is the evidence enough?
                         /           \
                       YES            NO
                       /               \
                      ▼                 ▼
                 AUTOMATE          TARGETED LLM
                                      │
                                      ▼
                              Structured Evidence
                                      │
                                      ▼
                               Python Validation
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                       SAFE                    UNCERTAIN
                         │                         │
                         ▼                         ▼
                    AUTO ACCEPT              HUMAN REVIEW
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                              FINAL MAPPING
                                      │
                                      ▼
                               STANDARDIZE
                                      │
                                      ▼
                            VALIDATE RELATIONSHIPS
```

**The LLM is a decision-support component inside the pipeline—not the pipeline itself.**

The module succeeds when the majority of ordinary mappings are resolved deterministically, AI is reserved for genuinely semantic ambiguity, human review is triggered only when evidence warrants it, and every resulting business decision can be traced back to the raw source and the evidence that supported it.
