# Submission Form Guide

Use the following status only with the linked evidence.

| Requirement | Status | Evidence |
|---|---|---|
| Python/FastAPI/PostgreSQL foundation | Yes | `tests/test_phase1.py`, `app/main.py`, Alembic migrations (3 revisions) |
| Exact connector contract | Yes | `tests/test_phase2.py`, `tests/contract/test_contract.py` (10 contract tests × 9 connectors), `app/connectors/registry.py`, `app/connectors/router.py` |
| Six core connectors | Yes (simulation) | `tests/test_phase3.py` (all 6 connectors: validate/publish/get_status/delete); live Lemmy/Ghost/Dev.to not demonstrated (no Docker) |
| Pure fail-closed rules engine | Yes | `tests/test_phase4.py` (19 tests), `app/rules.py`, `tests/fixtures/rules_cases.json` (42 cases, 0 misses asserted) |
| Idempotency reconciliation | Partial | `app/reliability.py` (reconcile_idempotent_publish tested); live platform marker search not demonstrated |
| Retry and 429 behavior | Yes | `tests/test_phase4.py`, `app/reliability.py` (bounded exponential backoff, Retry-After, stop after 5 × PLATFORM_UNAVAILABLE) |
| Rescheduled action on frequency cap | Yes | `app/rules.py` returns `action: rescheduled` + `scheduled_for`; tested in rules fixture and dedicated test |
| Certification harness | Partial | Mock certification tested (`tests/test_phase5.py`); local/live certification not demonstrated (no Docker) |
| OpenAPI drift protection | Yes | `tests/test_phase6.py`, `openapi.yaml` (17 paths, 0 drift) |
| MinIO implementation | Partial | `app/output.py` output abstraction exists; real object upload not implemented |
| Batch CLI | Yes | `app/batch.py`, `tests/test_phase6.py` (collect_inputs, argparse main) |
| CSV import | Yes | `tests/test_phase7.py`, `app/catalogue.py` (URL normalization, deduplication, bad-row report, 1,000 rows < 5 min) |
| Mock AI adapter | Yes | `tests/test_phase7.py`, `app/ai.py` (pending_confirmation gate, human confirm required) |
| Precision@10 helper | Yes | `tests/test_outstanding.py`, `app/recommendation.py` |
| Recertification scheduler | Yes | `tests/test_outstanding.py`, `app/recertification.py` |
| Three connectors return exact metrics shape | Yes | `tests/test_outstanding.py` (discourse, lemmy, ghost) |
| 150-destination seed catalogue | Yes | `data/catalogue-150.csv` (151 lines = header + 150 rows) |
| Advanced MRSS/Hashnode/Kit connectors | Partial | Manifests and simulation implementations exist; live API calls not verified |
| Secret redaction | Yes | `tests/test_secrets.py` (3 tests: repo scanner, token redaction, captured log redaction) |
| HMAC callback | Yes | `app/callback.py`, `tests/test_phase6.py` (64-char hex SHA-256 signature) |
