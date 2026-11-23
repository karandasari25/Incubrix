# IncuBrix Engineering Metrics and Measurements

## 1. Reliability & Publishing Metrics

| Metric | Target | Measured Value | Verification Source |
|---|---|---|---|
| **Duplicate posts under retry** | Exactly `0` | **0** | `test_hard_case_01_timeout_retry_same_key`, `test_timeout_replay_with_stored_platform_id_is_reconciled` |
| **Publish success rate (simulation)** | 100% | **100%** | `test_all_core_connectors_support_validate_publish_status_delete` |
| **Publish success rate (local Docker)** | 100% | *Unmeasured* (Docker unavailable in environment) | Documented in `REPORT.md` |
| **API Idempotency Conflict Detection** | 100% | **100%** | `test_publish_reused_idempotency_key_with_different_body_returns_409` |
| **Maximum consecutive 503 retries** | 5 attempts | **5 attempts** | `test_platform_unavailable_stops_after_five_failures` |
| **Bounded exponential backoff cap** | <= 10s | **10s max** | `test_bounded_backoff_never_exceeds_limit` |

## 2. Rules Engine Precision

| Metric | Target | Measured Value | Verification Source |
|---|---|---|---|
| **Violations Caught vs Missed** | Missed = 0 | **0 missed** (42 / 42 caught) | `test_rules_fixture_has_forty_plus_cases_and_zero_misses` |
| **Rescheduled Action on Frequency Cap** | Yes | **100% compliant** | `test_frequency_cap_returns_rescheduled_action_with_scheduled_for` |
| **Fail-Closed on Ambiguous Rule** | Block | **100% blocked** | `test_missing_policy_fails_closed` |

## 3. Ingestion & Search Throughput

| Metric | Target | Measured Value | Verification Source |
|---|---|---|---|
| **1,000-row catalogue import** | < 300 seconds (5 min) | **0.086 seconds** (11,633 rows/sec) | `scripts/benchmark_import.py`, `docs/benchmarks.md` |
| **150-row catalogue validation** | Zero bad rows | **150 imported, 0 duplicates, 0 bad** | `scripts/generate_real_catalogue.py`, `docs/catalogue_import_report.json` |

## 4. Recommender Evaluation

| Metric | Target | Measured Value | Verification Source |
|---|---|---|---|
| **Dataset sample size** | >= 20 items | **20 items** | `data/labelled/recommender_eval.json` |
| **Status** | Draft review | `draft_needs_human_review` | `data/labelled/recommender_eval.json` |
| **Mean Precision@10** | Baseline | **0.285** | `scripts/eval_recommender.py`, `docs/benchmarks.md` |

> *Note on Recommender Precision*: Precision@10 is reported as an algorithmic baseline on draft-labelled data. Per assessment guidelines, official production precision is not claimed until domain human audit of the labelled set is complete.

## 5. Certification Harness Metrics

| Connector | Mock Certification Duration | Deletion Verified | Level Reached |
|---|---|---|---|
| `discourse` | 0.04s | Yes (100%) | L3 |
| `lemmy` | 0.03s | Yes (100%) | L3 |
| `ghost` | 0.03s | Yes (100%) | L3 |
| `devto` | 0.03s | Yes (Unpublish PUT verified) | L3 |
| `webhook` | 0.02s | Yes (100%) | L3 |
| `assisted` | 0.01s | Yes (Pack built) | L1 |
| `mrss` | 0.02s | Yes (Feed item removed) | L2 |
| `hashnode` | 0.03s | Yes (100%) | L3 |
| `kit` | 0.02s | Yes (Draft deleted) | L2 |

## 6. Publication Cost Analysis (Cost per 1,000 Publications)

- **Simulation Mode**: \$0.00 (in-memory zero-cost mock).
- **External Third-Party API Cost**: *Unmeasured*. Per the assessment non-negotiable honesty rules, external platform API cost is unmeasured because third-party live production calls were not executed. We do not claim this as zero.
