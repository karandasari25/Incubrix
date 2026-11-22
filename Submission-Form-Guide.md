# Submission Form Guide

Use the following status only with the linked evidence.

| Requirement | Status | Evidence |
|---|---|---|
| Python/FastAPI/PostgreSQL foundation | Yes | `tests/test_phase1.py`, `app/main.py`, Alembic migrations |
| Exact connector contract | Yes | `tests/test_phase2.py`, `app/connectors/base.py`, `app/connectors/router.py` |
| Six core connectors | Partial | `tests/test_phase3.py`; live Lemmy/Ghost/Dev.to behavior is not demonstrated |
| Pure fail-closed rules engine | Yes | `tests/test_phase4.py`, `app/rules.py` |
| Idempotency reconciliation | Partial | Database marker fields and reconciliation tests exist; live platform search is not demonstrated |
| Retry and 429 behavior | Yes | `tests/test_phase4.py`, `app/reliability.py` |
| Certification harness | Partial | Mock certification is tested; local/live certification is not demonstrated |
| OpenAPI drift protection | Yes | `tests/test_phase6.py`, `openapi.yaml` |
| MinIO implementation | Partial | Configuration and output abstraction exist; real object upload is not implemented |
| Batch CLI | Yes | `app/batch.py`, `tests/test_phase6.py` |
| CSV import | Yes | `tests/test_phase7.py`, `app/catalogue.py` |
| Mock AI adapter | Yes | `tests/test_phase7.py`, `app/ai.py` |
| Advanced MRSS/Hashnode/Kit | Partial | Manifest and simulation connector implementations exist; live APIs are not verified |
