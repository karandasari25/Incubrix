# Submission Form Guide

Use the following status only with the linked evidence.

| Requirement | Status | Evidence |
|---|---|---|
| Python/FastAPI/PostgreSQL foundation | Yes | `tests/test_phase1.py`, `app/main.py`, Alembic migrations (4 revisions through 004) |
| Exact connector contract | Yes | `tests/test_phase2.py`, `tests/contract/test_contract.py` (10 contract tests × 9 connectors), `app/connectors/registry.py`, `app/connectors/router.py` |
| Six core connectors | Yes (simulation) | `tests/test_phase3.py` (all 6 connectors: validate/publish/get_status/delete/build_assist_pack) |
| Pure fail-closed rules engine | Yes | `tests/test_phase4.py` (21 tests), `app/rules.py`, `tests/fixtures/rules_cases.json` (42 cases, 0 misses asserted) |
| Rescheduled action on frequency cap | Yes | `app/rules.py` returns `action: rescheduled` + `scheduled_for`; tested in rules fixture and dedicated test |
| Real publish pipeline | Yes (inline) | `app/pipeline.py`, `tests/test_phase4.py` (orchestrates load -> tailoring -> rules -> validate -> publish -> status -> db persistence -> callback) |
| Idempotency reconciliation | Yes | `app/reliability.py` (`reconcile_idempotent_publish`), `tests/test_phase4.py`, `tests/test_hard_cases.py` |
| Retry and 429 behavior | Yes | `tests/test_phase4.py`, `tests/test_hard_cases.py`, `app/reliability.py` (bounded exponential backoff, Retry-After, stop after 5 × PLATFORM_UNAVAILABLE) |
| Certification harness | Yes (mock) | `tests/test_phase5.py`, `app/certification.py` (validate -> publish -> status -> delete -> verify; demotion alert on failure) |
| OpenAPI drift protection | Yes | `tests/test_phase6.py`, `scripts/export_openapi.py`, `openapi.yaml` (18 paths, 0 drift) |
| MinIO implementation | Partial | `app/output.py` output abstraction exists; local filesystem tested; real S3/MinIO upload unverified |
| Batch CLI | Yes | `app/batch.py`, `tests/test_phase6.py` (collect_inputs, run_batch, argparse main) |
| CSV import | Yes | `tests/test_phase7.py`, `app/catalogue.py` (URL normalization, deduplication, bad-row report, 1,000 rows in 0.086s) |
| Mock AI adapter | Yes | `tests/test_phase7.py`, `app/ai.py` (pending_confirmation gate, human confirm required) |
| Recommendation engine | Yes | `app/recommendation.py`, `POST /api/v1/recommendations`, `tests/test_outstanding.py`, `data/labelled/recommender_eval.json` |
| Researched 150-destination catalogue | Yes | `data/catalogue-150.csv`, `data/catalogue.csv` (150 real communities), `docs/catalogue_import_report.json` |
| Advanced MRSS/Hashnode/Kit connectors | Yes (simulation) | Manifests and simulation implementations verified in contract and core suites |
| Secret redaction | Yes | `tests/test_secrets.py` (3 tests: repo scanner, token redaction, captured log redaction) |
| HMAC callback | Yes | `app/callback.py`, `tests/test_phase6.py` (64-char hex SHA-256 signature) |
| Hard cases pack | Yes | `tests/test_hard_cases.py` (13 tests), `docs/HARD_CASES.md` |
