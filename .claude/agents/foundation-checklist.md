# Foundation Agent Checklist

- [ ] Inspect `backend/src/bordereaux/models` for SQLAlchemy models
- [ ] Verify `alembic` migrations in `backend/migrations/versions`
- [ ] Confirm `storage` module supports immutable assets
- [ ] Implement authentication and RBAC hooks in `backend/src/bordereaux/auth`
- [ ] Add audit/logging hooks in `backend/src/bordereaux/audit`
- [ ] Wire async job queue in `backend/src/bordereaux/jobs`
- [ ] Run backend tests: `pytest -m unit`
- [ ] Document setup steps in `.claude/agents/foundation-notes.md`
