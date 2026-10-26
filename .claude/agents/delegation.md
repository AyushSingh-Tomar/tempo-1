# Agent Delegation Plan

- Foundation Agent: implement core models, auth, storage, jobs, audit
- Pipeline Agent: implement ingestion, cleaning, profiling, mapping, reconciliation
- Frontend Agent: implement UI, tests, API client, mapping review UX

Delegation approach:
- Each agent will run a repo scan and update their checklist file when tasks are complete.
- We'll track progress in the top-level TODOs and update `.claude/agents/*.md` notes.

Next steps:
1. Foundation Agent: scan backend and start implementing missing hooks.
2. Pipeline Agent: scan pipeline modules and run unit tests.
3. Frontend Agent: run `npm install` and run UI tests.
