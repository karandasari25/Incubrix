import json
from datetime import datetime, timezone
from hashlib import sha256
from time import perf_counter
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.callback import send_signed_callback
from app.config import get_settings
from app.connectors.errors import ConnectorError
from app.connectors.registry import get_registry
from app.errors import APIError
from app.manifest import build_output_manifest
from app.models import AlertTicket, Destination, Job, Publication, utc_now
from app.output import OutputStore
from app.reliability import RetryPolicy
from app.rules import evaluate_post_rules
from app.tailoring import tailor_rendition


def run_publish_pipeline(
    job_id: str,
    db: Session,
    sleep_fn: Callable[[float], None] | None = None,
) -> Job:
    """Execute the end-to-end publishing pipeline for a job."""
    t_start = perf_counter()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    payload = job.payload or {}
    destinations = payload.get("destinations") or []
    marker = job.marker or sha256(job.idempotency_key.encode("utf-8")).hexdigest()[:16]

    job.status = "running"
    job.progress = 0
    db.commit()

    rendition = {
        "title": payload.get("title") or "Untitled publication",
        "body": payload.get("body") or "",
        "canonical_link": payload.get("canonical_link"),
        "tags": payload.get("tags") or [],
        "is_promotional": bool(payload.get("is_promotional")),
        "ai_generated": bool(payload.get("ai_generated")),
    }

    results = []
    warnings = []
    total = len(destinations)
    policy = RetryPolicy()

    if total == 0:
        manifest = build_output_manifest(
            providers={"simulation": "1.0.0"},
            settings={"simulation_mode": get_settings().simulation_mode},
            seed=0,
            timings={"pipeline_seconds": round(perf_counter() - t_start, 4)},
            warnings=["No destinations specified for this publication"],
            cost_estimate=0.0,
        )
        result_bytes = json.dumps(
            {"job_id": job.id, "status": "succeeded", "results": [], "manifest": manifest},
            indent=2,
        ).encode("utf-8")
        download_link = OutputStore().save(
            f"jobs/{job.id}/result.json",
            result_bytes,
            "application/json",
        )
        job.status = "succeeded"
        job.progress = 100
        job.result_links = [download_link]
        job.payload = {**payload, "results": [], "warnings": manifest["warnings"], "_output_manifest": manifest}
        db.commit()
        return job

    succeeded_count = 0
    for idx, dest_ref in enumerate(destinations, start=1):
        # 1. Strict destination lookup - no made-up mock destinations
        dest_record = db.query(Destination).filter(
            (Destination.id == dest_ref) | (Destination.name == dest_ref)
        ).first()

        if not dest_record:
            raise APIError(
                code="DESTINATION_NOT_FOUND",
                message=f"Destination '{dest_ref}' not found.",
                status_code=404,
                retryable=False,
                details={"destination": dest_ref},
            )

        dest_id = dest_record.id
        connector_key = dest_record.connector_key

        # 2. No permissive defaults: pass exact fields from destination record so missing rules fail closed
        dest_dict = {
            "id": dest_record.id,
            "name": dest_record.name,
            "url": dest_record.url,
            "platform_key": dest_record.platform_key,
            "surface": dest_record.surface,
            "category": dest_record.category,
            "frequency_cap": dest_record.frequency_cap,
            "self_promo_allowed": dest_record.self_promo_allowed,
            "link_policy": dest_record.link_policy,
            "disclosure_required": dest_record.disclosure_required,
            "automation_allowed": dest_record.automation_allowed,
            "connector_key": dest_record.connector_key,
            "status": dest_record.status,
            "excluded": dest_record.excluded,
        }

        # Check paused / excluded
        if dest_dict.get("status") == "paused" or dest_dict.get("excluded"):
            warn = f"Destination '{dest_dict['name']}' is paused or excluded; skipping."
            warnings.append(warn)
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="blocked",
                error_code="DESTINATION_EXCLUDED",
                marker=marker,
            )
            db.add(pub)
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": "blocked",
                "error_code": "DESTINATION_EXCLUDED",
                "reason": warn,
                "live_url": None,
                "platform_post_id": None,
            })
            continue

        # 3. Dynamic surface tailoring limits from connector manifest
        try:
            manifest = get_registry().get_manifest(connector_key)
            limits = {"title_max": 255, "body_max": 60000}
            for surf in manifest.get("surfaces", []):
                if surf.get("key") == dest_dict.get("surface"):
                    spec = surf.get("spec", {})
                    limits["title_max"] = spec.get("title_max_chars", 255)
                    limits["body_max"] = spec.get("body_max_chars", 60000)
                    break
        except Exception:
            limits = {"title_max": 255, "body_max": 60000}

        tailored = tailor_rendition(rendition, dest_dict, limits)

        # 4. Load real post history for frequency cap check
        history_pubs = db.query(Publication).filter(
            Publication.destination_id == dest_id,
            Publication.status.in_(["succeeded", "scheduled"]),
        ).all()
        post_history = [
            {"posted_at": p.created_at.isoformat() if p.created_at else utc_now().isoformat()}
            for p in history_pubs
        ]

        # 5. Rules evaluation
        rule_res = evaluate_post_rules(tailored, dest_dict, post_history)
        if rule_res.get("decision") == "blocked":
            action = rule_res.get("action", "blocked")
            reasons = rule_res.get("reasons", ["BLOCKED"])
            code = "DEST_RULE_FREQUENCY_CAP" if action == "rescheduled" or "FREQUENCY_CAP" in reasons else reasons[0]
            sched_dt = None
            sched_str = rule_res.get("scheduled_for")
            if sched_str:
                try:
                    sched_dt = datetime.fromisoformat(sched_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="scheduled" if action == "rescheduled" else "blocked",
                error_code=code,
                marker=marker,
                scheduled_for=sched_dt,
            )
            db.add(pub)
            reason_msg = f"Rescheduled for {sched_str} due to frequency cap" if action == "rescheduled" else f"Blocked by destination rules: {', '.join(reasons)}"
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": action,
                "error_code": code,
                "reason": reason_msg,
                "reasons": reasons,
                "scheduled_for": sched_str,
                "live_url": None,
                "platform_post_id": None,
            })
            warnings.append(f"Destination '{dest_dict['name']}': {reason_msg}")
            continue

        # 6. Connector lookup and spec validation
        try:
            connector = get_registry().get_connector(connector_key)
        except Exception as exc:
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="failed",
                error_code="CONNECTOR_NOT_FOUND",
                marker=marker,
            )
            db.add(pub)
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": "failed",
                "error_code": "CONNECTOR_NOT_FOUND",
                "reason": str(exc),
                "live_url": None,
                "platform_post_id": None,
            })
            warnings.append(f"Connector '{connector_key}' lookup failed: {exc}")
            continue

        connection = {"instance_url": dest_dict.get("url", "")}
        val = connector.validate(tailored, dest_dict, connection)
        if not val.get("ok"):
            violations = val.get("violations", [])
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="failed",
                error_code="DEST_SPEC_VIOLATION",
                marker=marker,
            )
            db.add(pub)
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": "failed",
                "error_code": "DEST_SPEC_VIOLATION",
                "reason": f"Surface spec violations: {violations}",
                "violations": violations,
                "live_url": None,
                "platform_post_id": None,
            })
            warnings.append(f"Destination spec violation on '{dest_dict['name']}': {violations}")
            continue

        # 7. Publish wrapped in RetryPolicy with per-destination idempotency key
        dest_idempotency_key = f"{job.idempotency_key}:{dest_id}"
        dest_marker = sha256(dest_idempotency_key.encode("utf-8")).hexdigest()[:16]

        attempt = 1
        max_attempts = 5
        pub_res = None
        error_code = None
        error_msg = None

        while attempt <= max_attempts:
            try:
                pub_res = connector.publish(tailored, dest_dict, connection, dest_idempotency_key)
                break
            except ConnectorError as ce:
                error_code = ce.code
                error_msg = ce.message
                retry_after_val = None
                if ce.details and isinstance(ce.details, dict):
                    retry_after_val = str(ce.details.get("retry_after", "")) or None
                action = policy.next_action(
                    status=ce.status_code,
                    retry_after=retry_after_val,
                    attempt=attempt,
                )
                if action.get("retry") and attempt < max_attempts:
                    delay = action.get("delay_seconds", 0)
                    if ce.status_code == 429:
                        warnings.append(f"Destination '{dest_dict['name']}': Rate limited (429). Waiting {delay}s before retry")
                    if sleep_fn:
                        sleep_fn(delay)
                    attempt += 1
                    continue
                if (ce.status_code == 503 or ce.code == "PLATFORM_UNAVAILABLE") and attempt >= 5:
                    warnings.append(f"Destination '{dest_dict['name']}': Stopped retrying after 5 consecutive 503 PLATFORM_UNAVAILABLE errors")
                break
            except Exception as exc:
                error_code = "PUBLISH_FAILED"
                error_msg = str(exc)
                action = policy.next_action(status=500, attempt=attempt)
                if action.get("retry") and attempt < max_attempts:
                    delay = action.get("delay_seconds", 0)
                    if sleep_fn:
                        sleep_fn(delay)
                    attempt += 1
                    continue
                break

        if pub_res:
            post_id = pub_res.get("platform_post_id")
            live_url = pub_res.get("live_url")
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="succeeded",
                platform_post_id=post_id,
                live_url=live_url,
                marker=dest_marker,
                attempts=attempt,
            )
            db.add(pub)
            succeeded_count += 1
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": "succeeded",
                "error_code": None,
                "reason": "Published successfully",
                "platform_post_id": post_id,
                "live_url": live_url,
            })
        else:
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="failed",
                error_code=error_code or "PUBLISH_FAILED",
                marker=dest_marker,
                attempts=attempt,
            )
            db.add(pub)
            results.append({
                "destination_id": dest_id,
                "destination": dest_dict["name"],
                "status": "failed",
                "error_code": error_code or "PUBLISH_FAILED",
                "reason": error_msg or "Failed to publish",
                "live_url": None,
                "platform_post_id": None,
            })
            warnings.append(f"Publish failed for '{dest_dict['name']}': {error_msg}")

        job.progress = int((idx / total) * 100)
        db.commit()

    if succeeded_count > 0 or total == 0:
        job.status = "succeeded"
    else:
        job.status = "failed" if any(r.get("status") == "failed" for r in results) else "succeeded"

    job.progress = 100
    elapsed_total = perf_counter() - t_start

    manifest = build_output_manifest(
        providers={dest_ref: "1.0.0" for dest_ref in destinations},
        settings={"simulation_mode": get_settings().simulation_mode},
        seed=0,
        timings={"pipeline_seconds": round(elapsed_total, 4)},
        warnings=warnings,
        cost_estimate=0.0,
    )
    result_bytes = json.dumps(
        {"job_id": job.id, "status": job.status, "results": results, "manifest": manifest},
        indent=2,
    ).encode("utf-8")
    download_link = OutputStore().save(
        f"jobs/{job.id}/result.json",
        result_bytes,
        "application/json",
    )
    job.result_links = [download_link]
    job.payload = {
        **payload,
        "results": results,
        "warnings": warnings,
        "_output_manifest": manifest,
    }
    db.commit()

    if payload.get("callback_url"):
        try:
            callback_secret = get_settings().callback_secret
            send_signed_callback(
                payload["callback_url"],
                {"job_id": job.id, "status": job.status, "results": results},
                secret=callback_secret,
            )
        except Exception:
            pass

    return job
