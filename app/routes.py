from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import APIError
from app.models import Job
from app.schemas import PublishRequest, DestinationCreate, CatalogueImportRequest, AIRulesCaptureRequest
from hashlib import sha256
from app.catalogue import import_catalogue_csv
from app.ai import MockAIAdapter
from app.recertification import select_due_destinations
from datetime import datetime, timezone

from app.certification import CertificationHarness
from app.models import AlertTicket, CertificationEvidence, Destination
from app.manifest import build_output_manifest
from app.output import OutputStore
import json
import hmac
from hashlib import sha256


router = APIRouter()


@router.get("/")
def root() -> dict:
    return {
        "service": "IncuBrix",
        "status": "running",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "ready": "/ready",
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    return {"status": "ready", "simulation_mode": settings.simulation_mode}


def _clean_payload(payload_dict: dict) -> dict:
    if not isinstance(payload_dict, dict):
        return {}
    return {k: v for k, v in payload_dict.items() if not k.startswith("_")}


@router.post("/api/v1/publish", status_code=202)
def publish(
    request: Request,
    payload: PublishRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict:
    current_payload = payload.model_dump()
    existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    if existing:
        if _clean_payload(existing.payload) != _clean_payload(current_payload):
            raise APIError(
                code="IDEMPOTENCY_KEY_REUSED",
                message="Idempotency key was previously used with a different request payload.",
                status_code=409,
                retryable=False,
                details={"idempotency_key": idempotency_key},
            )
        result_links = existing.result_links or []
        existing_manifest = existing.payload.get("_output_manifest")
        return {
            "job_id": existing.id,
            "status": existing.status,
            "replayed": True,
            "result_links": result_links,
            "warnings": ["Idempotency replay returned the existing job"],
            "output_manifest": existing_manifest,
        }

    job = Job(
        idempotency_key=idempotency_key,
        status="queued",
        progress=0,
        payload=current_payload,
        result_links=[],
        marker=sha256(idempotency_key.encode("utf-8")).hexdigest()[:16],
    )
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
        if existing:
            if _clean_payload(existing.payload) != _clean_payload(current_payload):
                raise APIError(
                    code="IDEMPOTENCY_KEY_REUSED",
                    message="Idempotency key was previously used with a different request payload.",
                    status_code=409,
                    retryable=False,
                    details={"idempotency_key": idempotency_key},
                )
            return {
                "job_id": existing.id,
                "status": existing.status,
                "replayed": True,
                "result_links": existing.result_links or [],
                "warnings": ["Idempotency replay returned the existing job"],
                "output_manifest": existing.payload.get("_output_manifest"),
            }
        raise APIError(
            code="INTERNAL_ERROR",
            message="Database error during job creation",
            status_code=500,
            retryable=False,
        )

    manifest = build_output_manifest(
        providers={"simulation": "1.0.0"},
        settings={"simulation_mode": get_settings().simulation_mode},
        seed=0,
        timings={"accepted_seconds": 0.01},
        warnings=["No platform posts were created by the Phase 1 job skeleton"],
        cost_estimate=0.0,
    )
    result_file = json.dumps({
        "job_id": job.id,
        "status": job.status,
        "manifest": manifest,
    }, indent=2).encode("utf-8")
    download_link = OutputStore().save(
        f"jobs/{job.id}/result.json",
        result_file,
        "application/json",
    )
    job.result_links = [download_link]
    job.payload = {**job.payload, "_output_manifest": manifest}
    db.commit()
    return {
        "job_id": job.id,
        "status": job.status,
        "replayed": False,
        "result_links": job.result_links,
        "warnings": manifest["warnings"],
        "output_manifest": manifest,
    }


@router.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result_links": job.result_links or [],
    }


@router.post("/api/v1/destinations", status_code=201)
def create_destination(payload: DestinationCreate, db: Session = Depends(get_db)) -> dict:
    destination = Destination(**payload.model_dump())
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return {
        "id": destination.id,
        "name": destination.name,
        "connector_key": destination.connector_key,
        "level": destination.level,
    }


@router.get("/api/v1/destinations")
def list_destinations(db: Session = Depends(get_db)) -> dict:
    destinations = db.query(Destination).all()
    return {"destinations": [
        {"id": item.id, "name": item.name, "connector_key": item.connector_key,
         "level": item.level}
        for item in destinations
    ]}


@router.post("/api/v1/certification", status_code=202)
def certification(
    destination_id: str,
    run_type: str,
    db: Session = Depends(get_db),
) -> dict:
    if run_type not in {"mock", "local", "live"}:
        raise HTTPException(status_code=400, detail="run_type must be mock, local, or live")
    destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")

    destination_data = {
        "name": destination.name,
        "url": destination.url,
        "connector_key": destination.connector_key,
        "level": destination.level,
    }
    rendition = {
        "title": "IncuBrix certification test",
        "body": "This temporary certification post must be deleted.",
        "canonical_link": None,
        "media": [],
        "tags": [],
        "is_promotional": False,
        "ai_generated": False,
    }
    connection = {"instance_url": destination.url, "auth": {}}
    evidence = CertificationHarness(run_type).run(
        destination_data,
        rendition,
        connection,
    )

    destination.level = evidence["level"]
    destination.last_certified_at = datetime.now(timezone.utc)
    db_record = CertificationEvidence(
        destination_id=destination.id,
        connector_key=destination.connector_key,
        run_type=evidence["run_type"],
        passed=evidence["passed"],
        level=evidence["level"],
        evidence=evidence,
        warnings=evidence["warnings"],
    )
    db.add(db_record)
    if evidence["alert"]:
        db.add(AlertTicket(
            destination_id=destination.id,
            type=evidence["alert"]["type"],
            reason=evidence["alert"]["reason"],
            details={"violations": evidence["alert"]["violations"]},
        ))
    db.commit()
    db.refresh(db_record)
    return {"evidence_id": db_record.id, "run_type": run_type,
            "passed": evidence["passed"], "level": evidence["level"],
            "warnings": evidence["warnings"], "alert": evidence["alert"]}


@router.post("/api/v1/catalogue/import", status_code=202)
def catalogue_import(payload: CatalogueImportRequest) -> dict:
    report = import_catalogue_csv(payload.csv_path)
    return {
        "job_status": "succeeded",
        "warnings": [
            f"{report['duplicates']} duplicate rows",
            f"{report['bad_rows']} bad rows",
        ],
        "report": report,
    }


@router.post("/api/v1/ai/rules/capture", status_code=202)
def capture_ai_rules(payload: AIRulesCaptureRequest) -> dict:
    candidate = MockAIAdapter().capture_rules(payload.text)
    return {
        "status": candidate["status"],
        "candidate_rules": candidate["candidate_rules"],
        "warnings": ["Captured rules require human confirmation before use"],
    }


@router.get("/api/v1/certification/due")
def certification_due(
    interval_days: int = 30,
    db: Session = Depends(get_db),
) -> dict:
    if interval_days < 1:
        raise HTTPException(status_code=400, detail="interval_days must be at least 1")
    destinations = db.query(Destination).all()
    records = [
        {
            "id": item.id,
            "name": item.name,
            "last_certified_at": item.last_certified_at.isoformat()
            if item.last_certified_at else None,
        }
        for item in destinations
    ]
    due = select_due_destinations(records, interval_days=interval_days)
    return {"interval_days": interval_days, "due": due}
