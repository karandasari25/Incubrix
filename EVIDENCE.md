# Evidence

## Phase 1

- Foundation tests: `tests/test_phase1.py`
- Secret scanning test: `tests/test_secrets.py`
- Health/readiness: `app/routes.py`
- Idempotency and correlation: `app/middleware.py`, `app/routes.py`
- Database job record: `app/models.py`, `alembic/versions/20261122_001_create_jobs.py`

## Phase 2

- Connector contract tests: `tests/test_phase2.py`
- Base connector contract: `app/connectors/base.py`
- Manifest loader: `app/connectors/loader.py`
- Discourse implementation: `app/connectors/discourse.py`
- Connector HTTP router: `app/connectors/router.py`
- Discourse simulation manifest: `connectors/discourse.yaml`
- Mock platform service: `app/mock_platforms.py`

## Phase 3

- Core connector tests: `tests/test_phase3.py`
- Lemmy implementation: `app/connectors/lemmy.py`
- Ghost implementation: `app/connectors/ghost.py`
- Dev.to implementation: `app/connectors/devto.py`
- HMAC webhook implementation: `app/connectors/webhook.py`
- Assisted implementation: `app/connectors/assisted.py`
- Connector manifests: `connectors/*.yaml`
- Local Lemmy/Ghost Compose services: `compose.yml`

## Phase 4

- Pure rules tests: `tests/test_phase4.py`
- Rules engine: `app/rules.py`
- Retry and 429 policy: `app/reliability.py`
- Idempotency reconciliation: `app/reliability.py`
- Stored reconciliation migration: `alembic/versions/20261122_002_job_reconciliation.py`

## Phase 5

- Certification harness tests: `tests/test_phase5.py`
- Response-shape validators and harness: `app/certification.py`
- Destination, evidence, and alert records: `app/models.py`
- Destination/certification application routes: `app/routes.py`
- Database migration: `alembic/versions/20261122_003_destinations_certification.py`

## Phase 6

- Integration drift tests: `tests/test_phase6.py`
- OpenAPI 3.1 document: `openapi.yaml`
- Output manifest builder: `app/manifest.py`
- Simulation/MinIO output abstraction: `app/output.py`
- HMAC callback helper: `app/callback.py`
- Batch CLI: `app/batch.py`

## Phase 7

- Advanced tests: `tests/test_phase7.py`
- CSV catalogue import: `app/catalogue.py`
- Mock AI adapter: `app/ai.py`
- Relevance ranking: `app/recommendation.py`
- Destination tailoring: `app/tailoring.py`
- Extra manifests: `connectors/mrss.yaml`, `connectors/hashnode.yaml`, `connectors/kit.yaml`

## Phase 8

- Delivery report: `REPORT.md`
- Submission guidance: `Submission-Form-Guide.md`
- Demo script: `Demo-Script.md`

## Outstanding

- Metrics, precision, scheduler, and catalogue tests: `tests/test_outstanding.py`
- Precision@10 helper: `app/recommendation.py`
- Recertification scheduler: `app.recertification.py`
- 150-destination seed: `data/catalogue-150.csv`
- Source/licence inventory: `SOURCES.md`
- AI-use disclosure: `AI_USE.md`
