import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.callback import send_signed_callback
from app.config import get_settings
from app.connectors.registry import get_registry
from app.manifest import build_output_manifest
from app.models import AlertTicket, Destination, Job, Publication
from app.output import OutputStore
from app.reliability import RetryPolicy, reconcile_idempotent_publish
from app.rules import evaluate_post_rules
from app.tailoring import tailor_rendition


def run_publish_pipeline(
    job_id: str,
    db: Session,
    sleep_fn: Callable[[float], None] | None = None,
) -> Job:
    """Execute the end-to-end publishing pipeline for a job."""
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
        # No destinations requested; complete as empty success
        manifest = build_output_manifest(
            providers={"simulation": "1.0.0"},
            settings={"simulation_mode": get_settings().simulation_mode},
            seed=0,
            timings={"accepted_seconds": 0.01},
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
        dest_record = db.query(Destination).filter(
            (Destination.id == dest_ref) | (Destination.name == dest_ref)
        ).first()

        if dest_record:
            dest_id = dest_record.id
            connector_key = dest_record.connector_key
            dest_dict = {
                "id": dest_record.id,
                "name": dest_record.name,
                "url": dest_record.url,
                "platform_key": dest_record.platform_key,
                "surface": dest_record.surface,
                "category": dest_record.category or "general",
                "frequency_cap": dest_record.frequency_cap or "weekly",
                "self_promo_allowed": True if dest_record.self_promo_allowed is None else dest_record.self_promo_allowed,
                "link_policy": dest_record.link_policy or "allowed",
                "disclosure_required": False if dest_record.disclosure_required is None else dest_record.disclosure_required,
                "status": dest_record.status,
                "excluded": dest_record.excluded,
            }
        else:
            # Fallback for transient or simulated destinations
            dest_id = dest_ref
            connector_key = "discourse"
            available = get_registry().list_connectors()
            if dest_ref.lower() in available:
                connector_key = dest_ref.lower()
            dest_dict = {
                "id": dest_ref,
                "name": dest_ref,
                "url": f"http://mock-platforms:8080/{connector_key}",
                "platform_key": connector_key,
                "surface": "topic" if connector_key == "discourse" else "post",
                "category": "general",
                "frequency_cap": "weekly",
                "self_promo_allowed": True,
                "link_policy": "allowed",
                "disclosure_required": False,
                "status": "active",
                "excluded": False,
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
            results.append({"destination": dest_ref, "status": "blocked", "error": "DESTINATION_EXCLUDED"})
            continue

        # 1. Tailor rendition
        tailored = tailor_rendition(rendition, dest_dict, {"title_max": 255, "body_max": 60000})

        # 2. Rules evaluation
        rule_res = evaluate_post_rules(tailored, dest_dict, [])
        if rule_res.get("decision") == "blocked":
            action = rule_res.get("action", "blocked")
            reasons = rule_res.get("reasons", ["BLOCKED"])
            code = reasons[0] if reasons else "RULE_BLOCKED"
            sched = None
            if rule_res.get("scheduled_for"):
                try:
                    sched = datetime.fromisoformat(rule_res["scheduled_for"].replace("Z", "+00:00"))
                except Exception:
                    pass

            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="scheduled" if action == "rescheduled" else "blocked",
                error_code=code,
                marker=marker,
                scheduled_for=sched,
            )
            db.add(pub)
            results.append({
                "destination": dest_ref,
                "status": action,
                "reasons": reasons,
                "scheduled_for": rule_res.get("scheduled_for"),
            })
            warnings.append(f"Destination '{dest_dict['name']}' blocked by rules: {', '.join(reasons)}")
            continue

        # 3. Connector validation
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
            results.append({"destination": dest_ref, "status": "failed", "error": str(exc)})
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
            results.append({"destination": dest_ref, "status": "failed", "violations": violations})
            warnings.append(f"Destination spec violation on '{dest_dict['name']}': {violations}")
            continue

        # 4. Publish
        try:
            pub_res = connector.publish(tailored, dest_dict, connection, job.idempotency_key)
            post_id = pub_res.get("platform_post_id")
            live_url = pub_res.get("live_url")

            # Status check
            stat = connector.get_status(post_id, connection)
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="succeeded",
                platform_post_id=post_id,
                live_url=live_url,
                marker=marker,
                attempts=1,
            )
            db.add(pub)
            succeeded_count += 1
            results.append({
                "destination": dest_ref,
                "status": "succeeded",
                "platform_post_id": post_id,
                "live_url": live_url,
            })
        except Exception as exc:
            pub = Publication(
                job_id=job.id,
                destination_id=dest_id,
                status="failed",
                error_code="PUBLISH_FAILED",
                marker=marker,
            )
            db.add(pub)
            results.append({"destination": dest_ref, "status": "failed", "error": str(exc)})
            warnings.append(f"Publish failed for '{dest_dict['name']}': {exc}")

        # Update progress along the way
        job.progress = int((idx / total) * 100)
        db.commit()

    # Determine final job status
    if succeeded_count > 0 or total == 0:
        job.status = "succeeded"
    else:
        # Check if all were blocked vs all failed
        job.status = "failed" if any(r.get("status") == "failed" for r in results) else "succeeded"

    job.progress = 100

    manifest = build_output_manifest(
        providers={dest: "1.0.0" for dest in destinations},
        settings={"simulation_mode": get_settings().simulation_mode},
        seed=0,
        timings={"pipeline_seconds": 0.05},
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

    # Optional callback
    if payload.get("callback_url"):
        try:
            send_signed_callback(
                payload["callback_url"],
                {"job_id": job.id, "status": job.status, "results": results},
                secret="incubrix-callback-secret",
            )
        except Exception:
            pass

    return job
