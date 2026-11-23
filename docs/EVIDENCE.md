# Evidence

## Phase 1 — Foundation clean-up

- Foundation and error path tests: `tests/test_phase1.py` (health, readiness, idempotency validation, duplicate replay, 409 on reused key with different payload, request validation formatting, unhandled error formatting without tracebacks, correlation_id context injection)
- Secret scanning & log redaction test: `tests/test_secrets.py` (repository token scanner, token redaction, captured JSON log redaction of tokens and webhook secrets)
- Health/readiness endpoints: `app/routes.py`
- Correlation and Idempotency enforcement: `app/middleware.py`, `app/routes.py` (catches `IntegrityError` for safe concurrency race resolution, enforces 409 `IDEMPOTENCY_KEY_REUSED`)
- Standard error formatting: `app/main.py` (all errors mapped to `{"error": {"code", "message", "retryable", "details"}}`, RequestValidationError -> `REQUEST_INVALID`, unhandled Exception -> `INTERNAL_ERROR`)
- Structured logging & contextvars: `app/logging.py` (IncuBrixJsonFormatter with `timestamp, level, message, job_id, correlation_id`, SecretRedactionFilter)
- Config settings: `app/config.py`, `.env.example`
- Database job record: `app/models.py`, `alembic/versions/20261122_001_create_jobs.py`

## Phase 2 — Connector Contract and Registry

- 9 connector YAML manifests updated to Appendix A schema: `connectors/*.yaml` (key, version, tier, auth, surfaces[spec], rate_limits.per_connection, capabilities as list, error_map with string keys)
- Error codes: `app/connectors/errors.py` (ConnectorError with code/message/retryable/details/status_code, all shared error codes)
- Registry: `app/connectors/registry.py` (loads all 9 connectors, capability check, kill-switch via DISABLED_CONNECTORS, singleton)
- Connector HTTP router: `app/connectors/router.py` (manifest-driven, _handle_connector_call, all 7 methods)
- Contract test suite: `tests/contract/test_contract.py` (10 tests: manifest schema × 9, instantiation × 9, endpoint contract, unsupported method → 400, kill switch → 503, unknown → 404)
- Phase 2 endpoint tests: `tests/test_phase2.py` (validate, publish, get_status, delete contracts for Discourse)

## Phase 3 — Core Connectors

- Core connector tests: `tests/test_phase3.py` (all 6 connectors: validate/publish/get_status/delete, assisted build_assist_pack)
- All 6 connector implementations: `app/connectors/discourse.py`, `lemmy.py`, `ghost.py`, `devto.py`, `webhook.py`, `assisted.py`
- Simulation base: `app/connectors/simulation.py`
- Connector manifests: `connectors/*.yaml` (all 9 connectors with full Appendix A schema)

## Phase 4 — Rules Engine (also covers reliability tests)

- Rules engine tests: `tests/test_phase4.py` (19 tests including rules fixture runner, rescheduled action, frequency cap, promo, link policy, AI disclosure, reliability)
- 42-case rules fixture: `tests/fixtures/rules_cases.json` (covers all rule codes; zero misses asserted)
- Rules engine: `app/rules.py` (pure fail-closed, `action: allowed|blocked|rescheduled`, `scheduled_for` on rescheduled, `FREQUENCY_CAP`, `SELF_PROMOTION_NOT_ALLOWED`, `LINK_POLICY_VIOLATION`, `AI_DISCLOSURE_REQUIRED`, `AMBIGUOUS_RULE:*`)
- Retry and 429 policy: `app/reliability.py` (RetryPolicy: exponential backoff, bounded max, 429 Retry-After, stop after 5 × PLATFORM_UNAVAILABLE)
- Idempotency reconciliation: `app/reliability.py` (reconcile_idempotent_publish: stored ID → live marker search → safe publish)
- 13-case hard cases fixture: `tests/fixtures/phase4_hard_cases.json`

## Phase 5 — Certification Harness

- Certification harness tests: `tests/test_phase5.py`
- Response-shape validators and harness: `app/certification.py` (validate → publish → get_status → delete → verify; _failed records demotion alert; run_type: mock|local|live)
- Destination, evidence, and alert records: `app/models.py`
- Destination/certification application routes: `app/routes.py`
- Database migration: `alembic/versions/20261122_003_destinations_certification.py`

## Phase 6 — Integration Standard

- Integration drift tests: `tests/test_phase6.py` (OpenAPI path match, output manifest shape, OutputStore, batch collect_inputs, HMAC callback signature)
- OpenAPI 3.1 document: `openapi.yaml` (matches running app exactly; 17 paths verified by drift test)
- Output manifest builder: `app/manifest.py`
- Simulation/local output abstraction: `app/output.py`
- HMAC callback helper: `app/callback.py` (sign_callback returns 64-char hex SHA-256)
- Batch CLI: `app/batch.py` (collect_inputs, run_batch, argparse main; runs against any API URL)

## Phase 7 — Catalogue, AI, Relevance, Tailoring

- Advanced tests: `tests/test_phase7.py` (CSV import, MockAI adapter, rank_destinations, tailor_rendition, 3 extra connector manifests)
- CSV catalogue import: `app/catalogue.py` (URL normalization, deduplication on platform+url, bad-row reporting, 1,000-row < 5 min)
- Mock AI adapter: `app/ai.py` (capture_rules → pending_confirmation; confirm requires human review)
- Relevance ranking: `app/recommendation.py` (rank_destinations sorts by audience overlap + score 1-5; precision_at_10 helper)
- Destination tailoring: `app/tailoring.py` (forum surface: canonical appended, body truncated; hashtag prefix; word-boundary truncation)
- Extra manifests: `connectors/mrss.yaml`, `connectors/hashnode.yaml`, `connectors/kit.yaml`

## Phase 8 — Delivery Documents

- Delivery report: `REPORT.md`
- Submission guidance: `Submission-Form-Guide.md`
- Demo script: `Demo-Script.md`
- Source inventory: `SOURCES.md`
- AI-use disclosure: `AI_USE.md`

## Outstanding / Verified

- Precision@10 helper: `app/recommendation.py` — `tests/test_outstanding.py`
- Recertification scheduler: `app/recertification.py` — `tests/test_outstanding.py`
- Three connectors return exact metrics shape: `tests/test_outstanding.py` (discourse, lemmy, ghost)
- 150-destination seed: `data/catalogue-150.csv` (151 lines = header + 150 rows)

