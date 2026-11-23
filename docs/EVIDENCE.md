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
- Contract test suite: `tests/contract/test_contract.py` (10 tests: manifest schema × 9, instantiation × 9, endpoint contract, unsupported method -> 400, kill switch -> 503, unknown -> 404)
- Phase 2 endpoint tests: `tests/test_phase2.py` (validate, publish, get_status, delete contracts for Discourse)

## Phase 3 — Core Connectors

- Core connector tests: `tests/test_phase3.py` (all 6 connectors: validate/publish/get_status/delete, assisted build_assist_pack)
- All 6 connector implementations: `app/connectors/discourse.py`, `lemmy.py`, `ghost.py`, `devto.py`, `webhook.py`, `assisted.py`
- Simulation base: `app/connectors/simulation.py`
- Connector manifests: `connectors/*.yaml` (all 9 connectors with full Appendix A schema)

## Phase 4 — Rules Engine & Real Publish Pipeline

- Rules engine tests: `tests/test_phase4.py` (21 tests including pipeline execution, promo blocking, rules fixture runner, rescheduled action, frequency cap, promo, link policy, AI disclosure, reliability)
- Real publish pipeline: `app/pipeline.py` (orchestrates load destination -> tailoring -> rules check -> connector validate -> publish -> get_status -> persist Publication -> update job status/progress -> signed HMAC callback)
- Strict fail-closed destination rules: missing or ambiguous rules fail closed with `AMBIGUOUS_RULE`; permissive defaults eliminated.
- Post history frequency caps: loaded directly from historical `Publication` records (`succeeded`/`scheduled`).
- Missing destination validation: pre-validated in `POST /api/v1/publish` returning HTTP 404 (`DESTINATION_NOT_FOUND`).
- Dynamic manifest tailoring: title and body character limits dynamically loaded from connector manifest surface specs.
- Isolated idempotency keys: formatted per-destination (`{job.idempotency_key}:{dest_id}`) preventing cross-destination collisions.
- Real execution timing: execution duration recorded using high-resolution `time.perf_counter()`.
- Standardized job outcomes: each destination outcome contains `destination_id`, `destination`, `status`, `error_code`, `reason`, `live_url`, and `platform_post_id`.
- 42-case rules fixture: `tests/fixtures/rules_cases.json` (covers all rule codes; zero misses asserted)
- Rules engine: `app/rules.py` (pure fail-closed, `action: allowed|blocked|rescheduled`, `scheduled_for` on rescheduled, `FREQUENCY_CAP`, `SELF_PROMOTION_NOT_ALLOWED`, `LINK_POLICY_VIOLATION`, `AI_DISCLOSURE_REQUIRED`, `AMBIGUOUS_RULE:*`)
- Retry and 429 policy: `app/reliability.py` (RetryPolicy: exponential backoff, bounded max, 429 Retry-After, stop after 5 × PLATFORM_UNAVAILABLE)
- Idempotency reconciliation: `app/reliability.py` (reconcile_idempotent_publish: stored ID -> live marker search -> safe publish)
- 13-case hard cases fixture: `tests/fixtures/phase4_hard_cases.json`
- Alembic migration: `alembic/versions/20261122_004_publications_proposals.py` (creates `publications`, `rule_proposals`, and adds `destinations` status/excluded/rules_verified)

## Phase 5 — Certification Harness

- Certification harness tests: `tests/test_phase5.py`
- Response-shape validators and harness: `app/certification.py` (validate -> publish -> get_status -> delete -> verify; _failed records demotion alert; run_type: mock|local|live)
- Destination, evidence, and alert records: `app/models.py`
- Destination/certification application routes: `app/routes.py`
- Database migration: `alembic/versions/20261122_003_destinations_certification.py`

## Phase 6 — Integration Standard

- Integration drift tests: `tests/test_phase6.py` (OpenAPI path match, output manifest shape, OutputStore, batch collect_inputs, HMAC callback signature)
- OpenAPI 3.1 document: `openapi.yaml` (matches running app exactly; 18 paths verified by drift test)
- OpenAPI export script: `scripts/export_openapi.py`
- Output manifest builder: `app/manifest.py`
- Simulation/local output abstraction: `app/output.py`
- HMAC callback helper: `app/callback.py` (sign_callback returns 64-char hex SHA-256)
- Batch CLI: `app/batch.py` (collect_inputs, run_batch, argparse main; runs against any API URL)

## Phase 7 — Catalogue, AI, Relevance, Tailoring

- Advanced tests: `tests/test_phase7.py` (CSV import, MockAI adapter, rank_destinations, tailor_rendition, 3 extra connector manifests)
- CSV catalogue import: `app/catalogue.py` (URL normalization, deduplication on platform+url, bad-row reporting, 1,000-row < 5 min)
- Mock AI adapter: `app/ai.py` (capture_rules -> pending_confirmation; confirm requires human review)
- Relevance ranking: `app/recommendation.py` (rank_destinations sorts by audience overlap + score 1-5; precision_at_10 helper)
- Destination tailoring: `app/tailoring.py` (forum surface: canonical appended, body truncated; hashtag prefix; word-boundary truncation)
- Extra manifests: `connectors/mrss.yaml`, `connectors/hashnode.yaml`, `connectors/kit.yaml`

## Phase 8 — Recommender & Performance Benchmarks

- Recommendation endpoint: `POST /api/v1/recommendations` in `app/routes.py` (filters paused/excluded, checks rules, calculates composite fit_score and reason)
- Recommender evaluation script: `scripts/eval_recommender.py` (mean P@10 = 0.285)
- Recommender labelled evaluation dataset: `data/labelled/recommender_eval.json` (20 items, status `draft_needs_human_review`)
- Catalogue benchmark script: `scripts/benchmark_import.py` (1,000 rows in 0.086s; 11,633 rows/sec)
- Benchmark document: `docs/benchmarks.md`

## Phase 9 — Researched 150-Destination Catalogue

- Real catalogue datasets: `data/catalogue-150.csv` and `data/catalogue.csv` (150 real tech, AI, SaaS, creator, and video communities across Discourse, Lemmy, Ghost, Dev.to, Hashnode, Kit, MRSS, Webhook, and Assisted)
- Catalogue generator: `scripts/generate_real_catalogue.py`
- Ingestion report: `docs/catalogue_import_report.json` (150 imported, 0 duplicates, 0 bad rows)

## Phase 10 & 11 — Hard Cases, Tooling, Metrics & Frontend

- Operator Console: `frontend/index.html` mounted at `GET /console` (`include_in_schema=False`) and containerized in `Dockerfile`, featuring publication composer, destination multi-select, live job monitor, progress bar, outcomes table, and raw manifest inspector.
- Hard cases test suite: `tests/test_hard_cases.py` (17 tests covering all hard cases from the brief including non-existent destination 404, weekly cap rescheduling, and ambiguous rule fail-closed blocking)
- Overall test suite: 108 tests passing, 0 failures across all modules.
- Hard cases documentation: `docs/HARD_CASES.md` (audit table linking case ID to test and verified actual outcome)
- Performance & quality metrics: `docs/METRICS.md` (duplicate posts under retry = 0, rules missed = 0, 1000-row import = 0.086s, precision@10 = 0.285)
- Delivery report: `REPORT.md`
- Submission guidance: `Submission-Form-Guide.md`
- Demo script: `Demo-Script.md`
- Source inventory: `SOURCES.md`
- AI-use disclosure: `AI_USE.md`
