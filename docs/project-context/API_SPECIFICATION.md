# API Specification
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **OpenAPI:** 3.1.0

---

## 1. API Design Principles

### 1.1 RESTful Conventions

- **Resources as nouns** — `/projects`, `/assets`, `/mappings`
- **HTTP verbs for actions** — GET, POST, PATCH, DELETE
- **Plural resource names** — `/projects/{id}/assets`
- **Nested for ownership** — Assets belong to projects
- **Flat for independence** — Reconciliations reference but don't belong

### 1.2 URL Structure

```
/api/v1/{resource}/{id}/{sub-resource}
```

### 1.3 HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PATCH |
| 201 | Created | Successful POST |
| 202 | Accepted | Async job started |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation error |
| 401 | Unauthorized | Missing/invalid auth |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | State conflict |
| 422 | Unprocessable | Semantic error |
| 500 | Server Error | Unexpected failure |

---

## 2. Request/Response Format

### 2.1 Request Headers

```http
Content-Type: application/json
Authorization: Bearer {token}
X-Request-ID: {uuid}        # Optional, for tracing
```

### 2.2 Response Envelope

**Success:**
```json
{
  "data": { ... },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-10-09T14:30:00Z"
  }
}
```

**List with Pagination:**
```json
{
  "data": [ ... ],
  "meta": {
    "total": 150,
    "page": 2,
    "per_page": 20,
    "total_pages": 8,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Error:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "name",
        "message": "Name is required",
        "code": "required"
      }
    ]
  },
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

### 2.3 Pagination

- `?page=2&per_page=20` — Page-based
- Default: `page=1`, `per_page=20`
- Maximum: `per_page=100`

### 2.4 Filtering and Sorting

```
?status=ACTIVE&created_after=2026-01-01
?sort=-created_at          # Descending
?sort=name,created_at      # Multiple fields
```

---

## 3. Authentication

### 3.1 MVP: Development Auth

```http
Authorization: Bearer dev-token-{user_id}
```

For MVP, tokens are simple identifiers. Production will use OIDC.

### 3.2 Token Validation

Tokens validated on each request. Invalid/expired tokens return 401.

---

## 4. Endpoint Specifications

### 4.1 Projects

#### POST /api/v1/projects

Create a new project.

**Request:**
```json
{
  "name": "Q3 2026 Reconciliation",
  "description": "Quarterly claims reconciliation"
}
```

**Response (201):**
```json
{
  "data": {
    "id": "proj_a1b2c3d4",
    "name": "Q3 2026 Reconciliation",
    "description": "Quarterly claims reconciliation",
    "status": "CREATED",
    "created_at": "2026-10-09T14:30:00Z",
    "updated_at": "2026-10-09T14:30:00Z",
    "created_by": "user_123"
  }
}
```

**Errors:**
- 400: Invalid name (empty, too long)
- 401: Not authenticated

---

#### GET /api/v1/projects

List projects accessible to user.

**Query Parameters:**
- `status` — Filter by status
- `search` — Search by name
- `page`, `per_page` — Pagination
- `sort` — Sort field (default: `-created_at`)

**Response (200):**
```json
{
  "data": [
    {
      "id": "proj_a1b2c3d4",
      "name": "Q3 2026 Reconciliation",
      "status": "ACTIVE",
      "created_at": "2026-10-09T14:30:00Z",
      "asset_count": 3,
      "reconciliation_count": 1
    }
  ],
  "meta": {
    "total": 25,
    "page": 1,
    "per_page": 20,
    "total_pages": 2
  }
}
```

---

#### GET /api/v1/projects/{id}

Get project details.

**Response (200):**
```json
{
  "data": {
    "id": "proj_a1b2c3d4",
    "name": "Q3 2026 Reconciliation",
    "description": "Quarterly claims reconciliation",
    "status": "ACTIVE",
    "created_at": "2026-10-09T14:30:00Z",
    "updated_at": "2026-10-09T15:45:00Z",
    "created_by": "user_123",
    "stats": {
      "asset_count": 3,
      "claims_mapping_count": 1,
      "subledger_count": 1,
      "reconciliation_count": 2
    }
  }
}
```

---

#### PATCH /api/v1/projects/{id}

Update project.

**Request:**
```json
{
  "name": "Q3 2026 Reconciliation - Final",
  "status": "ARCHIVED"
}
```

**Response (200):** Updated project object

---

### 4.2 Assets

#### POST /api/v1/projects/{project_id}/assets

Upload file to project.

**Request:** `multipart/form-data`
```
file: <binary>
name: optional display name
metadata: {"sheet": "Sheet1"}  # optional JSON
```

**Response (201):**
```json
{
  "data": {
    "id": "asset_x1y2z3",
    "project_id": "proj_a1b2c3d4",
    "name": "claims_mapping.csv",
    "original_filename": "claims_mapping.csv",
    "size_bytes": 15234567,
    "checksum": "sha256:abc123...",
    "format": "CSV",
    "status": "UPLOADED",
    "created_at": "2026-10-09T14:35:00Z"
  }
}
```

**Errors:**
- 400: File too large (>100MB), invalid format
- 404: Project not found

---

#### GET /api/v1/projects/{project_id}/assets

List assets in project.

**Query Parameters:**
- `status` — Filter by status
- `format` — Filter by format

**Response (200):** Array of asset summaries

---

#### GET /api/v1/assets/{id}

Get asset details.

**Response (200):**
```json
{
  "data": {
    "id": "asset_x1y2z3",
    "project_id": "proj_a1b2c3d4",
    "name": "claims_mapping.csv",
    "original_filename": "claims_mapping.csv",
    "size_bytes": 15234567,
    "checksum": "sha256:abc123...",
    "format": "CSV",
    "status": "PARSED",
    "created_at": "2026-10-09T14:35:00Z",
    "metadata": {
      "detected_encoding": "UTF-8",
      "detected_delimiter": ","
    },
    "versions": [
      {
        "id": "ver_m1n2o3",
        "version_number": 1,
        "status": "PROFILED",
        "row_count": 50000,
        "column_count": 15
      }
    ]
  }
}
```

---

#### DELETE /api/v1/assets/{id}

Delete asset and all versions.

**Response (204):** No content

**Errors:**
- 409: Asset in use by active reconciliation

---

### 4.3 Versions

#### GET /api/v1/assets/{asset_id}/versions

List versions of asset.

**Response (200):**
```json
{
  "data": [
    {
      "id": "ver_m1n2o3",
      "asset_id": "asset_x1y2z3",
      "version_number": 1,
      "status": "PROFILED",
      "row_count": 50000,
      "column_count": 15,
      "created_at": "2026-10-09T14:40:00Z",
      "parse_job_id": "job_p1q2r3"
    }
  ]
}
```

---

#### GET /api/v1/versions/{id}

Get version details.

**Response (200):**
```json
{
  "data": {
    "id": "ver_m1n2o3",
    "asset_id": "asset_x1y2z3",
    "version_number": 1,
    "status": "PROFILED",
    "row_count": 50000,
    "column_count": 15,
    "structure": {
      "header_row": 1,
      "data_start_row": 2,
      "column_names": ["CLAIM_NO", "POL_REF", "TXN_DATE", ...]
    },
    "parse_errors": [],
    "created_at": "2026-10-09T14:40:00Z"
  }
}
```

---

#### GET /api/v1/versions/{id}/profile

Get data profile for version.

**Response (200):**
```json
{
  "data": {
    "id": "profile_s1t2u3",
    "version_id": "ver_m1n2o3",
    "row_count": 50000,
    "column_count": 15,
    "columns": [
      {
        "name": "CLAIM_NO",
        "position": 0,
        "data_type": "STRING",
        "null_count": 0,
        "null_percentage": 0.0,
        "distinct_count": 50000,
        "distinct_percentage": 100.0,
        "top_values": [
          {"value": "CLM-00001", "count": 1},
          {"value": "CLM-00002", "count": 1}
        ],
        "length_stats": {
          "min": 9,
          "max": 10,
          "avg": 9.5
        }
      },
      {
        "name": "GROSS_AMT",
        "position": 4,
        "data_type": "DECIMAL",
        "null_count": 5,
        "null_percentage": 0.01,
        "distinct_count": 45000,
        "numeric_stats": {
          "min": 0.0,
          "max": 500000.0,
          "mean": 15234.56,
          "median": 10000.0,
          "std_dev": 25000.0
        }
      }
    ],
    "profiled_at": "2026-10-09T14:42:00Z"
  }
}
```

---

### 4.4 Mappings

#### POST /api/v1/versions/{version_id}/mappings/generate

Generate mapping candidates.

**Request:**
```json
{
  "schema_id": "mvp-claims-v1",
  "options": {
    "min_confidence": 0.3,
    "max_candidates_per_column": 5
  }
}
```

**Response (202):**
```json
{
  "data": {
    "job_id": "job_g1h2i3",
    "status": "PENDING"
  }
}
```

---

#### GET /api/v1/versions/{version_id}/mappings/candidates

List mapping candidates.

**Query Parameters:**
- `status` — Filter: PROPOSED, APPROVED, REJECTED
- `source_column` — Filter by source column
- `min_confidence` — Filter by minimum confidence

**Response (200):**
```json
{
  "data": [
    {
      "id": "cand_j1k2l3",
      "version_id": "ver_m1n2o3",
      "source_column": "CLAIM_NO",
      "target_field": "claim_id",
      "confidence": {
        "total": 0.95,
        "breakdown": {
          "alias_match": 0.25,
          "name_similarity": 0.20,
          "type_compatibility": 0.20,
          "pattern_match": 0.15,
          "position_hint": 0.05,
          "historical_match": 0.10
        }
      },
      "evidence": [
        {
          "type": "ALIAS_MATCH",
          "description": "Source name matches alias 'claim_no'",
          "weight": 0.25
        }
      ],
      "status": "PROPOSED",
      "auto_approve_eligible": true
    }
  ]
}
```

---

#### POST /api/v1/mappings/{id}/approve

Approve a mapping candidate.

**Request:**
```json
{
  "comment": "Verified correct mapping"
}
```

**Response (200):**
```json
{
  "data": {
    "id": "cand_j1k2l3",
    "status": "APPROVED",
    "approved_by": "user_123",
    "approved_at": "2026-10-09T15:00:00Z",
    "approved_mapping_id": "amap_v1w2x3"
  }
}
```

---

#### POST /api/v1/mappings/{id}/reject

Reject a mapping candidate.

**Request:**
```json
{
  "reason": "Incorrect semantic match - this is a policy reference"
}
```

**Response (200):**
```json
{
  "data": {
    "id": "cand_j1k2l3",
    "status": "REJECTED",
    "rejected_by": "user_123",
    "rejected_at": "2026-10-09T15:00:00Z",
    "rejection_reason": "Incorrect semantic match - this is a policy reference"
  }
}
```

---

#### POST /api/v1/versions/{version_id}/mappings/manual

Create manual mapping.

**Request:**
```json
{
  "source_column": "CLM_REF",
  "target_field": "claim_id",
  "transformation": null
}
```

**Response (201):**
```json
{
  "data": {
    "id": "amap_y1z2a3",
    "version_id": "ver_m1n2o3",
    "source_column": "CLM_REF",
    "target_field": "claim_id",
    "origin": "MANUAL",
    "confidence": {
      "total": 1.0,
      "breakdown": {
        "manual_override": 1.0
      }
    },
    "created_by": "user_123",
    "created_at": "2026-10-09T15:05:00Z"
  }
}
```

---

#### POST /api/v1/versions/{version_id}/mappings/finalize

Finalize mapping set for standardization.

**Response (200):**
```json
{
  "data": {
    "id": "mapset_b1c2d3",
    "version_id": "ver_m1n2o3",
    "schema_id": "mvp-claims-v1",
    "mappings": [
      {
        "source_column": "CLAIM_NO",
        "target_field": "claim_id",
        "origin": "APPROVED"
      }
    ],
    "coverage": {
      "mapped_required": 1,
      "total_required": 1,
      "mapped_optional": 12,
      "total_optional": 13,
      "percentage": 0.93
    },
    "finalized_at": "2026-10-09T15:10:00Z"
  }
}
```

---

### 4.5 Schema Templates

#### POST /api/v1/templates

Create a new schema template from finalized mappings.

**Request:**
```json
{
  "name": "Quarterly Claims Template",
  "description": "Standard mapping for quarterly claims files from ABC Re",
  "scope": "PROJECT",
  "project_id": "proj_a1b2c3d4",
  "mapping_set_id": "mapset_b1c2d3",
  "flexibility": "FLEXIBLE",
  "options": {
    "include_transformations": true,
    "generalize_patterns": true
  }
}
```

**Response (201):**
```json
{
  "data": {
    "id": "tmpl_x1y2z3",
    "name": "Quarterly Claims Template",
    "description": "Standard mapping for quarterly claims files from ABC Re",
    "scope": "PROJECT",
    "project_id": "proj_a1b2c3d4",
    "target_schema_id": "mvp-claims-v1",
    "flexibility": "FLEXIBLE",
    "source_signature": {
      "column_patterns": [
        {"name_pattern": "CLAIM_NO|claim_id", "expected_type": "STRING", "required": true},
        {"name_pattern": "GROSS_AMT|gross_amount", "expected_type": "DECIMAL", "required": false}
      ],
      "min_columns": 10,
      "max_columns": 20,
      "signature_hash": "sha256:abc123..."
    },
    "field_mappings": [
      {
        "source_pattern": "CLAIM_NO|claim_id|clm_ref",
        "target_field": "claim_id",
        "match_strategy": "REGEX",
        "confidence_boost": 0.15,
        "priority": 1
      }
    ],
    "rule_count": 12,
    "status": "ACTIVE",
    "usage_count": 0,
    "created_by": "user_123",
    "created_at": "2026-10-09T15:15:00Z"
  }
}
```

---

#### GET /api/v1/templates

List available templates.

**Query Parameters:**
- `scope` — Filter: PROJECT, GLOBAL
- `project_id` — Filter by project (includes GLOBAL templates)
- `target_schema_id` — Filter by target schema
- `status` — Filter: ACTIVE, DEPRECATED, ARCHIVED

**Response (200):**
```json
{
  "data": [
    {
      "id": "tmpl_x1y2z3",
      "name": "Quarterly Claims Template",
      "description": "Standard mapping for quarterly claims files",
      "scope": "PROJECT",
      "project_id": "proj_a1b2c3d4",
      "target_schema_id": "mvp-claims-v1",
      "flexibility": "FLEXIBLE",
      "rule_count": 12,
      "status": "ACTIVE",
      "usage_count": 5,
      "created_at": "2026-10-09T15:15:00Z"
    }
  ],
  "meta": {
    "total": 3
  }
}
```

---

#### GET /api/v1/templates/{id}

Get template details.

**Response (200):**
```json
{
  "data": {
    "id": "tmpl_x1y2z3",
    "name": "Quarterly Claims Template",
    "description": "Standard mapping for quarterly claims files",
    "scope": "PROJECT",
    "project_id": "proj_a1b2c3d4",
    "target_schema_id": "mvp-claims-v1",
    "flexibility": "FLEXIBLE",
    "source_signature": { ... },
    "field_mappings": [ ... ],
    "rule_count": 12,
    "status": "ACTIVE",
    "usage_count": 5,
    "created_by": "user_123",
    "created_at": "2026-10-09T15:15:00Z",
    "updated_at": "2026-10-09T15:15:00Z"
  }
}
```

---

#### PATCH /api/v1/templates/{id}

Update template.

**Request:**
```json
{
  "name": "Quarterly Claims Template v2",
  "description": "Updated description",
  "status": "DEPRECATED"
}
```

**Response (200):** Updated template object

---

#### DELETE /api/v1/templates/{id}

Delete template (sets status to ARCHIVED).

**Response (204):** No content

---

#### POST /api/v1/versions/{version_id}/templates/match

Find templates that match a version's structure.

**Request:**
```json
{
  "target_schema_id": "mvp-claims-v1",
  "min_match_score": 0.7
}
```

**Response (200):**
```json
{
  "data": [
    {
      "template_id": "tmpl_x1y2z3",
      "template_name": "Quarterly Claims Template",
      "match_score": 0.92,
      "matched_columns": 11,
      "total_columns": 12,
      "unmatched_source_columns": ["NEW_FIELD"],
      "unmatched_template_rules": ["old_field_pattern"],
      "recommendation": "APPLY"
    }
  ]
}
```

**Recommendation values:**
- `APPLY` — High match, recommended
- `REVIEW` — Moderate match, review suggested
- `SKIP` — Low match, likely not applicable

---

#### POST /api/v1/versions/{version_id}/templates/apply

Apply a template to generate mapping candidates.

**Request:**
```json
{
  "template_id": "tmpl_x1y2z3",
  "options": {
    "auto_approve_high_confidence": false,
    "min_confidence_for_auto": 0.95,
    "merge_with_existing": true
  }
}
```

**Response (200):**
```json
{
  "data": {
    "mapping_set_id": "mapset_d4e5f6",
    "applied_rules": 11,
    "total_rules": 12,
    "candidates_created": 11,
    "candidates_boosted": 8,
    "average_confidence": 0.89,
    "application_id": "app_a1b2c3"
  }
}
```

---

### 4.6 Standardization

#### POST /api/v1/versions/{version_id}/standardize

Start standardization job.

**Request:**
```json
{
  "mapping_set_id": "mapset_b1c2d3",
  "options": {
    "preserve_unmapped": true,
    "strict_type_coercion": false
  }
}
```

**Response (202):**
```json
{
  "data": {
    "job_id": "job_e1f2g3",
    "status": "PENDING"
  }
}
```

---

#### GET /api/v1/claims-mappings/{id}

Get standardized claims mapping.

**Response (200):**
```json
{
  "data": {
    "id": "cm_h1i2j3",
    "version_id": "ver_m1n2o3",
    "schema_id": "mvp-claims-v1",
    "row_count": 49995,
    "valid_rows": 49990,
    "error_rows": 5,
    "columns": ["claim_id", "policy_id", "transaction_date", ...],
    "standardization_job_id": "job_e1f2g3",
    "created_at": "2026-10-09T15:15:00Z"
  }
}
```

---

#### GET /api/v1/claims-mappings/{id}/data

Get standardized data.

**Query Parameters:**
- `page`, `per_page` — Pagination (default per_page=100, max 1000)
- `columns` — Comma-separated column filter

**Response (200):**
```json
{
  "data": {
    "columns": ["claim_id", "policy_id", "gross_amount"],
    "rows": [
      ["CLM-00001", "POL-A001", "10000.00"],
      ["CLM-00002", "POL-A002", "25000.00"]
    ]
  },
  "meta": {
    "total": 49990,
    "page": 1,
    "per_page": 100
  }
}
```

---

### 4.6 Subledgers

#### POST /api/v1/projects/{project_id}/subledgers

Create subledger from asset.

**Request:**
```json
{
  "asset_id": "asset_a1b2c3",
  "name": "GL Subledger Q3",
  "mapping_set_id": "mapset_d4e5f6"
}
```

**Response (202):**
```json
{
  "data": {
    "job_id": "job_k1l2m3",
    "subledger_id": "sl_n1o2p3",
    "status": "PENDING"
  }
}
```

---

#### GET /api/v1/subledgers/{id}

Get subledger details.

**Response (200):**
```json
{
  "data": {
    "id": "sl_n1o2p3",
    "project_id": "proj_a1b2c3d4",
    "name": "GL Subledger Q3",
    "source_asset_id": "asset_a1b2c3",
    "row_count": 48500,
    "status": "READY",
    "created_at": "2026-10-09T15:20:00Z"
  }
}
```

---

### 4.7 Reconciliation

#### POST /api/v1/reconciliations

Create and start reconciliation.

**Request:**
```json
{
  "project_id": "proj_a1b2c3d4",
  "claims_mapping_id": "cm_h1i2j3",
  "subledger_id": "sl_n1o2p3",
  "name": "Q3 2026 Initial Reconciliation",
  "config": {
    "key_columns": ["claim_id"],
    "measure_column": "net_amount",
    "group_by": ["currency", "reporting_period"],
    "variance_thresholds": {
      "absolute": {
        "enabled": true,
        "value": 100.00
      },
      "percentage": {
        "enabled": true,
        "value": 0.01
      },
      "mode": "OR"
    },
    "diagnostics": {
      "enabled": true,
      "checks": ["D001", "D003", "D004", "D005", "D018"]
    }
  }
}
```

**Response (202):**
```json
{
  "data": {
    "id": "rec_q1r2s3",
    "job_id": "job_t1u2v3",
    "status": "QUEUED"
  }
}
```

---

#### GET /api/v1/reconciliations/{id}

Get reconciliation details.

**Response (200):**
```json
{
  "data": {
    "id": "rec_q1r2s3",
    "project_id": "proj_a1b2c3d4",
    "name": "Q3 2026 Initial Reconciliation",
    "status": "SUCCEEDED",
    "claims_mapping_id": "cm_h1i2j3",
    "subledger_id": "sl_n1o2p3",
    "config": { ... },
    "summary": {
      "total_groups": 990,
      "matched": 890,
      "within_tolerance": 35,
      "unreconciled": 65,
      "reported_total": "15234567.89",
      "subledger_total": "15234067.89",
      "net_variance": "-500.00",
      "execution_time_ms": 45000
    },
    "started_at": "2026-10-09T15:30:00Z",
    "completed_at": "2026-10-09T15:30:45Z"
  }
}
```

---

#### GET /api/v1/reconciliations/{id}/variances

Get variance records.

**Query Parameters:**
- `status` — Filter: MATCH, WITHIN_TOLERANCE, UNRECONCILED
- `min_variance` — Minimum absolute variance
- `sort` — Sort field (default: `-absolute_variance`)

**Response (200):**
```json
{
  "data": [
    {
      "id": "var_w1x2y3",
      "reconciliation_id": "rec_q1r2s3",
      "key_values": {
        "claim_id": "CLM-00051"
      },
      "group_values": {
        "currency": "USD",
        "reporting_period": "2026-Q3"
      },
      "reported_value": "15000.00",
      "subledger_value": "14500.00",
      "absolute_variance": "-500.00",
      "percentage_variance": "-0.0333",
      "status": "UNRECONCILED",
      "thresholds_applied": {
        "absolute_passed": false,
        "percentage_passed": false
      }
    }
  ],
  "meta": {
    "total": 65,
    "page": 1,
    "per_page": 20
  }
}
```

---

#### GET /api/v1/reconciliations/{id}/diagnostics

Get diagnostic findings.

**Query Parameters:**
- `severity` — Filter by severity
- `check_id` — Filter by check ID

**Response (200):**
```json
{
  "data": [
    {
      "id": "diag_z1a2b3",
      "reconciliation_id": "rec_q1r2s3",
      "check_id": "D001",
      "category": "STRUCTURAL",
      "severity": "INFO",
      "message": "Row count difference: Claims Mapping has 1000 rows, Subledger has 980 rows",
      "metrics": {
        "reported_rows": 1000,
        "subledger_rows": 980,
        "difference": 20
      },
      "evidence": [],
      "created_at": "2026-10-09T15:30:40Z"
    },
    {
      "id": "diag_c3d4e5",
      "reconciliation_id": "rec_q1r2s3",
      "check_id": "D003",
      "category": "COMPLETENESS",
      "severity": "WARNING",
      "message": "20 records in Claims Mapping not found in Subledger",
      "metrics": {
        "missing_count": 20
      },
      "evidence": [
        {"key": "CLM-00981", "claim_id": "CLM-00981"},
        {"key": "CLM-00982", "claim_id": "CLM-00982"}
      ],
      "created_at": "2026-10-09T15:30:42Z"
    }
  ]
}
```

---

#### POST /api/v1/reconciliations/{id}/report

Generate reconciliation report.

**Request:**
```json
{
  "format": "JSON",
  "sections": ["summary", "exceptions", "diagnostics"],
  "include_evidence": true
}
```

**Response (200):**
```json
{
  "data": {
    "report_id": "rpt_f1g2h3",
    "reconciliation_id": "rec_q1r2s3",
    "format": "JSON",
    "content": {
      "summary": {
        "title": "Q3 2026 Initial Reconciliation",
        "generated_at": "2026-10-09T16:00:00Z",
        "totals": { ... },
        "match_rate": 0.934
      },
      "exceptions": [ ... ],
      "diagnostics": [ ... ]
    },
    "generated_at": "2026-10-09T16:00:05Z"
  }
}
```

---

### 4.8 Jobs

#### GET /api/v1/jobs/{id}

Get job status.

**Response (200):**
```json
{
  "data": {
    "id": "job_t1u2v3",
    "type": "RECONCILIATION",
    "status": "RUNNING",
    "progress": {
      "current_step": "variance_calculation",
      "total_steps": 5,
      "percentage": 60
    },
    "started_at": "2026-10-09T15:30:00Z",
    "estimated_completion": "2026-10-09T15:30:45Z"
  }
}
```

**Job Statuses:**
- `PENDING` — Queued, not started
- `RUNNING` — In progress
- `SUCCEEDED` — Completed successfully
- `FAILED` — Completed with error
- `CANCELLED` — User cancelled

---

#### GET /api/v1/projects/{project_id}/jobs

List jobs for project.

**Query Parameters:**
- `type` — Filter by job type
- `status` — Filter by status

---

### 4.9 Schemas

#### GET /api/v1/schemas

List available schemas.

**Response (200):**
```json
{
  "data": [
    {
      "id": "mvp-claims-v1",
      "name": "MVP Claims Mapping Schema",
      "version": "1.0.0",
      "standard": "CUSTOM",
      "field_count": 14,
      "required_field_count": 1
    }
  ]
}
```

---

#### GET /api/v1/schemas/{id}

Get schema details with all fields.

**Response (200):**
```json
{
  "data": {
    "id": "mvp-claims-v1",
    "name": "MVP Claims Mapping Schema",
    "version": "1.0.0",
    "standard": "CUSTOM",
    "fields": [
      {
        "name": "claim_id",
        "type": "STRING",
        "required": true,
        "aliases": ["claim_number", "claim_no", "clm_id"],
        "category": "IDENTIFIER",
        "description": "Unique claim identifier"
      }
    ]
  }
}
```

---

### 4.10 Lineage

#### GET /api/v1/lineage/{artifact_type}/{artifact_id}

Get lineage for an artifact.

**Path Parameters:**
- `artifact_type` — One of: variance, claims_mapping, subledger
- `artifact_id` — Artifact ID

**Query Parameters:**
- `depth` — Traversal depth (default: 3, max: 10)
- `direction` — upstream, downstream, both (default: both)

**Response (200):**
```json
{
  "data": {
    "artifact": {
      "type": "variance",
      "id": "var_w1x2y3"
    },
    "upstream": [
      {
        "type": "claims_mapping_row",
        "id": "cm_h1i2j3:51",
        "source_row_number": 51
      },
      {
        "type": "source_version_row",
        "id": "ver_m1n2o3:51",
        "source_row_number": 51
      },
      {
        "type": "source_asset",
        "id": "asset_x1y2z3",
        "filename": "claims_mapping.csv"
      }
    ],
    "downstream": []
  }
}
```

---

### 4.11 Health

#### GET /health

Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "storage": "ok",
    "queue": "ok"
  },
  "timestamp": "2026-10-09T16:00:00Z"
}
```

---

## 5. Error Codes

### 5.1 Global Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | State conflict |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

### 5.2 Domain Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `FILE_TOO_LARGE` | 400 | File exceeds 100MB |
| `UNSUPPORTED_FORMAT` | 400 | File format not supported |
| `PARSE_FAILED` | 422 | Could not parse file |
| `MAPPING_INCOMPLETE` | 422 | Required fields unmapped |
| `SCHEMA_NOT_FOUND` | 404 | Canonical schema not found |
| `RECONCILIATION_FAILED` | 422 | Reconciliation execution failed |
| `JOB_STILL_RUNNING` | 409 | Cannot modify while job running |

---

## 6. Rate Limiting (Post-MVP)

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1696867200
```

---

## 7. Webhooks (Post-MVP)

```json
{
  "event": "job.completed",
  "data": {
    "job_id": "job_t1u2v3",
    "type": "RECONCILIATION",
    "status": "SUCCEEDED"
  },
  "timestamp": "2026-10-09T15:30:45Z"
}
```

---

## 8. OpenAPI Schema

Full OpenAPI 3.1.0 specification available at:
- **Development:** `http://localhost:8000/openapi.json`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
