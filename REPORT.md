# IncuBrix Phase 6 Report

## Approach

The system separates connector calls from application persistence and uses
configuration-backed manifests for each supported connector type. Phase 6 adds
the integration contract: OpenAPI drift checking, output manifests, downloadable
simulation results, signed callbacks, and a batch runner.

## What works

Foundation, connector contracts, rules, retries, certification, and integration
tests run from the repository with no external API credentials.

## What does not

Real MinIO uploads are not yet implemented behind the output abstraction.
Live Lemmy and Ghost certification remain unverified. Celery job execution is
not yet connected to the 202/job endpoint.

## Measured results

The complete local test suite contains 48 tests and passes without API keys.
Compose configuration renders successfully. Migration SQL renders through
revision `20261122_003`. The simulation and mock adapters produce no external
platform cost; external API cost is therefore unmeasured and should not be
claimed as zero.

## Cost per 1,000 publications

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
