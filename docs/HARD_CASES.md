# IncuBrix Hard Cases Verification Report

All 13 hard cases are tested via `tests/test_hard_cases.py` and `tests/fixtures/phase4_hard_cases.json`.

| Case ID | Case Description | Test / Input File | Expected System Action | Verified Actual Outcome |
|---|---|---|---|---|
| `HC-01` | Timeout then retry with same Idempotency-Key | `test_hard_case_01_timeout_retry_same_key` | Idempotent replay; returns existing `job_id`, `replayed=True`, 0 duplicates created | **Verified**: Replayed job returned with exact same `job_id` |
| `HC-02` | Rate limit 429 with Retry-After header | `test_hard_case_02_rate_limit_429_reset_header` | Retry scheduled with parsed `delay_seconds`, code `PLATFORM_RATE_LIMIT` | **Verified**: Retry scheduled for exact 30s delay |
| `HC-03` | Expired connection token (401) | `test_hard_case_03_expired_token` | `CONNECTION_AUTH_EXPIRED`, non-retryable, destination paused | **Verified**: `retryable=False`, mapped to `CONNECTION_AUTH_EXPIRED` |
| `HC-04` | Content rejected by destination (422) | `test_hard_case_04_content_rejected` | Map to `PLATFORM_CONTENT_REJECTED`, non-retryable | **Verified**: Error map translates 422 to `PLATFORM_CONTENT_REJECTED` |
| `HC-05` | Title exceeds surface character limit | `test_hard_case_05_title_too_long` | `DEST_SPEC_VIOLATION`, `ok=False`, field violation reported | **Verified**: `ok=False`, violation list includes `title` |
| `HC-06` | Unsupported media attached to surface | `test_hard_case_06_unsupported_media` | `DEST_SPEC_VIOLATION`, `ok=False`, media violation reported | **Verified**: `ok=False`, violation list includes `media` |
| `HC-07` | Second post within frequency cap window | `test_hard_case_07_second_post_inside_weekly_cap` | `action: rescheduled`, `scheduled_for` calculated, reason `FREQUENCY_CAP` | **Verified**: Rescheduled to end of weekly cap window |
| `HC-08` | Promotional post to non-promotional destination | `test_hard_case_08_promo_to_no_promo_destination` | `action: blocked`, reason `SELF_PROMOTION_NOT_ALLOWED` | **Verified**: Blocked with machine-readable reason |
| `HC-09` | Platform API renames/drops required fields | `test_hard_case_09_platform_field_rename_causes_demotion` | Certification fails, destination demoted to `L0`, alert ticket created | **Verified**: `level=L0`, `alert=destination_demoted` |
| `HC-10` | CSV import with duplicates, bad URLs, missing columns | `test_hard_case_10_csv_duplicates_and_bad_urls` | Deduplicate on (url, platform), reject bad URLs, row-level error report | **Verified**: 1 imported, 1 duplicate flagged, 2 bad rows rejected |
| `HC-11` | Partner webhook revokes permission (403) | `test_hard_case_11_partner_revokes_permission` | Map to `CONNECTION_AUTH_EXPIRED`, alert created, no retry | **Verified**: 403 mapped to `CONNECTION_AUTH_EXPIRED` in manifest |
| `HC-12` | Non-English community content (Unicode/accents) | `test_hard_case_12_non_english_community_preserved` | Preserved intact without rejection by English assumption | **Verified**: `decision=allowed`, accents preserved |
| `HC-13` | Destination requires AI disclosure tag | `test_hard_case_13_destination_requires_ai_disclosure` | Blocked if disclosure missing; reason `AI_DISCLOSURE_REQUIRED` | **Verified**: Blocked with `AI_DISCLOSURE_REQUIRED` |
