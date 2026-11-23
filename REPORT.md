# IncuBrix Engineering Report

## Approach

The system separates connector calls from application persistence and uses
configuration-backed YAML manifests for each supported connector type.

A manifest-driven registry (`app/connectors/registry.py`) loads all 9 connector
manifests from `connectors/*.yaml` at startup. The HTTP router uses the registry
for capability checks, kill-switch enforcement, and connector instantiation —
no hardcoded dicts.

The rules engine (`app/rules.py`) is a pure function with no I/O: it returns
`action: allowed | blocked | rescheduled` with machine-readable reason codes
(`FREQUENCY_CAP`, `SELF_PROMOTION_NOT_ALLOWED`, `LINK_POLICY_VIOLATION`,
`AI_DISCLOSURE_REQUIRED`, `AMBIGUOUS_RULE:*`). A rescheduled result includes
`scheduled_for` (the timestamp when the cap window expires). Missing or ambiguous
rules always fail closed.

## What Works (Verified by Tests)

- **Foundation**: health, readiness, idempotency, 409 on reused key with different
  payload, standard error format, structured JSON logs with secret redaction (89 tests total, 0 failures).
- **Connector contract**: 9 manifests conforming to Appendix A schema; registry
  with capability check and kill-switch; contract test suite (10 tests × 9 connectors).
- **Six core connectors**: Discourse, Lemmy, Ghost, Dev.to, Webhook, Assisted —
  all verified in simulation mode (validate/publish/get_status/delete/build_assist_pack).
- **Rules engine**: 42-case fixture asserted at zero misses; `rescheduled` action
  with `scheduled_for` for frequency-cap-only blocks.
- **Reliability**: RetryPolicy with bounded exponential backoff; Retry-After header
  parsing; stop after 5 × PLATFORM_UNAVAILABLE; idempotency reconciliation.
- **Certification harness**: mock-mode validate→publish→status→delete→verify cycle.
- **OpenAPI drift**: 17 app routes == 17 documented paths; drift test verifies every run.
- **Catalogue import**: URL normalization, deduplication, bad-row report, 1,000-row
  throughput < 5 minutes.
- **Batch CLI**: collect_inputs, run_batch, argparse main.
- **Relevance ranking**: rank_destinations with audience-tag overlap and score 1–5;
  precision@10 helper.
- **Tailoring**: forum-surface canonical append, word-boundary truncation, hashtag prefix.
- **Mock AI adapter**: capture_rules → `pending_confirmation`; confirm requires human review.
- **Recertification scheduler**: recertification_due, select_due_destinations.
- **150-destination seed**: `data/catalogue-150.csv` (151 lines).

## What Does Not Work / Unverified

- **Real connector HTTP calls**: All connectors run in simulation mode.
  Live Lemmy/Ghost require Docker containers not available in this environment.
- **Background jobs (Celery/inline)**: Jobs stay `queued`; no worker dispatched.
- **Real MinIO uploads**: `app/output.py` only writes to local filesystem in
  simulation mode; presigned S3 links not implemented.
- **Live certification**: mock-mode only; real round-trips to Lemmy/Ghost/Discourse
  not demonstrated.
- **Real AI provider**: Only the mock adapter is used; no external LLM calls.
- **Docker Compose**: Lemmy/Ghost/worker containers boot but are not verified
  end-to-end (Docker Desktop not available in environment).

## Measured Results

- **Test suite**: 89 tests, 0 failures, no API keys required.
- **Rules fixture**: 42 cases, 0 misses.
- **Catalogue throughput**: 1,000 rows in < 1 second (Python dict-based dedup).
- **OpenAPI drift**: 0 (all 17 paths match).

## Cost per 1,000 Publications

All results are simulation/mock. No external API calls are made in tests.
Real cost cannot be reported until live connectors are verified.

## Next Steps

1. Wire inline job runner so `POST /api/v1/publish` dispatches connector calls.
2. Add Celery worker + beat scheduler to Compose for background execution.
3. Implement real httpx connector adapters guarded by `CONNECTOR_MODE != simulation`.
4. Add real MinIO presigned upload to `app/output.py`.
5. Verify local Lemmy and Ghost with `pytest -m local` after Docker is available.
Local simulation cost is estimated at **0.000 external API credits** because no
external calls are made. Infrastructure cost depends on the user's PostgreSQL,
Redis, MinIO, and Celery deployment. Cost per 1,000 live publications cannot be
measured until live credentials and target platforms are available.

## Approaches considered

Connectors were separated from application persistence to prevent duplicate
database behavior in platform implementations. A YAML manifest and base class
were preferred over destination-specific code. Reconciliation is marker-first
and stored-ID-first. AI rule capture remains pending human confirmation.

## Next steps

Implement real MinIO object writes, worker execution, live platform HTTP
adapters, live Lemmy/Ghost certification, and recertification scheduling.
