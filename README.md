# IncuBrix

## Phase 1 foundation

The Phase 1 service provides health/readiness endpoints, JSON logging,
correlation IDs, standard error bodies, idempotency-key enforcement, and
202-style publish jobs.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest
python -m uvicorn app.main:app --reload
```

## Docker Compose

Copy `.env.example` to `.env`, then run:

```powershell
docker compose up --build
```

## Phase 2 connector contract

Discourse is available as the template connector:

```text
POST /connector/v1/discourse/validate
POST /connector/v1/discourse/publish
POST /connector/v1/discourse/get_status
POST /connector/v1/discourse/delete
```

Connector implementations live in `app/connectors/` and must not access SQLAlchemy.
One YAML manifest per connector lives in `connectors/`; adding a platform type
should be configuration plus a connector implementation, never application-code
branches per destination.

## Phase 3 core connectors

The simulation registry includes Discourse, Lemmy, Ghost, Dev.to, a
HMAC-signed generic webhook, and an assisted connector. Compose includes
local Lemmy and Ghost services plus the mock platform service.

## Phase 4 rules and reliability

Phase 4 provides a database-free, fail-closed rules engine, stored idempotency
reconciliation metadata, reset-aware 429 handling, bounded backoff, and a
stop-after-five limit for consecutive platform availability failures.

## Phase 5 certification

`POST /api/v1/destinations` creates catalogue rows.

`POST /api/v1/certification?destination_id=...&run_type=mock`
starts a mock, local, or live certification run. The run type is never inferred:
mock results remain mock results. Failed publish/status/delete validation stores
evidence and creates an open destination-demotion alert ticket.

## Phase 6 integration standard

The OpenAPI document is generated from and tested against the running FastAPI
application. JSON and JSON/CSV batch inputs can be run with:

```powershell
incubrix-batch --source .\inputs --output-dir .\results --api-url http://127.0.0.1:8000
```

Simulation publications save a result file under `outputs/` and return a
`simulation://` link plus an output manifest. Optional callbacks are signed
with HMAC-SHA256 in `X-IncuBrix-Signature`.

## Phase 7 advanced

CSV catalogue import uses normalized URLs and reports duplicate/bad rows.
AI rule capture is implemented behind a mock adapter and is always pending
human confirmation. Relevance ranking, word-boundary tailoring, and three
additional connector manifests are included for MRSS, Hashnode, and Kit.

## Outstanding level

Simulation metrics are available for Discourse, Lemmy, and Ghost.
`GET /api/v1/certification/due?interval_days=30` lists destinations that require
recertification. The measured precision@10 helper is in
`app/recommendation.py`, and `data/catalogue-150.csv` contains 150 seed rows.
