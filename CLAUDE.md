# Bordereaux Intelligence Platform

Enterprise reinsurance data standardization and reconciliation system.

## Project Status

**Phase:** Pre-Implementation (Specifications Complete)

All specifications are in `docs/project-context/`. Read them before implementing.

## Quick Start

```bash
# Backend (Python 3.11+)
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.main:app --reload

# Frontend (Node 20+)
cd frontend
npm install
npm run dev
```

## Architecture

**Modular monolith** with async workers. See `docs/project-context/ARCHITECTURE.md`.

Key principle: **"Deterministic first, AI second"** — Python handles all calculations, LLM only interprets.

## Specification Documents

| Document | Purpose |
|----------|---------|
| `PROJECT_BRIEF.md` | Executive summary |
| `REQUIREMENTS.md` | All functional/non-functional requirements |
| `DOMAIN_MODEL.md` | Entities, aggregates, events |
| `ARCHITECTURE.md` | System design |
| `MODULE_CONTRACTS.md` | Python Protocol interfaces |
| `API_SPECIFICATION.md` | REST API endpoints |
| `DATA_MODEL.md` | Database schema |
| `MVP_SCOPE.md` | What's in/out of MVP |
| `MVP_ACCEPTANCE_CRITERIA.md` | Acceptance tests |
| `TEST_STRATEGY.md` | Testing approach |
| `SECURITY_AND_AUDIT.md` | Auth, RBAC, audit |
| `ADR/` | Architecture decisions |

## Development Agents

Three specialized agents implement this project:

1. **Foundation Agent** — Core infrastructure (models, storage, auth, jobs)
2. **Pipeline Agent** — Data processing (ingestion → reconciliation)
3. **Frontend Agent** — React/TypeScript UI

Agent configurations in `.claude/agents/`.

## Key Decisions (ADRs)

- **ADR-001:** Modular Monolith (single deploy, module boundaries)
- **ADR-002:** Deterministic First (Python math, LLM interprets)
- **ADR-003:** Immutable Artifacts (versioned, never modified)
- **ADR-004:** Confidence Scoring (weighted evidence)
- **ADR-005:** LLM Provider Abstraction (Claude initial, swappable)
- **ADR-006:** Async Job Processing (database-backed queue)

## Confidence Scoring Weights

When implementing mapping candidate scoring:

| Evidence | Weight |
|----------|--------|
| Semantic | 30% |
| Value | 25% |
| Context | 20% |
| Layout | 10% |
| AI | 15% |

Revised: the Relationship and Historical buckets were removed (no column relationships exist at mapping time;
the arithmetic relationship check now runs in financial checks after treaty figures, and nothing is learned
from past manual mappings). A source header that is a data-dictionary term of the field it maps to scores 100%.
Before mapping, the user picks the target format: the default data dictionary or their own final columns.

## Schema Templates

Users can save approved mappings as reusable templates:
- **Create**: From finalized mapping set → extract patterns → save as template
- **Match**: New file uploaded → compare structure → suggest matching templates
- **Apply**: Selected template → boost confidence scores → faster mapping approval

Template scopes: `PROJECT` (visible only in creating project) or `GLOBAL` (available everywhere)

Flexibility levels:
- `STRICT` — Exact column name match
- `FLEXIBLE` — Fuzzy matching (≥80% similarity)
- `LOOSE` — Type + position matching

## MVP Diagnostic Checks (20 of 33)

D001, D002, D003, D004, D005, D006, D007, D008, D009, D010, D011, D013, D015, D016, D018, D020, D023, D024, D025, D027

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific category
pytest -m unit
pytest -m integration
pytest -m golden
```

Golden dataset in `tests/fixtures/golden/` — 1000-row claims mapping, 980-row subledger.

## File Structure

```
src/
├── core/           # Shared kernel
├── storage/        # File storage
├── auth/           # Authentication
├── jobs/           # Async processing
├── audit/          # Audit logging
├── ingestion/      # File handling
├── profiling/      # Data analysis
├── mapping/        # Schema mapping
├── standardization/# Transformation
├── reconciliation/ # Comparison
├── api/            # HTTP endpoints
└── models/         # SQLAlchemy models

frontend/
├── src/
│   ├── api/        # Generated client
│   ├── components/ # UI components
│   ├── pages/      # Page layouts
│   ├── hooks/      # Custom hooks
│   └── stores/     # State management
```

## Do Not

- Skip reading specifications before implementing
- Modify raw uploaded files (immutable)
- Use randomness in calculations
- Auto-apply LLM suggestions without user approval
- Implement features outside MVP scope
- Skip audit logging for state changes
