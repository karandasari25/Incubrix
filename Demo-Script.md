# 8-Minute Demo Script

## 0:00-1:00 Clean start
Show repository structure and explain that connectors never touch the database.

## 1:00-2:00 Start
Run `docker compose config --quiet`, then start the application locally.

## 2:00-3:30 Publish and replay
Create a publish request with an `Idempotency-Key`; replay the same request and show `replayed: true`.

## 3:30-5:00 Connector contract
Call Discourse `validate`, `publish`, `get_status`, and `delete`. State that the
result is simulation evidence, not live evidence.

## 5:00-6:00 Handled failure
Show a title too long or a missing posting policy. Explain that the result is
blocked and carries a machine-readable reason.

## 6:00-7:00 Design decision
Open [app/connectors/base.py](/Users/radha/Downloads/incruibix/app/connectors/base.py)
and [app/rules.py](/Users/radha/Downloads/incruibix/app/rules.py). Explain
separation of connectors and pure fail-closed rules.

## 7:00-8:00 Tests
Run the test suite and close with exactly what is verified versus what remains unverified.
