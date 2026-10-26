# Pipeline Agent Checklist

- [ ] Inspect `backend/src/bordereaux/ingestion` for file ingestion flows
- [ ] Verify cleaning pipeline in `backend/src/bordereaux/cleaning`
- [ ] Review profiling in `backend/src/bordereaux/profiling`
- [ ] Implement mapping candidates scoring in `backend/src/bordereaux/mapping`
- [ ] Validate standardization in `backend/src/bordereaux/standardization`
- [ ] Run pipeline unit tests: `pytest tests/unit -m pipeline`
- [ ] Produce integration tests for end-to-end ingestion
- [ ] Document pipeline assumptions in `.claude/agents/pipeline-notes.md`
