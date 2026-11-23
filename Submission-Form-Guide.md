# Submission Form Guide

Use the following status only with the linked evidence.

| Requirement | Status | Evidence |
|---|---|---|
| Python/FastAPI/PostgreSQL foundation | Yes | `tests/test_phase1.py`, `app/main.py`, Alembic migrations (4 revisions through 004) |
| Exact connector contract | Yes | `tests/test_phase2.py`, `tests/contract/test_contract.py` (10 contract tests × 9 connectors), `app/connectors/registry.py`, `app/connectors/router.py` |
| Six core connectors | Yes (real HTTPX & simulation) | `tests/test_phase3.py`, `tests/test_real_adapters_and_faults.py` (real HTTPX for Discourse, Lemmy, Ghost, DevTo, Webhook with JWT, HMAC, error map) |
| Pure fail-closed rules engine | Yes | `tests/test_phase4.py` (21 tests), `app/rules.py`, `tests/fixtures/rules_cases.json` (42 cases, 0 misses asserted) |
| Rescheduled action on frequency cap | Yes | `app/rules.py` returns `action: rescheduled` + `scheduled_for`; tested in rules fixture and dedicated test |
| Real publish pipeline | Yes (inline & celery) | `app/pipeline.py`, `app/worker.py`, `tests/test_phase4.py`, `tests/test_real_adapters_and_faults.py` (load -> tailoring -> rules -> validate -> publish -> status -> db persistence -> callback -> scheduler tick) |
| Idempotency reconciliation | Yes | `app/reliability.py` (`reconcile_idempotent_publish`), `tests/test_phase4.py`, `tests/test_hard_cases.py`, `tests/test_real_adapters_and_faults.py` |
| Retry and 429 behavior | Yes | `tests/test_phase4.py`, `tests/test_hard_cases.py`, `tests/test_real_adapters_and_faults.py`, `app/reliability.py` (bounded exponential backoff, Retry-After wait, stop after 5 × PLATFORM_UNAVAILABLE) |
| Certification harness & demotion | Yes (mock & verified deletion) | `tests/test_phase5.py`, `tests/test_real_adapters_and_faults.py`, `app/certification.py`, `app/recertification.py` (validate -> publish -> status -> delete -> verify deleted -> demote failing to L0/demoted) |
| OpenAPI drift protection | Yes | `tests/test_phase6.py`, `scripts/export_openapi.py`, `openapi.yaml` (18 paths, 0 drift) |
| MinIO implementation | Partial | `app/output.py` output abstraction exists; local filesystem tested; compose image pinned |
| Batch CLI | Yes | `app/batch.py`, `tests/test_phase6.py` (collect_inputs, run_batch, argparse main) |
| CSV import | Yes | `tests/test_phase7.py`, `app/catalogue.py` (URL normalization, deduplication, bad-row report, 1,000 rows in 0.086s) |
| Mock AI adapter | Yes | `tests/test_phase7.py`, `app/ai.py` (pending_confirmation gate, human confirm required) |
| Recommendation engine | Yes | `app/recommendation.py`, `POST /api/v1/recommendations`, `tests/test_outstanding.py`, `data/labelled/recommender_eval.json` |
| Researched 150-destination catalogue | Yes | `data/catalogue-150.csv`, `data/catalogue.csv` (150 real communities, 23 Appendix A columns, honest rules_verified boolean), `docs/catalogue_import_report.json` |
| Advanced MRSS/Hashnode/Kit connectors | Yes (simulation) | Manifests and simulation implementations verified in contract and core suites |
| Secret redaction | Yes | `tests/test_secrets.py` (3 tests: repo scanner, token redaction, captured log redaction) |
| HMAC callback | Yes | `app/callback.py`, `tests/test_phase6.py` (64-char hex SHA-256 signature) |
| Hard cases pack | Yes | `tests/test_hard_cases.py` (16 tests), `tests/test_real_adapters_and_faults.py` (17 tests), `docs/HARD_CASES.md` |
| Operator Web Console | Yes | `frontend/index.html`, `GET /console`, containerized in `Dockerfile` |
| Celery Background Worker & Scheduler | Yes | `app/worker.py`, `compose.yml` (`worker` + `scheduler` services), periodic scheduled publications tick |
