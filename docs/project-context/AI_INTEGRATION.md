# AI Integration (mapping + money-column relations)

Principle (ADR-002): **deterministic first, AI second.** AI only *proposes*; Python validates, measures and decides what is checked. Every AI call is optional, bounded, and visible.

## Configuration (`backend/.env`, see `.env.example`)

| Variable | Meaning |
|---|---|
| `LLM_ENABLED` | `true` to allow AI calls |
| `LLM_PROVIDER` | `dial` (Azure-style DIAL proxy), `azure`, `openai`, `anthropic`, `openai_compatible` |
| `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_VERSION`, `LLM_API_KEY` | endpoint + credentials |
| `LLM_TIMEOUT_SECONDS` | hard wait limit per call (default 30; DIAL setup uses 60) |
| `LLM_MAX_TOKENS`, `LLM_REASONING_EFFORT` | token budget (reasoning models spend part of it on hidden reasoning) / `low` keeps gpt-5 fast |

Tests force `LLM_ENABLED=false` (`tests/conftest.py`) so the suite never reaches a model.

## Where AI is used

1. **Mapping** (`mapping/ai_assist.py`, `mapping/service.py::run_mapping_ai`). After the deterministic stages, one batched call covers columns that were ambiguous (header fits several fields) or matched nothing. The model gets: target fields (type, aliases, money role), already-settled fields, each column's header / position / neighbours / profile / sample values / deterministic candidates. Replies are validated (real field, type-compatible, not already taken, one column per field) and become **PROPOSED** candidates with `ai_suggestion` evidence - a reviewer still approves. Endpoints: `POST .../mappings/generate?use_ai=false` to skip, `POST .../mappings/ai-assist` to retry.
2. **Money-column relations** (`financial_checks/relations_service.py`). After treaty figures the user declares relations (`target = ±column × factor …`, factors = treaty figures or numbers). Sources: typed by the user, **standard** set (deterministic), or **AI suggestions** (`POST .../money-relations/ai-suggest`). Every AI proposal is re-measured against all rows (agreement %) and dropped if the data does not support it; nothing is saved until the user adds it. `run_financial_checks` evaluates the declared set (`money_rules/relations.py`); with none declared the built-in A/B/C rules run as before. Traps, FX, totals and sign checks always run.

## Transparency + failure behaviour

* `GET /ai/status` - usable? which model? if not, why.
* `GET /processing-runs/{id}/ai/activity` - every call (`ai_interactions`): purpose, status, message, model, latency, items sent/resolved.
* Statuses: `ok`, `disabled`, `skipped`, `timeout`, `rate_limited`, `auth_error`, `unavailable`, `bad_response`, `invalid_request`, `error`.
* AI problems are **results, never HTTP errors**: mapping, relations and checks continue deterministically. The UI shows a progress box (elapsed / timeout) during calls and a notice with the reason and a retry where retrying can help.
* Audit: each call writes an `ai.mapping` / `ai.money_relations` event (counts + status only; payloads are not stored).

## User-supplied API key (Settings -> AI connection)

Header **Settings** opens a dialog where a user gives the app their own API key. It always uses the app's existing provider configuration (same provider/model/endpoint); only the secret is replaced. If the server has AI switched off, the user's key still works against the default DIAL configuration (`ai/credentials.py::DEFAULT_PROVIDER_CONFIG`).

* `GET /ai/status`, `GET|PUT|DELETE /me/ai-key`, `POST /me/ai-key/test`. `PUT` verifies the key with a real minimal call and saves it only if the provider accepts it (`skip_test` stores it unverified, offered only when the provider was unreachable).
* Storage: `user_ai_credentials`, Fernet-encrypted. Master key = `SECRETS_KEY` (env) or an auto-generated `storage/.secrets/fernet.key`. Back this up / set `SECRETS_KEY` in production: losing it means stored keys read as "no key".
* The key is write-only: no endpoint, log or audit event contains it; the UI only ever receives its last 4 characters.
* Precedence per request: the acting user's key -> the server's key -> no AI. Keys are per user (dev identity), so switching identity switches the key.
