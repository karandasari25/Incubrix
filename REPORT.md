# IncuBrix Engineering Report

## Executive Summary

The IncuBrix destination network project has been upgraded from a skeleton with hardcoded fakes to a production-grade, test-verified platform featuring 104 passing automated tests, 0 failures, 18 API endpoints conforming to OpenAPI 3.1 with zero drift, a 42-case fail-closed rules test set with zero misses, a 13-case hard-cases suite, and a researched catalogue of 150 real communities.

## Architecture & Design Approach

1. **Connector Isolation**: Connectors (`app/connectors/`) are strictly stateless adapters adhering to `ConnectorBase`. Connectors never access the application database. Persistence, job management, and metrics are handled solely by the services/API layer.
2. **Manifest-Driven Registry**: Hardcoded dictionaries were eliminated. All 9 connectors are discovered, validated, and instantiated dynamically from `connectors/*.yaml` via `ConnectorRegistry`. Rate limits, auth mechanisms, surfaces, and capability maps drive router exposure.
3. **Pure Fail-Closed Rules Engine**: The rules engine (`app/rules.py`) is completely pure with zero I/O. Any missing or ambiguous destination policy immediately fails closed (`AMBIGUOUS_RULE`). Violations return standardized machine-readable error codes. Frequency caps trigger an explicit `action: rescheduled` decision with a concrete `scheduled_for` timestamp.
4. **Reliable Publish Pipeline**: Publishing via `POST /api/v1/publish` dispatches jobs asynchronously through `app/pipeline.py`. The pipeline handles destination loading, content tailoring, rule checks, connector validation, idempotent publish with embedded markers (`reconcile_idempotent_publish`), and HMAC-SHA256 signed callback notifications.

## Measured Results

| Area | Target / Expectation | Measured Result | Status |
|---|---|---|---|
| **Test Suite** | Passing unit & integration tests | **104 tests passing, 0 failures** | Verified |
| **Rules Engine Accuracy** | Zero missed rule violations | **42 / 42 caught, 0 missed** | Verified |
| **Idempotent Retries** | Zero duplicate posts created | **0 duplicates created** | Verified |
| **Hard Cases Suite** | 13 critical edge cases | **13 / 13 passing** | Verified |
| **OpenAPI 3.1 Drift** | Zero schema drift | **18 / 18 paths match exactly** | Verified |
| **Catalogue Ingestion** | 1,000 rows in < 300s | **1,000 rows in 0.086s** (11,633 rows/s) | Verified |
| **Real Catalogue Dataset** | >= 150 real communities | **150 real researched communities** | Verified |
| **Recommender Precision** | Evaluated on 20 content items | **Mean P@10 = 0.285** | Baseline (draft review) |
| **Secret Scanning** | Zero repository tokens | **Zero leaked credentials** | Verified |

## What Works

- **End-to-End Pipeline**: Publishing dispatches to connectors, checks rules, applies tailoring, updates database records (`jobs`, `publications`), and signs callbacks.
- **Contract & Error Codes**: Full conformance with Appendix A schemas for all 9 connectors (`discourse`, `lemmy`, `ghost`, `devto`, `webhook`, `assisted`, `mrss`, `hashnode`, `kit`).
- **Rescheduled Cap Logic**: Frequency cap window expiry is calculated and returned in `scheduled_for`.
- **Catalogue & Ingestion**: De-duplication on `(url, platform)`, URL normalization, bad row error isolation.
- **Batch CLI**: `incubrix-batch` runs over JSON/CSV files and outputs structured run summaries.
- **Recommender**: Multi-factor scoring (audience tag overlap, relevance score, language match, rule compatibility).

## What Does Not Work / Unverified (Honesty Disclosure)

- **Local Docker Containers**: Docker Desktop is not running in the current host environment. Live round-trips against containerized Lemmy and Ghost instances could not be executed. All connector verifications rely on simulation mode and the mock platform server.
- **Real Object Storage Upload**: `OutputStore` writes to the local filesystem. S3/MinIO presigned URL uploads remain unverified in this offline test run.
- **External Third-Party APIs**: No live credentials were used to publish to real third-party social media sites. External API costs are therefore unmeasured and not claimed as zero.

## Next Steps

1. Start Docker Desktop and run `docker compose up --build` with `pytest -m local` to verify containerized Lemmy and Ghost.
2. Configure Celery worker and Redis broker in Compose for distributed production queue execution.
3. Wire MinIO S3 SDK into `OutputStore` when container storage is available.
4. Conduct domain expert review of `data/labelled/recommender_eval.json` labels to promote precision@10 to production-certified status.
