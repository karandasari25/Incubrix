from datetime import datetime, timezone
import logging
from celery import Celery

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, Publication
from app.pipeline import run_publish_pipeline

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "incubrix",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scheduled-publications-tick": {
            "task": "app.worker.scheduled_publications_tick",
            "schedule": 30.0,
        },
    },
)


@celery_app.task(name="app.worker.publish_pipeline_task")
def publish_pipeline_task(job_id: str) -> dict:
    """Execute publish pipeline asynchronously, transitioning queued -> running -> succeeded/failed."""
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"error": f"Job {job_id} not found", "status": "failed"}

        job.status = "running"
        db.commit()

        try:
            job = run_publish_pipeline(job.id, db)
            return {"job_id": job.id, "status": job.status, "progress": job.progress}
        except Exception as exc:
            job.status = "failed"
            db.commit()
            return {"job_id": job.id, "status": "failed", "error": str(exc)}


@celery_app.task(name="app.worker.scheduled_publications_tick")
def scheduled_publications_tick() -> dict:
    """Periodic scheduler tick executing scheduled publications whose cap window has elapsed."""
    return run_scheduled_publications_tick()


def run_scheduled_publications_tick(db=None) -> dict:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        now = datetime.now(timezone.utc)
        due_pubs = db.query(Publication).filter(
            Publication.status == "scheduled",
            Publication.scheduled_for <= now,
        ).all()

        executed = []
        for pub in due_pubs:
            job = db.query(Job).filter(Job.id == pub.job_id).first()
            if job:
                job.status = "running"
                db.commit()
                run_publish_pipeline(job.id, db)
                executed.append(pub.id)

        return {"due_count": len(due_pubs), "executed": executed}
    finally:
        if close_db:
            db.close()
