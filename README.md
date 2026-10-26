# Bordereaux Processing Accelerator — Iteration 1

A step-by-step workflow for processing a reinsurance bordereaux file:

```
Upload → Validate → Clean/Standardize → Review → Confirm → Map Columns → Review Mappings
→ Treaty Figures → Validate Figures → Apply Money-Column Rules → Review Discrepancies
→ Override/Resolve → Generate Reports → Download
```

Backend: Python/FastAPI/SQLAlchemy (SQLite for this iteration). Frontend: React/TypeScript/Vite.
See `docs/project-context/` for the broader platform specification this iteration builds on, and
`Initial_iteration_implementation_command.md` for the detailed step-by-step requirements this
iteration implements.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ (3.12 used in development) | [python.org/downloads](https://www.python.org/downloads/) |
| Node.js | 20+ | npm comes with it |

**Windows note:** if `python` / `pip` aren't recognized after installing, either reopen your
terminal (installer PATH changes need a fresh shell), or use the launcher: `py -3.12 ...`, or call
the interpreter by its full install path (shown at the end of the Python installer, typically
`%LOCALAPPDATA%\Programs\Python\Python312\python.exe` for a per-user install). All commands below
assume plain `python`/`pip` resolve correctly in your shell — substitute the full path if not.

---

## 2. Backend setup

```powershell
cd backend
python -m venv venv

# Activate the venv (pick one):
.\venv\Scripts\Activate.ps1      # PowerShell
venv\Scripts\activate.bat        # cmd.exe
source venv/bin/activate         # macOS/Linux

pip install -e ".[dev]"

# Create your local .env (defaults are fine to start)
copy .env.example .env            # Windows
cp .env.example .env              # macOS/Linux

# Apply database migrations (creates backend/bordereaux.db)
alembic upgrade head
```

> If your shell doesn't keep the venv activated between commands (e.g. some CI runners, or if
> you're scripting this), call the venv's own executables directly instead of relying on
> activation: `.\venv\Scripts\python.exe -m alembic upgrade head`, etc. — every command below has
> an implicit `python -m` form that works the same way.

### Run the backend

```powershell
uvicorn bordereaux.main:app --reload
```

- API base: `http://localhost:8000/api/v1`
- Health check: `http://localhost:8000/health`
- Interactive API docs: `http://localhost:8000/docs`

### Run backend tests

```powershell
pytest                                              # all tests
pytest -m unit                                       # unit tests only
pytest -m integration                                # integration tests (full happy-path run, migrations)
pytest --cov=src/bordereaux --cov-report=html        # coverage report -> htmlcov/index.html
```

---

## 3. Frontend setup

```powershell
cd frontend
npm install

copy .env.example .env.local      # Windows
cp .env.example .env.local        # macOS/Linux
```

Edit `.env.local` if your backend isn't on the default `http://localhost:8000`.

### Run the frontend

```powershell
npm run dev
```

Open `http://localhost:5173`. The backend must be running (step 2) for the app to do anything
useful — the UI calls it directly.

### Run frontend tests

```powershell
npm test            # vitest
npm run build        # type-check + production build
```

---

## 4. Authentication (development only)

This iteration uses a **development-only** auth provider — there is no real login. Requests carry
a header of the form:

```
Authorization: Bearer dev-{any-identifier}-{role}
```

where `{role}` is one of: `admin`, `project_owner`, `analyst`, `reviewer`, `viewer`. The first
request with a given identifier auto-creates that user. Example: `dev-jane-analyst`.

The frontend has a **"Dev identity" switcher** in the app header for changing the active token
without editing config — use it to test role-based behavior (e.g. an `analyst` can upload and
propose mappings but cannot approve them or override a discrepancy; a `reviewer`, `project_owner`,
or `admin` can).

| Role | Can do |
|---|---|
| `analyst` | Create projects, upload files, run cleaning, generate/manually map columns, submit treaty figures, run financial checks |
| `reviewer` | Approve/reject mapping candidates, override discrepancies |
| `project_owner`, `admin` | Everything |
| `viewer` | Read-only |

---

## 5. Walking through the workflow

With both servers running, either use the frontend UI at `http://localhost:5173`, or drive the API
directly. A full example using `curl` (PowerShell: use `curl.exe`, not the `curl` alias):

```bash
# 1. Create a project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer dev-jane-analyst" -H "Content-Type: application/json" \
  -d '{"name": "Q3 2026 Reconciliation"}'
# -> note the returned "id" as PROJECT_ID

# 2. Upload a bordereaux file (multi-sheet workbooks require sheet_name)
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/processing-runs" \
  -H "Authorization: Bearer dev-jane-analyst" \
  -F "file=@/path/to/bordereaux.xlsx"
# -> note the returned run "id" as RUN_ID, and "available_sheets" if present

# 3. Validate (pass sheet_name if the upload response listed multiple sheets)
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/validate" \
  -H "Authorization: Bearer dev-jane-analyst" -H "Content-Type: application/json" \
  -d '{"sheet_name": "Bordereaux"}'

# 4. Clean, then review and acknowledge
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/clean" -H "Authorization: Bearer dev-jane-analyst"
curl "http://localhost:8000/api/v1/processing-runs/$RUN_ID/cleaning-result" -H "Authorization: Bearer dev-jane-analyst"
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/cleaning/acknowledge" -H "Authorization: Bearer dev-jane-analyst"

# 5. Generate and review column mappings
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/mappings/generate" -H "Authorization: Bearer dev-jane-analyst"
curl "http://localhost:8000/api/v1/processing-runs/$RUN_ID/mappings/candidates" -H "Authorization: Bearer dev-jane-analyst"
# approve each candidate (requires reviewer/project_owner/admin - "separation of duties"):
curl -X POST "http://localhost:8000/api/v1/mappings/$CANDIDATE_ID/approve" -H "Authorization: Bearer dev-jane-reviewer" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/mappings/finalize" -H "Authorization: Bearer dev-jane-reviewer"

# 6. Submit treaty figures (percentages are fractions: 0.25 means 25%)
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/treaty-figures" \
  -H "Authorization: Bearer dev-jane-analyst" -H "Content-Type: application/json" \
  -d '{"commission_pct": "0.25", "tax_pct": "0.12", "cession_pct": "0.40", "order_pct": "0.20"}'

# 7. Run financial checks and review discrepancies
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/financial-checks/run" -H "Authorization: Bearer dev-jane-analyst"
curl "http://localhost:8000/api/v1/processing-runs/$RUN_ID/discrepancies" -H "Authorization: Bearer dev-jane-analyst"
# override one if needed (requires reviewer/project_owner/admin):
curl -X POST "http://localhost:8000/api/v1/discrepancies/$DISCREPANCY_ID/override" \
  -H "Authorization: Bearer dev-jane-reviewer" -H "Content-Type: application/json" \
  -d '{"reason": "Known timing difference, confirmed with cedant"}'

# 8. Proceed to reports, generate, and download
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/discrepancies/proceed" -H "Authorization: Bearer dev-jane-analyst"
curl -X POST "http://localhost:8000/api/v1/processing-runs/$RUN_ID/reports/generate" -H "Authorization: Bearer dev-jane-analyst"
curl "http://localhost:8000/api/v1/processing-runs/$RUN_ID/download/processed_file" -H "Authorization: Bearer dev-jane-analyst" -o processed.csv
curl "http://localhost:8000/api/v1/processing-runs/$RUN_ID/download/audit_report" -H "Authorization: Bearer dev-jane-analyst" -o audit_report.json
```

Sample files to try this with: `Initial provided Info/Test_files/test_integration_realistic.xlsx`
(the primary end-to-end fixture) and its siblings in the same folder, each targeting a specific
stage (structural cleaning, mapping, money-column resolution).

---

## 6. Project structure

```
backend/
  src/bordereaux/
    core/, storage/, auth/, jobs/, audit/, models/   # foundation layer
    money_rules/                                      # deterministic money-column-resolution engine
    schemas/                                           # canonical bordereaux schema (YAML)
    runs/                                              # processing-run state machine
    ingestion/, cleaning/, profiling/, mapping/,
    standardization/, financial_checks/, reporting/   # pipeline
    api/v1/routes/                                     # HTTP endpoints
  migrations/        # Alembic
  tests/

frontend/
  src/
    api/              # typed HTTP client
    hooks/            # TanStack Query hooks
    components/       # shell, mapping, treaty, discrepancies, reports, common
    pages/            # routed pages, including the per-step wizard screens
  tests/
```

---

## 7. Known limitations (iteration 1)

- Jobs (cleaning, mapping generation, financial checks, report generation) run synchronously
  in-process rather than through an async queue — fine for the file sizes this iteration targets,
  not yet wired for background workers.
- No real authentication — the dev token scheme above is explicitly not for production.
- Not built in this iteration: schema templates, treaty clause/state management, subledger
  reconciliation.
