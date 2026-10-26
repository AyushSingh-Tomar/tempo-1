Bordereaux Foundation Agent notes

Summary:
The Foundation Agent is responsible for core infra: storage adapters, async job framework, audit logging, and DB models/migrations. This scan uncovered storage implementations, model files, migrations, audit classes, and jobs wiring that need verification and alignment with MODULE_CONTRACTS.md.

Actionable next steps:
- Verify StorageService implementations implement all methods declared in docs/project-context/MODULE_CONTRACTS.md and add missing methods or adapters.
- Ensure every SQLAlchemy model in src/bordereaux/models has a corresponding migration in backend/migrations/versions; create missing migrations.
- Confirm AuditService provides `log` and `query` with expected parameters and add tests to assert audit logging on state changes.
- Wire an app-wide async queue (Redis/Celery/asyncio wrapper) if not present; add docs and initialization code.
- Triage TODO/FIXME items and replace NotImplemented placeholders in high-priority modules (storage, audit, jobs).
- Add unit tests for storage adapters and job claiming logic to reach >=90% coverage for foundation modules.
