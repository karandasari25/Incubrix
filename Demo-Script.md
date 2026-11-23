# 8-Minute Demo Script

## 0:00–1:00 Clean start
Show repository structure and explain that connectors never touch the database.
Key files: `app/connectors/base.py`, `connectors/*.yaml`, `app/rules.py`.

## 1:00–2:00 Start
Run the test suite with no API keys:
```
python -m pytest -q
```
Show all 89 tests passing, 0 failures, 0 warnings about secrets.

## 2:00–3:30 Publish and replay
Create a publish request with an `Idempotency-Key`; replay the same request and show `replayed: true`.
Show 409 when replaying with a different payload.

## 3:30–5:00 Connector contract
Call Discourse `validate`, `publish`, `get_status`, and `delete` via the connector router.
State that the result is simulation evidence, not live evidence.
Show the manifest-driven registry: `app/connectors/registry.py`.

## 5:00–6:00 Handled failure
Show a title too long (`x * 256`) or a missing posting policy.
Explain that the result is `blocked` with a machine-readable reason code (`DEST_SPEC_VIOLATION`, `FREQUENCY_CAP`, etc.).

## 6:00–7:00 Design decision
Open `app/connectors/base.py` and `app/rules.py`.
Explain:
- Connectors are stateless adapters that return results only; they never touch the DB.
- The rules engine is a pure function (no I/O); missing or ambiguous policy always fails closed.
- Rescheduled (frequency cap) returns `action: rescheduled` with `scheduled_for`.

## 7:00–8:00 Evidence summary
Show `Submission-Form-Guide.md` and `EVIDENCE.md`.
State clearly what is verified (simulation/mock) versus what is unverified (live Lemmy/Ghost/Docker).
Run `git log --oneline` to show real commit history.
